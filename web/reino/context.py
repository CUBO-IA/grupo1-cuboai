"""Contexto global de templates reino: tienda activa, perfil activo y carrito."""

from . import services_memory, tenancy
from .models import RecipientProfile


def reino_context(request):
    ctx = {"reino_store": None, "reino_profile": None, "reino_cart_units": 0,
           "reino_profiles": [], "reino_flash": request.session.pop("reino_flash", None)}
    store = getattr(request, "reino_store", None)
    if store is None:
        return ctx
    session_key = tenancy.ensure_session(request)
    ctx["reino_store"] = store
    ctx["reino_profiles"] = services_memory.list_profiles(store, session_key)
    profile_id = tenancy.active_profile_id(request, store)
    if profile_id:
        ctx["reino_profile"] = RecipientProfile.objects.filter(
            store=store, session_key=session_key, public_id=profile_id
        ).first()
    from .services_commerce import get_open_cart
    cart = get_open_cart(store, session_key)
    if cart:
        ctx["reino_cart_units"] = sum(i.quantity for i in cart.items.all())
    return ctx
