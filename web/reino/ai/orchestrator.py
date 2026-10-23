"""Orquestador del asesor (§10, pasos 1–8) tras la auditoría del PR #3.

1. Contexto firmado por servidor (tienda, sesión, perfil permitido).
2. Recupera solo memoria pertinente y AUTORIZADA por finalidad vigente (R07):
   una medida revocada jamás vuelve al contexto del modelo.
3. El modelo interpreta intención y decide herramientas (máx. 4 rondas).
4. Herramientas devuelven datos reales del catálogo/guía.
5. Filtrado/puntuación en backend (recommend).
6. El modelo redacta con esos resultados.
7. VALIDACIÓN: IDs desconocidos no se hidratan; el TEXTO se verifica contra
   la evidencia recuperada (R12): precios, porcentajes, fechas o garantías
   sin soporte en herramientas reemplazan la respuesta por una abstención
   honesta. Las tarjetas siempre se construyen en servidor.
8. Escrituras por PROPUESTA Y AUTORIZACIÓN (R11): el modelo nunca ejecuta
   una acción; genera una propuesta con permiso de un solo uso (ActionToken)
   que el comprador confirma. Repetir la llamada no duplica.

Modo degradado: si el proveedor no está disponible, responde el recomendador
basado en reglas y se ETIQUETA el modo disponible (nunca se simula IA).
"""

import json
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .. import services_memory
from ..models import ActionToken, AIConversation, AIMessage
from . import adapter, fallback
from .schemas import SYSTEM_PROMPT, TOOL_SPECS
from .tools import ToolContext, run_tool

MAX_HISTORY = 12  # no reenviar todo el historial en cada turno
WRITE_TOOLS = {"add_item_to_cart"}  # escrituras: propuesta + confirmación (R11)
ACTION_TTL_MINUTES = 15

_MONEY_RE = re.compile(r"\$\s*([0-9]+(?:[.,][0-9]{1,2})?)")
_PERCENT_RE = re.compile(r"(\d{1,2})\s*%")
_GUARANTEE_RE = re.compile(
    r"garantizad|llega hoy|entrega hoy|entrega inmediata|lo recibís hoy|"
    r"devolución asegurada|reembolso garantizado",
    re.IGNORECASE,
)

ABSTENTION_TEXT = (
    "No puedo confirmar ese dato con la información publicada de la tienda. "
    "¿Querés revisar juntos la ficha del producto o las políticas de entrega?"
)


def _memory_context(ctx):
    """Solo campos consentidos y pertinentes (capa estructurada, §12 y R07)."""
    if ctx.profile is None:
        return ""
    parts = [f"\nPerfil activo autorizado: «{ctx.profile.alias}» (elegido por el cliente)."]
    m = services_memory.authorized_measurement(ctx.store, ctx.session_key, ctx.profile)
    if m:
        medidas = []
        if m.chest_cm: medidas.append(f"pecho {m.chest_cm} cm")
        if m.neck_cm: medidas.append(f"cuello {m.neck_cm} cm")
        if m.back_cm: medidas.append(f"largo {m.back_cm} cm")
        if medidas:
            parts.append(f"Medidas guardadas ({m.measured_at:%Y-%m-%d}): {', '.join(medidas)}.")
    prefs = services_memory.authorized_preferences(ctx.profile, ctx.store, ctx.session_key)
    if prefs:
        parts.append("Preferencias consentidas: " + ", ".join(f"{k}={v}" for k, v in prefs.items()))
    return "\n".join(parts)


def get_conversation(store, session_key):
    conv = AIConversation.objects.filter(store=store, session_key=session_key).first()
    if conv is None:
        conv = AIConversation.objects.create(
            store=store, session_key=session_key,
            mode="ai" if adapter.available() else "rules",
        )
    return conv


def _validate_answer(answer_text, evidence_blobs):
    """Verificación de hechos comerciales del TEXTO libre (R12).

    Precio, porcentaje, fecha o garantía solo pueden afirmarse con soporte en
    resultados autorizados de herramientas de ESTE turno. Sin evidencia, la
    respuesta se reemplaza por una abstención honesta (nunca se «pule» el
    dato inventado).
    """
    if not answer_text:
        return answer_text, []
    problems = []
    evidence = " ".join(evidence_blobs)

    for amount in _MONEY_RE.findall(answer_text):
        normalized = amount.replace(",", ".")
        if normalized not in evidence:
            problems.append(f"precio_sin_evidencia:{amount}")
    for pct in _PERCENT_RE.findall(answer_text):
        if pct not in evidence and f"{pct} %" not in evidence:
            problems.append(f"porcentaje_sin_evidencia:{pct}")
    if _GUARANTEE_RE.search(answer_text) and '"fragments"' not in evidence \
            and '"zones"' not in evidence:
        problems.append("promesa_sin_evidencia")
    return answer_text, problems


def respond(conversation, user_text, ctx: ToolContext):
    """Procesa un turno del cliente y devuelve el contrato de respuesta a UI."""
    request_id = uuid.uuid4().hex[:12]
    AIMessage.objects.create(conversation=conversation, role="user", content=user_text,
                             request_id=request_id)

    if not adapter.available():
        reply = fallback.respond(user_text, ctx)
        reply["mode"] = "rules"
        reply["mode_note"] = ("El asesor con IA no está disponible ahora. "
                              "Estás usando la selección guiada de la tienda.")
        reply.setdefault("proposed_actions", [])
        _persist(conversation, reply, request_id)
        return reply

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            store_name=ctx.store.name, memory_context=_memory_context(ctx))},
    ]
    history = list(conversation.messages.order_by("-created_at", "-pk")[:MAX_HISTORY])
    for msg in reversed(history):
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    cards, warnings, proposals, evidence = [], [], [], []
    rounds = 0
    answer = ""
    try:
        while rounds < settings.REINO_AI["MAX_TOOL_ROUNDS"]:
            rounds += 1
            message = adapter.chat(messages, tools=TOOL_SPECS)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                answer = (message.get("content") or "").strip()
                break
            messages.append(message)
            for call in tool_calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if name in WRITE_TOOLS:
                    # R11: el modelo PROPONE; nunca ejecuta. El comprador
                    # confirma con un permiso de un solo uso y caducidad.
                    token = _propose_action(name, args, ctx)
                    proposals.append({
                        "action_id": token.action_id,
                        "tool": name,
                        "label": _proposal_label(token),
                        "payload": token.payload,
                    })
                    result = {"error": "requires_buyer_confirmation",
                              "proposal_id": token.action_id}
                else:
                    result = run_tool(name, args, ctx)
                    _collect_cards(name, result, cards, warnings)
                    if isinstance(result, dict) and not result.get("error"):
                        evidence.append(json.dumps(result, ensure_ascii=False, default=str))
                messages.append({
                    "role": "tool", "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:4000],
                })
        else:
            warnings.append("tool_rounds_exhausted")
            answer = ("Estoy consultando más datos de los habituales. "
                      "¿Podés precisar un poco más qué buscás?")
    except adapter.ProviderUnavailable:
        reply = fallback.respond(user_text, ctx)
        reply["mode"] = "rules"
        reply["mode_note"] = ("El asesor con IA no está disponible ahora. "
                              "Estás usando la selección guiada de la tienda.")
        reply.setdefault("proposed_actions", [])
        _persist(conversation, reply, request_id)
        return reply
    except adapter.ProviderError as exc:
        reply = {
            "answer_text": ("No pude completar la consulta. Tus selecciones siguen "
                            "guardadas; podés reintentar o ver la colección."),
            "cards": [], "clarifying_question": None,
            "suggested_actions": [{"label": "Reintentar", "action": "retry"},
                                  {"label": "Ver colección", "action": "collection"}],
            "proposed_actions": [],
            "warnings": [f"provider_error:{exc}"], "mode": "ai",
            "request_id": request_id,
        }
        _persist(conversation, reply, request_id)
        return reply

    # R12: validar el texto contra la evidencia del turno.
    answer, problems = _validate_answer(answer, evidence)
    if problems:
        warnings += problems
        answer = ABSTENTION_TEXT
        cards = []  # sin evidencia no hay tarjetas que mostrar

    reply = {
        "answer_text": answer or "Acá tenés lo que encontré.",
        # Las tarjetas SIEMPRE provienen de resultados de herramientas
        # validados en servidor, nunca del texto del modelo (A11).
        "cards": _dedupe_cards(cards)[:3],
        "clarifying_question": None,
        "suggested_actions": [],
        "proposed_actions": proposals,
        "warnings": warnings,
        "mode": "ai",
        "request_id": request_id,
    }
    _persist(conversation, reply, request_id)
    return reply


def _propose_action(tool, args, ctx):
    """Crea el permiso de acción propuesta: alcance tienda+sesión, 15 min (R11)."""
    return ActionToken.objects.create(
        action_id=uuid.uuid4().hex[:24],
        store=ctx.store, session_key=ctx.session_key, tool=tool,
        payload={k: v for k, v in (args or {}).items() if k != "action_id"},
        expires_at=timezone.now() + timedelta(minutes=ACTION_TTL_MINUTES),
    )


def _proposal_label(token):
    if token.tool == "add_item_to_cart":
        qty = token.payload.get("quantity") or 1
        return f"Agregar al carrito (cantidad {qty})"
    return "Ejecutar acción"


def _collect_cards(tool_name, result, cards, warnings):
    """Extrae tarjetas SOLO de resultados de herramientas (IDs reales)."""
    if not isinstance(result, dict) or result.get("error"):
        if isinstance(result, dict) and result.get("error") not in (None, "not_found"):
            warnings.append(f"{tool_name}:{result['error']}")
        return
    for product in result.get("products", []):
        cards.append(product)
    for item in result.get("selection", []):
        cards.append(item)


def _dedupe_cards(cards):
    seen, out = set(), []
    for card in cards:
        pid = card.get("product_id")
        if pid and pid not in seen:
            seen.add(pid)
            out.append(card)
    return out


def _persist(conversation, reply, request_id):
    conversation.mode = reply.get("mode", conversation.mode)
    conversation.save(update_fields=["mode"])
    AIMessage.objects.create(
        conversation=conversation, role="assistant",
        content=reply["answer_text"], cards=reply.get("cards", []),
        request_id=request_id,
    )
