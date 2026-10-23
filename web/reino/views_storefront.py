"""Storefront Reino Commerce (S01–S03, S05, S07–S09, S12).

Composición, copy, estados y comportamiento móvil según §6. Toda la lógica de
talla/precio/stock vive en servicios de servidor; las vistas traducen
solicitudes a servicios.
"""

import uuid

from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import services_commerce as commerce
from . import services_fit, services_memory, tenancy
from .models import (
    KnowledgeDocument, Order, Product, ShippingZone, Variant,
)
from .money import fmt


def _store_view(view_func):
    """Resuelve tienda y sesión; fail-closed sin tenant válido."""
    def wrapper(request, slug, *args, **kwargs):
        request.reino_store = tenancy.get_store(slug)
        tenancy.ensure_session(request)
        return view_func(request, request.reino_store, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _profile(request, store):
    pid = tenancy.active_profile_id(request, store)
    if not pid:
        return None
    return services_memory.get_profile(store, request.session.session_key, pid)


def _measurement(request, store, profile):
    """Medidas persistentes SOLO con consentimiento vigente (R07)."""
    if not profile:
        return None
    return services_memory.authorized_measurement(
        store, request.session.session_key, profile)


# ------------------------------------------------------------------- S01 ----

@_store_view
def store_home(request, store):
    """S01 · Inicio: entrar a una boutique.

    Módulos en orden §6: hero, claridad de compra, selección de la casa,
    LookLab, Smart Fit, editorial por ocasión, ayuda, cierre.
    """
    featured = list(
        Product.objects.filter(store=store, status=Product.Status.PUBLISHED)
        .prefetch_related("media", "variants")
        .order_by("-is_featured", "short_title")[:3]
    )
    products_exist = Product.objects.filter(store=store, status=Product.Status.PUBLISHED).exists()
    return render(request, "reino/store_home.html", {
        "featured": featured,
        "products_exist": products_exist,
        "profile": _profile(request, store),
    })


# ------------------------------------------------------------------- S02 ----

@_store_view
def collection(request, store):
    """S02 · Colección: descubrir con una intención.

    Texto simple => búsqueda lexical; filtros curados; el resultado y la URL
    conservan el estado; los filtros incompatibles devuelven cero (honesto).
    """
    q = request.GET.get("q", "").strip()[:200]
    category = request.GET.get("categoria", "").strip()
    occasion = request.GET.get("ocasion", "").strip()
    max_price = request.GET.get("max", "").strip()
    available_only = request.GET.get("disponible") == "1"
    sort = request.GET.get("orden", "relevancia")

    products = list(
        Product.objects.filter(store=store, status=Product.Status.PUBLISHED)
        .prefetch_related("media", "variants")
    )

    interpretation = []
    if q:
        ql = q.lower()
        products = [p for p in products if ql in p.title.lower()
                    or ql in p.short_title.lower()
                    or ql in (p.description or "").lower()
                    or any(ql in str(m).lower() for m in (p.materials or []))]
        interpretation.append(f"“{q}”")
    if category:
        products = [p for p in products if p.category == category]
        interpretation.append(category)
    if occasion:
        products = [p for p in products if occasion in (p.occasions or [])]
        interpretation.append(occasion)
    if max_price:
        try:
            cap = float(max_price)
            products = [p for p in products if float(p.base_price) <= cap]
            interpretation.append(f"hasta ${cap:,.0f}")
        except ValueError:
            pass
    if available_only:
        products = [p for p in products if any(v.stock > 0 for v in p.variants.filter(is_active=True))]
        interpretation.append("disponible")

    if sort == "precio-asc":
        products.sort(key=lambda p: p.base_price)
    elif sort == "precio-desc":
        products.sort(key=lambda p: -p.base_price)

    categories = sorted({p.category for p in Product.objects.filter(
        store=store, status=Product.Status.PUBLISHED)})
    occasions = sorted({o for p in Product.objects.filter(
        store=store, status=Product.Status.PUBLISHED) for o in (p.occasions or [])})

    profile = _profile(request, store)
    measurement = _measurement(request, store, profile)
    cards = []
    for p in products:
        fit = services_fit.evaluate_for_profile(p, measurement) if measurement and store.category == "moda canina" else None
        cards.append({"product": p, "fit": fit})

    return render(request, "reino/collection.html", {
        "cards": cards, "q": q, "interpretation": interpretation,
        "categories": categories, "occasions": occasions,
        "selected": {"categoria": category, "ocasion": occasion, "max": max_price,
                     "disponible": available_only, "orden": sort},
        "result_count": len(cards),
    })


# ------------------------------------------------------------------- S03 ----

@_store_view
def product_detail(request, store, product_slug):
    """S03 · Ficha: elegir con seguridad (galería, variantes, fit, acordeones)."""
    product = (
        Product.objects.filter(store=store, slug=product_slug, status=Product.Status.PUBLISHED)
        .prefetch_related("media", "variants", "fit_rules")
        .first()
    )
    if product is None:
        return render(request, "reino/product_detail.html", {"product": None}, status=404)

    profile = _profile(request, store)
    measurement = _measurement(request, store, profile)
    variants = list(product.variants.filter(is_active=True).order_by("pk"))
    fit = services_fit.evaluate_for_profile(product, measurement) if measurement else None

    variant_rows = []
    for v in variants:
        hint = None
        if fit and fit["candidates"] and any(
                services_fit.label_matches(c, v.option_label) for c in fit["candidates"]):
            hint = "sugerida"
        variant_rows.append({"variant": v, "fit_hint": hint, "available": v.stock > 0})

    # Complementos: máximo dos, solo con compatibilidad registrada.
    from .services_recommend import compose_bundle
    bundle, _ = compose_bundle(store, product, measurement=measurement)
    complements = [b["product"] for b in bundle if b["role"] == "complemento"][:2]

    # Datos estructurados Product/ofertas/variantes (descubrimiento, §8 [S02]).
    import json
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.title,
        "description": product.description or product.subtitle,
        "brand": {"@type": "Brand", "name": store.name},
        "offers": [
            {"@type": "Offer", "sku": v.sku, "name": v.option_label,
             "price": str(v.price), "priceCurrency": store.currency,
             "availability": "https://schema.org/InStock" if v.stock > 0
             else "https://schema.org/OutOfStock"}
            for v in variants
        ],
    }, ensure_ascii=False)

    return render(request, "reino/product_detail.html", {
        "product": product, "variant_rows": variant_rows, "fit": fit,
        "profile": profile, "complements": complements,
        "media": list(product.media.all()),
        "json_ld": json_ld,
        "has_quote_flow": bool(product.legacy_slug),  # pieza a medida: Smart Quote preservado
    })


# ------------------------------------------------------------------- S05 ----

@_store_view
def smart_fit(request, store):
    """S05 · Smart Fit: tres medidas, cuatro estados honestos, cm/in equivalentes."""
    profile = _profile(request, store)
    product = None
    if request.GET.get("producto"):
        product = Product.objects.filter(
            store=store, slug=request.GET["producto"], status=Product.Status.PUBLISHED
        ).first()

    result, errors, values = None, {}, {}
    # GET con ?producto= y medidas guardadas (autorizadas): evaluación directa.
    if request.method == "GET" and product and profile:
        latest = _measurement(request, store, profile)
        if latest:
            result = services_fit.evaluate_for_profile(product, latest)
    if request.method == "POST":
        unit = request.POST.get("unit", "cm")
        values = {k: request.POST.get(k, "").strip() for k in ("chest", "neck", "back")}
        values["unit"] = unit
        try:
            chest = services_fit.to_cm(values["chest"], unit) if values["chest"] else None
        except services_fit.InvalidMeasurement as exc:
            chest, errors["chest"] = None, str(exc)
        try:
            neck = services_fit.to_cm(values["neck"], unit) if values["neck"] else None
        except services_fit.InvalidMeasurement as exc:
            neck, errors["neck"] = None, str(exc)
        try:
            back = services_fit.to_cm(values["back"], unit) if values["back"] else None
        except services_fit.InvalidMeasurement as exc:
            back, errors["back"] = None, str(exc)

        if not errors and (chest or neck or back):
            remember = request.POST.get("remember") == "1"
            if remember and profile:
                # Guardar requiere consentimiento explícito y separado (R07).
                services_memory.grant_consent(
                    store, request.session.session_key,
                    services_memory.Consent.Purpose.MEASUREMENTS, profile)
                measurement = services_memory.save_measurement(
                    profile, chest_cm=chest, neck_cm=neck, back_cm=back,
                    original={**values}, source="smartfit",
                )
            else:
                # «Calcular sin guardar»: evaluación temporal, nada persiste.
                measurement = services_fit.SimpleMeasurement(chest, neck, back)
            if product:
                result = services_fit.evaluate_for_profile(product, measurement)
        elif not errors:
            errors["chest"] = "Ingresá al menos una medida para evaluar."

    products = Product.objects.filter(store=store, status=Product.Status.PUBLISHED)
    return render(request, "reino/smartfit.html", {
        "profile": profile, "product": product, "result": result, "errors": errors,
        "values": values, "products": products,
        "latest": _measurement(request, store, profile),
    })


# ------------------------------------------------------------------- S07 ----

@_store_view
def cart_view(request, store):
    """S07 · Carrito: confirmar la selección; envío por calcular."""
    cart = commerce.get_open_cart(store, request.session.session_key)
    summary = commerce.cart_summary(cart) if cart else None
    return render(request, "reino/cart.html", {
        "cart": cart, "summary": summary,
        "line_errors": request.session.pop("reino_cart_error", None),
    })


@_store_view
@require_POST
def cart_add(request, store):
    """Añade una variante válida; una inexistente nunca llega al carrito."""
    variant = Variant.objects.filter(
        public_id=request.POST.get("variant"), product__store=store, is_active=True
    ).select_related("product").first()
    if variant is None:
        request.session["reino_cart_error"] = "Esa variante ya no está disponible."
        return redirect("reino_cart", slug=store.slug)
    cart = commerce.get_open_cart(store, request.session.session_key, create=True)
    try:
        commerce.add_item(cart, variant, request.POST.get("quantity", 1),
                          recipient=_profile(request, store))
    except (commerce.CartError, commerce.StockConflict) as exc:
        request.session["reino_cart_error"] = str(exc)
        return redirect("reino_cart", slug=store.slug)
    return redirect("reino_cart", slug=store.slug)


@_store_view
@require_POST
def cart_update(request, store, item_id):
    cart = commerce.get_open_cart(store, request.session.session_key)
    if cart:
        try:
            commerce.update_item(cart, item_id, request.POST.get("quantity", 1))
        except (commerce.CartError, ValueError) as exc:
            request.session["reino_cart_error"] = str(exc)
    return redirect("reino_cart", slug=store.slug)


@_store_view
@require_POST
def cart_remove(request, store, item_id):
    cart = commerce.get_open_cart(store, request.session.session_key)
    if cart:
        commerce.remove_item(cart, item_id)
    return redirect("reino_cart", slug=store.slug)


# ------------------------------------------------------------------- S08 ----

@_store_view
def checkout(request, store):
    """S08 · Checkout: datos y opciones → revisión vigente → confirmar.

    Microcopy final honesto: «Crear pedido pendiente de pago» (flujo manual).
    La clave de intento es POR TIENDA (R01); el resumen aprobado queda ligado
    a su contenido (R02); modalidad/zona/tarifa se validan en servidor (R06).
    """
    session_key = request.session.session_key
    cart = commerce.get_open_cart(store, session_key)
    if cart is None:
        return redirect("reino_cart", slug=store.slug)

    idem_key = f"reino_idem_{store.slug}"  # un intento por tienda, jamás compartido (R01)
    zones = ShippingZone.objects.filter(store=store, is_active=True)
    errors = {}
    data = {}
    payment_method = "manual"

    if request.method == "POST":
        step = request.POST.get("step", "review")
        data = {k: request.POST.get(k, "").strip() for k in
                ("name", "email", "phone", "delivery_mode", "zone", "address", "city",
                 "payment_method")}
        payment_method = data["payment_method"] or "manual"
        idem = request.POST.get("idempotency_key") or uuid.uuid4().hex
        request.session.setdefault(idem_key, idem)

        if not data["name"]:
            errors["name"] = "Ingresá tu nombre."
        if "@" not in data["email"]:
            errors["email"] = "Ingresá un correo válido."
        # Zona validada en servidor: tienda + activa + modalidad coherente (R06).
        zone = None
        if data["delivery_mode"] == "local":
            zone = zones.filter(name=data["zone"], mode="local").first()
            if zone is None:
                errors["zone"] = "Elegí una zona de entrega válida."
            if not data["address"]:
                errors["address"] = "Ingresá la dirección de entrega."
        elif data["delivery_mode"] == "pickup":
            zone = None
        else:
            errors["delivery_mode"] = "Elegí una modalidad de entrega válida."
        if payment_method not in ("manual", "bitcoin"):
            errors["payment_method"] = "Elegí un método de pago habilitado."

        if not errors:
            try:
                session = commerce.prepare_checkout(
                    cart, payment_method,
                    delivery_mode=data["delivery_mode"] or "pickup",
                    zone=zone, idempotency_key=request.session[idem_key],
                )
            except commerce.StockConflict as exc:
                request.session["reino_cart_error"] = str(exc)
                return redirect("reino_cart", slug=store.slug)
            except commerce.CartError as exc:
                errors["zone"] = str(exc)
            else:
                reviewed_id = request.POST.get("session_id", "")
                if step == "confirm" and reviewed_id and str(session.public_id) != reviewed_id:
                    # El resumen cambió desde la última revisión: exigir una
                    # revisión nueva del contenido vigente (R02), nunca
                    # confirmar un resumen obsoleto.
                    step = "review"
                if step == "review":
                    return render(request, "reino/checkout_review.html", {
                        "cart": cart, "summary": commerce.cart_summary(cart, payment_method),
                        "data": data, "session": session, "store": store,
                        "total": _review_total(session),
                        "idem": request.session[idem_key],
                    })
                try:
                    order = commerce.confirm_checkout(
                        session,
                        {"name": data["name"], "email": data["email"],
                         "phone": data["phone"], "address": data["address"],
                         "city": data["city"]},
                        idempotency_key=session.idempotency_key,
                    )
                except (commerce.CartError, commerce.StockConflict) as exc:
                    errors["confirm"] = str(exc)
                else:
                    request.session.pop(idem_key, None)
                    return redirect("reino_order_guest", slug=store.slug,
                                    public_id=order.public_id, token=order.access_token)

    summary = commerce.cart_summary(cart, payment_method)
    if summary["is_empty"]:
        return redirect("reino_cart", slug=store.slug)
    return render(request, "reino/checkout.html", {
        "cart": cart, "summary": summary, "zones": zones, "errors": errors,
        "data": data, "idem": request.session.get(idem_key, uuid.uuid4().hex),
    })


def _review_total(session):
    from decimal import Decimal
    s = session.summary
    subtotal = Decimal(s["subtotal"])
    discount = Decimal(s.get("discount", "0"))
    shipping = Decimal(s["shipping"]) if s.get("shipping") is not None else None
    return {"subtotal": subtotal, "discount": discount, "shipping": shipping,
            "total": subtotal - discount + (shipping or 0)}


# ------------------------------------------------------------------- S09 ----

@_store_view
def order_detail(request, store, public_id, token=None):
    """S09 · Confirmación y seguimiento. Acceso protegido por token de alta
    entropía (invitados) o por sesión propietaria."""
    order = Order.objects.filter(store=store, public_id=public_id).prefetch_related(
        "items", "events").first()
    if order is None:
        return render(request, "reino/order.html", {"order": None}, status=404)
    owner_session = order.cart and order.cart.session_key == request.session.session_key
    if not owner_session and str(order.access_token) != str(token):
        # Un número adivinado no autentica: sin datos privados (A25).
        return render(request, "reino/order.html", {"order": None}, status=404)
    return render(request, "reino/order.html", {
        "order": order,
        "payment_label": dict(Order.PaymentStatus.choices).get(order.payment_status),
    })


# ------------------------------------------------------------------- S12 ----

@_store_view
def help_center(request, store):
    """S12 · Ayuda: respuestas publicadas y vigentes por la tienda (RAG P0)."""
    topic = request.GET.get("tema", "")
    docs = KnowledgeDocument.objects.filter(store=store, is_published=True,
                                            audience="customer")
    if topic:
        docs = docs.filter(topic=topic)
    topics = sorted(set(KnowledgeDocument.objects.filter(
        store=store, is_published=True, audience="customer"
    ).values_list("topic", flat=True)))
    return render(request, "reino/help.html", {
        "docs": docs, "topics": topics, "selected_topic": topic,
    })
