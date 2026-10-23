"""Herramientas autorizadas del asesor (implementación servidor, §11).

El servidor inyecta tienda, sesión y perfil permitido. Las herramientas de
lectura no reservan nada; la única escritura (add_item_to_cart) revalida y es
idempotente vía servicios de comercio. No existe herramienta para fijar
precios, confirmar cobros, reembolsar, enviar marketing ni SQL libre.
"""

from decimal import Decimal

from .. import services_commerce as commerce
from .. import services_fit, services_memory
from ..models import KnowledgeDocument, Order, Product, ShippingZone, Variant
from ..money import fmt
from ..services_recommend import normalize_intent, recommend


class ToolContext:
    """Contexto firmado/controlado por servidor para una conversación."""

    def __init__(self, store, session_key, profile=None, cart=None):
        self.store = store
        self.session_key = session_key
        self.profile = profile
        self.cart = cart


def _card(product, reasons=(), fit=None):
    image = product.media.first()
    return {
        "product_id": str(product.public_id),
        "slug": product.slug,
        "title": product.short_title,
        "price": fmt(product.base_price, product.store.currency),
        "image": image.path if image else "",
        "alt": image.alt if image else product.short_title,
        "reason_codes": list(reasons),
        "fit_state": fit["state"] if fit else None,
        "fit_label": fit["label"] if fit else None,
    }


def run_tool(name, args, ctx: ToolContext):
    """Despacha una llamada del modelo a la herramienta permitida."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": "tool_not_allowed"}
    try:
        return handler(args or {}, ctx)
    except Exception as exc:  # la herramienta falla en cerrado y con mensaje útil
        return {"error": "tool_error", "detail": str(exc)[:200]}


def _search_products(args, ctx):
    qs = Product.objects.filter(store=ctx.store, status=Product.Status.PUBLISHED)
    query = (args.get("query") or "").lower().strip()
    if query:
        qs = [p for p in qs if query in p.title.lower()
              or query in p.short_title.lower()
              or query in (p.description or "").lower()]
    if args.get("category"):
        qs = [p for p in qs if p.category == args["category"]]
    if args.get("occasion"):
        qs = [p for p in qs if args["occasion"] in (p.occasions or [])]
    if args.get("max_price"):
        qs = [p for p in qs if p.base_price <= Decimal(str(args["max_price"]))]
    return {"products": [_card(p) for p in list(qs)[:6]]}


def _get_product_details(args, ctx):
    out = []
    for pid in (args.get("product_ids") or [])[:6]:
        p = Product.objects.filter(store=ctx.store, public_id=pid,
                                   status=Product.Status.PUBLISHED).first()
        if p is None:
            continue  # IDs desconocidos no se hidratan (fail-closed)
        out.append({
            **_card(p),
            "description": p.description,
            "materials": p.materials or [],
            "variants": [
                {"variant_id": str(v.public_id), "sku": v.sku,
                 "option": v.option_label, "price": fmt(v.price, ctx.store.currency),
                 "available": v.stock > 0}
                for v in p.variants.filter(is_active=True)
            ],
        })
    return {"products": out}


def _check_inventory(args, ctx):
    v = Variant.objects.filter(public_id=args.get("variant_id"),
                               product__store=ctx.store).first()
    if v is None:
        return {"error": "unknown_variant"}
    qty = int(args.get("quantity") or 1)
    return {"variant_id": str(v.public_id), "sku": v.sku, "requested": qty,
            "available": v.stock >= qty, "stock": v.stock}


def _calculate_smart_fit(args, ctx):
    from decimal import Decimal as D

    p = Product.objects.filter(store=ctx.store, public_id=args.get("product_id"),
                               status=Product.Status.PUBLISHED).first()
    if p is None:
        return {"error": "unknown_product"}
    chest = D(str(args["chest_cm"])) if args.get("chest_cm") else None
    neck = D(str(args["neck_cm"])) if args.get("neck_cm") else None
    back = D(str(args["back_cm"])) if args.get("back_cm") else None
    if chest is None and ctx.profile is not None:
        m = services_memory.latest_measurement(ctx.profile)
        if m:
            chest, neck, back = m.chest_cm, m.neck_cm, m.back_cm
    return services_fit.evaluate(p, chest_cm=chest, neck_cm=neck, back_cm=back)


def _recommend_products(args, ctx):
    measurement = services_memory.latest_measurement(ctx.profile) if ctx.profile else None
    intent = normalize_intent(
        occasion=args.get("occasion", ""), style=args.get("style", ""),
        budget=args.get("budget"), budget_scope=args.get("budget_scope", "products"),
        profile=ctx.profile, needs_fit=ctx.store.category == "moda canina",
    )
    result = recommend(ctx.store, intent, measurement=measurement, kind="stylist")
    return {
        "selection": [
            {**_card(e["product"], e["reasons"]), "score": e["score"]}
            for e in result["selection"]
        ],
        "excluded": result["excluded"],
        "engine_version": result["engine_version"],
    }


def _get_store_policies(args, ctx):
    docs = KnowledgeDocument.objects.filter(
        store=ctx.store, topic=args.get("topic", ""), is_published=True,
        audience="customer",
    )
    return {"fragments": [
        {"title": d.title, "body": d.body, "version": d.version,
         "published_at": d.published_at.isoformat() if d.published_at else None}
        for d in docs[:5]
    ]}


def _get_shipping_options(args, ctx):
    zones = ShippingZone.objects.filter(store=ctx.store, is_active=True)
    return {"zones": [
        {"name": z.name, "mode": z.mode, "fee": fmt(z.fee, ctx.store.currency),
         "eta": z.eta_note or "Por confirmar"}
        for z in zones
    ]}


def _get_customer_preferences(args, ctx):
    if ctx.profile is None:
        return {"preferences": {}, "note": "sin perfil activo"}
    return {"preferences": services_memory.authorized_preferences(
        ctx.profile, ctx.store, ctx.session_key)}


def _add_item_to_cart(args, ctx):
    """Escritura autorizada: la instrucción del cliente llega inequívoca desde
    el orquestador (token de acción); el servidor revalida siempre."""
    v = Variant.objects.filter(public_id=args.get("variant_id"),
                               product__store=ctx.store, is_active=True).first()
    if v is None:
        return {"error": "unknown_variant"}
    cart = ctx.cart or commerce.get_open_cart(ctx.store, ctx.session_key, create=True)
    try:
        commerce.add_item(cart, v, int(args.get("quantity") or 1), recipient=ctx.profile)
    except (commerce.CartError, commerce.StockConflict) as exc:
        return {"error": "cart_rejected", "detail": str(exc)}
    summary = commerce.cart_summary(cart)
    return {"ok": True, "cart_units": sum(l["item"].quantity for l in summary["lines"]),
            "subtotal": fmt(summary["subtotal"], ctx.store.currency)}


def _get_cart(args, ctx):
    cart = ctx.cart or commerce.get_open_cart(ctx.store, ctx.session_key)
    if cart is None:
        return {"lines": [], "subtotal": fmt(0, ctx.store.currency)}
    summary = commerce.cart_summary(cart)
    return {
        "lines": [
            {"title": l["item"].variant.product.short_title,
             "option": l["item"].variant.option_label,
             "quantity": l["item"].quantity,
             "subtotal": fmt(l["subtotal"], ctx.store.currency)}
            for l in summary["lines"]
        ],
        "subtotal": fmt(summary["subtotal"], ctx.store.currency),
        "shipping": "por calcular",
    }


def _get_order_status(args, ctx):
    """Solo pedidos del comprador autenticado (su sesión), nunca por adivinar."""
    ref = (args.get("reference") or "").strip().upper()
    order = Order.objects.filter(store=ctx.store, reference=ref).first()
    if order is None or not order.cart or order.cart.session_key != ctx.session_key:
        return {"error": "not_found"}  # sin filtrar existencia de pedidos ajenos
    return {
        "reference": order.reference,
        "status": order.get_status_display(),
        "payment": order.get_payment_status_display(),
        "preparation": order.get_prep_status_display(),
        "delivery": order.get_delivery_status_display(),
        "total": fmt(order.total, order.currency),
    }


_HANDLERS = {
    "search_products": _search_products,
    "get_product_details": _get_product_details,
    "check_inventory": _check_inventory,
    "calculate_smart_fit": _calculate_smart_fit,
    "recommend_products": _recommend_products,
    "get_store_policies": _get_store_policies,
    "get_shipping_options": _get_shipping_options,
    "get_customer_preferences": _get_customer_preferences,
    "add_item_to_cart": _add_item_to_cart,
    "get_cart": _get_cart,
    "get_order_status": _get_order_status,
}
