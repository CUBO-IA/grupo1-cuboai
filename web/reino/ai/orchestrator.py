"""Orquestador del asesor (§10, pasos 1–8).

1. Contexto firmado por servidor (tienda, sesión, perfil permitido).
2. Recupera solo memoria pertinente y autorizada.
3. El modelo interpreta intención y decide herramientas (máx. 4 rondas).
4. Herramientas devuelven datos reales del catálogo/guía.
5. Filtrado/puntuación en backend (recommend).
6. El modelo redacta con esos resultados.
7. VALIDACIÓN: se rechazan IDs desconocidos, precios inventados o
   afirmaciones sin soporte; las tarjetas se construyen en servidor.
8. Acciones con clave idempotente y confirmación real.

Modo degradado: si el proveedor no está disponible, responde el recomendador
basado en reglas y se ETIQUETA el modo disponible (nunca se simula IA).
"""

import json
import uuid

from django.conf import settings

from .. import services_memory
from ..models import AIConversation, AIMessage
from . import adapter, fallback
from .schemas import SYSTEM_PROMPT, TOOL_SPECS
from .tools import ToolContext, run_tool

MAX_HISTORY = 12  # no reenviar todo el historial en cada turno


def _memory_context(ctx):
    """Solo campos consentidos y pertinentes (capa estructurada, §12)."""
    if ctx.profile is None:
        return ""
    parts = [f"\nPerfil activo autorizado: «{ctx.profile.alias}» (elegido por el cliente)."]
    m = services_memory.latest_measurement(ctx.profile)
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


def respond(conversation, user_text, ctx: ToolContext):
    """Procesa un turno del cliente y devuelve el contrato de respuesta a UI."""
    request_id = uuid.uuid4().hex[:12]
    AIMessage.objects.create(conversation=conversation, role="user", content=user_text,
                             request_id=request_id)

    if not adapter.available():
        reply = fallback.respond(user_text, ctx)
        reply["mode"] = "rules"
        reply["mode_note"] = ("El asesor con IA está pendiente de conexión; estás usando "
                              "la selección por reglas de la tienda.")
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

    cards, warnings, actions = [], [], []
    rounds = 0
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
                # Escrituras: solo la instrucción inequívoca del cliente llega
                # hasta aquí; la herramienta revalida en servidor.
                result = run_tool(name, args, ctx)
                _collect_cards(name, result, cards, warnings)
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
        reply["mode_note"] = ("La IA no está disponible en este momento; estás usando "
                              "la selección por reglas. Tus selecciones siguen guardadas.")
        _persist(conversation, reply, request_id)
        return reply
    except adapter.ProviderError as exc:
        reply = {
            "answer_text": ("No pude completar la consulta. Tus selecciones siguen "
                            "guardadas; podés reintentar o ver la colección."),
            "cards": [], "clarifying_question": None,
            "suggested_actions": [{"label": "Reintentar", "action": "retry"},
                                  {"label": "Ver colección", "action": "collection"}],
            "warnings": [f"provider_error:{exc}"], "mode": "ai",
            "request_id": request_id,
        }
        _persist(conversation, reply, request_id)
        return reply

    reply = {
        "answer_text": answer or "Acá tenés lo que encontré.",
        # Las tarjetas SIEMPRE provienen de resultados de herramientas
        # validados en servidor, nunca del texto del modelo (A11).
        "cards": _dedupe_cards(cards)[:3],
        "clarifying_question": None,
        "suggested_actions": actions,
        "warnings": warnings,
        "mode": "ai",
        "request_id": request_id,
    }
    _persist(conversation, reply, request_id)
    return reply


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
