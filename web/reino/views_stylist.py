"""S06 · Royal Stylist: conversación con productos.

- El perfil activo y la tienda siempre visibles.
- Las tarjetas usan IDs del catálogo de la tienda (render servidor).
- Ante fallo: mensaje honesto, selecciones conservadas, Reintentar/Colección.
- La conversación nunca bloquea el checkout.
"""

from django.http import JsonResponse
from django.shortcuts import redirect, render  # redirect: confirmación HTTP (N01)
from django.views.decorators.http import require_POST

from . import services_memory, tenancy
from .ai import adapter
from .ai.orchestrator import get_conversation, respond
from .ai.tools import ToolContext
from .views_storefront import _store_view

EXAMPLES = [
    "Un look para una celebración",
    "Ayudame con la talla",
    "Algo para el día a día",
]


def _ctx(request, store):
    session_key = request.session.session_key
    pid = tenancy.active_profile_id(request, store)
    profile = services_memory.get_profile(store, session_key, pid) if pid else None
    return ToolContext(store, session_key, profile)


@_store_view
def stylist(request, store):
    conversation = get_conversation(store, request.session.session_key)
    messages = conversation.messages.filter(role__in=("user", "assistant"))
    return render(request, "reino/stylist.html", {
        "conversation": conversation,
        "messages": messages,
        "examples": EXAMPLES,
        "ai_available": adapter.available(),
        "profile": _ctx(request, store).profile,
    })


@_store_view
@require_POST
def stylist_message(request, store):
    """Recibe un mensaje y devuelve la respuesta (HTML parcial o JSON)."""
    text = (request.POST.get("message") or "").strip()[:500]
    if not text:
        return JsonResponse({"error": "empty_message"}, status=400)
    conversation = get_conversation(store, request.session.session_key)
    ctx = _ctx(request, store)
    reply = respond(conversation, text, ctx)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "reino/_stylist_reply.html", {"reply": reply, "store": store})
    return render(request, "reino/stylist_reply_page.html", {"reply": reply, "store": store})


@_store_view
@require_POST
def stylist_confirm_action(request, store):
    """El comprador CONFIRMA una acción propuesta por el asesor (R11).

    El permiso (ActionToken) es de un solo uso, con alcance tienda+sesión y
    caducidad; reintentar el mismo action_id nunca duplica la escritura.
    """
    from .ai.tools import run_tool
    action_id = (request.POST.get("action_id") or "").strip()
    ctx = _ctx(request, store)
    result = run_tool("add_item_to_cart", {"action_id": action_id}, ctx)
    if result.get("error"):
        request.session["reino_cart_error"] = (
            "Esa propuesta venció o ya no es válida. Pedí una nueva al asesor."
        )
        return redirect("reino_stylist", slug=store.slug)
    request.session["reino_flash"] = "Agregado al carrito."
    return redirect("reino_cart", slug=store.slug)
