import os

from django.conf import settings


def asset_version(request):
    """Version del CSS/JS (fecha del archivo) para que el navegador no use una copia vieja."""
    path = os.path.join(settings.BASE_DIR, "static", "tienda", "css", "style.css")
    try:
        return {"asset_version": int(os.path.getmtime(path))}
    except OSError:
        return {"asset_version": 0}


def cart_summary(request):
    """Número de unidades en el carrito de la sesión (para la cabecera)."""
    from . import services

    session = getattr(request, "session", None)
    cart_id = session.get("cart") if session is not None else None
    units = 0
    if cart_id:
        try:
            cart = services.get_open_cart(cart_id)
        except Exception:
            cart = None
        if cart is not None:
            units = sum(q.quantity for q in services.cart_lines(cart))
    flash = session.pop("flash", "") if session is not None else ""
    return {"cart_units": units, "flash": flash}
