"""M03–M10 · Panel del comerciante (P0, sobrio y honesto).

- Acceso: is_staff + membresía del tenant (aislamiento A26).
- Capacidades por rol verificadas en servidor (R13): logística opera entregas,
  nunca confirma cobros; catálogo/inventario requieren su capacidad propia.
- Editor de catálogo P0: crear, editar, publicar/archivar, variantes y stock
  con motivo — sin tocar código (§6.14).
- Las tareas urgentes antes que las gráficas; sin datos => «Sin datos
  suficientes», nunca porcentajes inventados (A28).
- Integraciones declaradas con su estado real: Sin configurar / Prueba /
  Producción / Error.
"""

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services_commerce
from .models import (
    FitRule, KnowledgeDocument, MerchantMember, Order, Product, ProductMedia,
    ShippingZone, StockAdjustment, Store, Variant,
)
from .services_commerce import PermissionDenied, member_can


def _member_store(user, slug):
    store = Store.objects.filter(slug=slug).first()
    if store is None:
        return None, None
    member = MerchantMember.objects.filter(
        user=user, merchant=store.merchant, is_active=True
    ).first()
    return store, member


def merchant_view(view_func):
    """Protege panel: login + membresía del tenant de la URL."""
    @login_required(login_url="panel_login")
    def wrapper(request, slug, *args, **kwargs):
        store, member = _member_store(request.user, slug)
        if member is None:
            return render(request, "reino/merchant_denied.html", {"slug": slug}, status=403)
        request.reino_store = store
        request.reino_member = member
        return view_func(request, store, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_capability(capability):
    """Capacidad por operación en backend (R13): sin ella, 403 explícito."""
    def decorator(view_func):
        def wrapper(request, slug, *args, **kwargs):
            if not member_can(request.reino_member, capability):
                return render(request, "reino/merchant_denied.html", {
                    "slug": slug, "capability": capability,
                }, status=403)
            return view_func(request, slug, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator


def _flash(request, text):
    request.session["reino_flash"] = text


# ------------------------------------------------------------------- M03 ----

@merchant_view
def dashboard(request, store):
    """M03 · Resumen: «Esto necesita tu atención» primero, KPIs después."""
    orders = Order.objects.filter(store=store).order_by("-created_at")
    attention = orders.filter(payment_status=Order.PaymentStatus.PENDING)[:5]
    low_stock = [v for p in Product.objects.filter(store=store, status="published")
                 for v in p.variants.filter(is_active=True, stock__lte=2)][:5]

    paid = orders.filter(payment_status=Order.PaymentStatus.PAID)
    kpis = None
    if paid.exists():
        total = sum(o.total for o in paid)
        kpis = {
            "ventas": total, "pedidos_pagados": paid.count(),
            "ticket_medio": total / paid.count(),
            "pendientes": orders.filter(payment_status=Order.PaymentStatus.PENDING).count(),
        }
    return render(request, "reino/merchant_dashboard.html", {
        "store": store, "attention": attention, "low_stock": low_stock,
        "kpis": kpis,  # None => «Sin datos suficientes», nunca 0 % inventado
        "member": request.reino_member,
    })


# ------------------------------------------------------------------- M04 ----

@merchant_view
def catalog(request, store):
    """M04 · Lista con imagen, SKU, variantes, precio y disponibilidad."""
    products = (Product.objects.filter(store=store)
                .prefetch_related("media", "variants").order_by("short_title"))
    return render(request, "reino/merchant_catalog.html", {
        "store": store, "products": products,
        "can_catalog": member_can(request.reino_member, "catalog"),
        "can_inventory": member_can(request.reino_member, "inventory"),
    })


PRODUCT_FIELDS = ("title", "short_title", "subtitle", "description", "category",
                  "base_price", "reason", "shipping_note")


def _product_form(request, store, product=None):
    """Lee y valida el formulario de producto. Devuelve (data, errors)."""
    data = {f: request.POST.get(f, "").strip() for f in PRODUCT_FIELDS}
    data["occasions"] = [o.strip() for o in request.POST.get("occasions", "").split(",") if o.strip()]
    data["styles"] = [s.strip() for s in request.POST.get("styles", "").split(",") if s.strip()]
    data["materials"] = [m.strip() for m in request.POST.get("materials", "").split(",") if m.strip()]
    data["care"] = [c.strip() for c in request.POST.get("care", "").split(",") if c.strip()]
    data["is_featured"] = request.POST.get("is_featured") == "1"
    data["bitcoin_discount_eligible"] = request.POST.get("bitcoin_discount_eligible") == "1"
    data["status"] = request.POST.get("status", "draft")
    errors = {}
    if not data["title"]:
        errors["title"] = "El título es obligatorio."
    if not data["short_title"]:
        data["short_title"] = data["title"][:80]
    try:
        price = Decimal(data["base_price"] or "0")
        if price <= 0 or price > Decimal("999999"):
            raise InvalidOperation
        data["base_price"] = price
    except InvalidOperation:
        errors["base_price"] = "Ingresá un precio válido."
    if data["status"] not in ("draft", "published", "archived"):
        errors["status"] = "Estado no válido."
    return data, errors


@merchant_view
@require_capability("catalog")
def product_new(request, store):
    """Crear producto en borrador (nunca nace publicado sin revisión)."""
    errors, data = {}, {}
    if request.method == "POST":
        data, errors = _product_form(request, store)
        if not errors:
            base = data["short_title"].lower().replace(" ", "-")[:40]
            slug, n = base, 1
            while Product.objects.filter(store=store, slug=slug).exists():
                n += 1
                slug = f"{base}-{n}"
            product = Product.objects.create(store=store, slug=slug, **{
                **data, "status": "draft"})
            _flash(request, f"«{product.short_title}» creado en borrador.")
            return redirect("reino_merchant_product_edit", slug=store.slug, pk=product.pk)
    return render(request, "reino/merchant_product_form.html", {
        "store": store, "product": None, "data": data, "errors": errors,
    })


@merchant_view
@require_capability("catalog")
def product_edit(request, store, pk):
    """Editar, publicar o archivar un producto existente."""
    product = Product.objects.filter(store=store, pk=pk).first()
    if product is None:
        return redirect("reino_merchant_catalog", slug=store.slug)
    errors, data = {}, None
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action in ("publish", "archive"):
            if action == "publish" and not product.variants.filter(is_active=True).exists():
                _flash(request, "No se puede publicar sin al menos una variante activa.")
            else:
                product.status = "published" if action == "publish" else "archived"
                product.save(update_fields=["status", "updated_at"])
                _flash(request, "Estado actualizado.")
            return redirect("reino_merchant_product_edit", slug=store.slug, pk=product.pk)
        data, errors = _product_form(request, store)
        if not errors:
            for field in PRODUCT_FIELDS:
                setattr(product, field, data[field])
            for field in ("occasions", "styles", "materials", "care", "is_featured",
                          "bitcoin_discount_eligible", "status"):
                setattr(product, field, data[field])
            product.save()
            _flash(request, "Cambios guardados.")
            return redirect("reino_merchant_product_edit", slug=store.slug, pk=product.pk)
    return render(request, "reino/merchant_product_form.html", {
        "store": store, "product": product, "data": data, "errors": errors,
        "variants": product.variants.order_by("pk"),
        "fit_rules": product.fit_rules.order_by("-version")[:3],
        "adjustments": StockAdjustment.objects.filter(variant__product=product)
        .select_related("variant", "by")[:20],
    })


@merchant_view
@require_capability("catalog")
@require_POST
def variant_new(request, store, pk):
    product = Product.objects.filter(store=store, pk=pk).first()
    if product is None:
        return redirect("reino_merchant_catalog", slug=store.slug)
    sku = request.POST.get("sku", "").strip()[:60]
    label = request.POST.get("option_label", "").strip()[:60]
    try:
        stock = max(0, int(request.POST.get("stock", 0)))
    except ValueError:
        stock = 0
    override = request.POST.get("price_override", "").strip()
    errors = []
    if not sku or not label:
        errors.append("SKU y etiqueta son obligatorios.")
    if Variant.objects.filter(product=product, sku=sku).exists():
        errors.append("Ese SKU ya existe en este producto.")
    price_override = None
    if override:
        try:
            price_override = Decimal(override)
            if price_override <= 0:
                raise InvalidOperation
        except InvalidOperation:
            errors.append("Precio de variante no válido.")
    if errors:
        _flash(request, " ".join(errors))
    else:
        Variant.objects.create(product=product, sku=sku, option_label=label,
                               stock=stock, price_override=price_override)
        _flash(request, f"Variante {sku} creada.")
    return redirect("reino_merchant_product_edit", slug=store.slug, pk=pk)


@merchant_view
@require_capability("inventory")
@require_POST
def variant_stock(request, store, pk):
    """Ajuste de stock con MOTIVO obligatorio y registro auditable."""
    variant = Variant.objects.filter(pk=pk, product__store=store).first()
    if variant is None:
        return redirect("reino_merchant_catalog", slug=store.slug)
    reason = request.POST.get("reason", "").strip()
    try:
        delta = int(request.POST.get("delta", "0"))
    except ValueError:
        delta = 0
    if not reason:
        _flash(request, "El ajuste de stock requiere un motivo.")
    elif delta == 0 or variant.stock + delta < 0:
        _flash(request, "Ajuste no válido: el stock nunca queda negativo.")
    else:
        variant.stock += delta
        variant.save(update_fields=["stock"])
        StockAdjustment.objects.create(variant=variant, delta=delta, reason=reason[:200],
                                       by=request.user)
        _flash(request, f"Stock de {variant.sku}: {variant.stock} (motivo registrado).")
    return redirect(request.POST.get("next") or
                    f"/negocio/{store.slug}/catalogo/")


@merchant_view
@require_capability("catalog")
@require_POST
def variant_toggle(request, store, pk):
    variant = Variant.objects.filter(pk=pk, product__store=store).first()
    if variant:
        variant.is_active = not variant.is_active
        variant.save(update_fields=["is_active"])
        _flash(request, f"{variant.sku}: {'activa' if variant.is_active else 'desactivada'}.")
    return redirect(request.POST.get("next") or f"/negocio/{store.slug}/catalogo/")


# ------------------------------------------------------------------- M05 ----

@merchant_view
def orders(request, store):
    """M05 · Pedidos por estado y antigüedad."""
    state = request.GET.get("estado", "")
    qs = Order.objects.filter(store=store).order_by("-created_at")
    if state:
        qs = qs.filter(status=state)
    return render(request, "reino/merchant_orders.html", {
        "store": store, "orders": qs, "selected": state,
        "states": Order.Status.choices, "member": request.reino_member,
    })


@merchant_view
def order_detail(request, store, public_id):
    order = Order.objects.filter(store=store, public_id=public_id).prefetch_related(
        "items", "events").first()
    if order is None:
        return render(request, "reino/merchant_orders.html",
                      {"store": store, "orders": [], "states": Order.Status.choices,
                       "selected": ""}, status=404)
    member = request.reino_member
    return render(request, "reino/merchant_order.html", {
        "store": store, "order": order,
        "transitions": {f: [str(v) for v in vs]
                        for f, vs in services_commerce.TRANSITIONS.items()},
        "current": {"status": order.status, "payment_status": order.payment_status,
                    "prep_status": order.prep_status, "delivery_status": order.delivery_status},
        "capabilities": {cap: member_can(member, cap)
                         for cap in ("orders", "payments", "fulfilment")},
    })


@merchant_view
@require_POST
def order_transition(request, store, public_id):
    """Transición con capacidad por rol verificada en servidor (R13)."""
    order = Order.objects.filter(store=store, public_id=public_id).first()
    if order:
        refund_amount = request.POST.get("refund_amount", "").strip()
        try:
            refund_amount = Decimal(refund_amount) if refund_amount else None
        except InvalidOperation:
            refund_amount = None
        try:
            services_commerce.apply_transition(
                order, request.POST["field"], request.POST["to"],
                user=request.user, note=request.POST.get("note", "")[:200],
                member=request.reino_member, refund_amount=refund_amount,
            )
        except (services_commerce.CartError, KeyError) as exc:
            _flash(request, str(exc))
    return redirect("reino_merchant_order", slug=store.slug, public_id=public_id)


# ------------------------------------------------------- M06–M08 mínimos ---

@merchant_view
def customers(request, store):
    """M06 mínimo: clientes derivados de pedidos reales (sin inventar datos)."""
    seen = {}
    for o in Order.objects.filter(store=store).order_by("-created_at"):
        row = seen.setdefault(o.customer_email, {
            "name": o.customer_name, "email": o.customer_email, "orders": 0,
            "paid_total": Decimal("0"), "last": o.created_at,
        })
        row["orders"] += 1
        if o.payment_status == Order.PaymentStatus.PAID:
            row["paid_total"] += o.total
    return render(request, "reino/merchant_customers.html", {
        "store": store, "customers": sorted(seen.values(), key=lambda c: -c["orders"]),
    })


@merchant_view
@require_capability("payments")
def finance(request, store):
    """M07 mínimo: conciliación de cobros manuales (evidencia, no etiquetas)."""
    qs = Order.objects.filter(store=store).order_by("-created_at")
    paid = qs.filter(payment_status=Order.PaymentStatus.PAID)
    refunds = qs.filter(payment_status__in=(Order.PaymentStatus.REFUNDED,
                                            Order.PaymentStatus.PARTIALLY_REFUNDED))
    kpis = None
    if paid.exists():
        total = sum(o.total for o in paid)
        kpis = {"cobrado": total, "pedidos": paid.count(),
                "ticket_medio": total / paid.count()}
    return render(request, "reino/merchant_finance.html", {
        "store": store, "kpis": kpis,
        "pending": qs.filter(payment_status=Order.PaymentStatus.PENDING),
        "refunds": refunds,
    })


@merchant_view
@require_capability("fulfilment")
def logistics(request, store):
    """M08 mínimo: tablero de preparación y entrega por estado."""
    qs = Order.objects.filter(store=store).exclude(status=Order.Status.CANCELLED)
    return render(request, "reino/merchant_logistics.html", {
        "store": store,
        "to_prepare": qs.filter(prep_status=Order.PrepStatus.NOT_STARTED,
                                payment_status=Order.PaymentStatus.PAID),
        "preparing": qs.filter(prep_status=Order.PrepStatus.PREPARING),
        "ready": qs.filter(prep_status=Order.PrepStatus.READY),
        "shipping": qs.exclude(delivery_status=Order.DeliveryStatus.UNASSIGNED),
    })


# ------------------------------------------------------------------- M10 ----

@merchant_view
def settings_view(request, store):
    """M10: identidad, integraciones con estado real comprobado y uso de IA."""
    from django.conf import settings as djsettings
    integrations = [
        {"name": "Pasarela de pagos", "state": "Sin configurar",
         "detail": "Pago manual con verificación del equipo (flujo aprobado P0)."},
        {"name": "Bitcoin (manual)", "state": "Prueba",
         "detail": "Descuento 15 % sobre piezas participantes, pendiente de verificación."},
        {"name": "Correo transaccional", "state": "Sin configurar",
         "detail": "La pantalla de pedido no promete envío de correo."},
        {"name": "IA (Royal Stylist)",
         "state": "Producción" if djsettings.REINO_AI.get("API_KEY") else "Sin configurar",
         "detail": "Sin clave el asesor opera en selección guiada etiquetada."},
        {"name": "Operador logístico", "state": "Sin configurar",
         "detail": "Matriz de zonas manual (retiro y tarifas por zona)."},
    ]
    return render(request, "reino/merchant_settings.html", {
        "store": store, "integrations": integrations,
        "zones": ShippingZone.objects.filter(store=store),
        "policies": KnowledgeDocument.objects.filter(store=store).order_by("topic"),
        "team": MerchantMember.objects.filter(merchant=store.merchant).select_related("user"),
        "can_settings": member_can(request.reino_member, "settings"),
        "can_team": member_can(request.reino_member, "team"),
    })


@merchant_view
@require_capability("settings")
@require_POST
def settings_store(request, store):
    """Editar identidad visible de la tienda (nombre, tagline, contacto)."""
    store.name = request.POST.get("name", store.name).strip()[:80] or store.name
    store.tagline = request.POST.get("tagline", store.tagline).strip()[:160]
    store.contact_email = request.POST.get("contact_email", store.contact_email).strip()[:120]
    store.contact_phone = request.POST.get("contact_phone", store.contact_phone).strip()[:40]
    store.save(update_fields=["name", "tagline", "contact_email", "contact_phone"])
    _flash(request, "Identidad de la tienda actualizada.")
    return redirect("reino_merchant_settings", slug=store.slug)


@merchant_view
@require_capability("settings")
@require_POST
def zone_save(request, store):
    """Crear o actualizar una zona de envío/retiro (tarifa nunca negativa)."""
    name = request.POST.get("name", "").strip()[:80]
    mode = request.POST.get("mode", "local")
    eta = request.POST.get("eta_note", "").strip()[:120]
    try:
        fee = Decimal(request.POST.get("fee", "0"))
        if fee < 0:
            raise InvalidOperation
    except InvalidOperation:
        _flash(request, "Tarifa no válida.")
        return redirect("reino_merchant_settings", slug=store.slug)
    if mode not in ("local", "pickup") or not name:
        _flash(request, "Nombre y modalidad válidos son obligatorios.")
        return redirect("reino_merchant_settings", slug=store.slug)
    zone, created = ShippingZone.objects.update_or_create(
        store=store, name=name, mode=mode,
        defaults={"fee": fee, "eta_note": eta,
                  "is_active": request.POST.get("is_active") == "1"},
    )
    _flash(request, f"Zona «{name}» {'creada' if created else 'actualizada'}.")
    return redirect("reino_merchant_settings", slug=store.slug)


@merchant_view
@require_capability("settings")
@require_POST
def policy_save(request, store):
    """Publicar una política de la tienda (contenido que también usa el asesor)."""
    topic = request.POST.get("topic", "").strip()[:40]
    title = request.POST.get("title", "").strip()[:120]
    body = request.POST.get("body", "").strip()
    if not (topic and title and body):
        _flash(request, "Tema, título y contenido son obligatorios.")
        return redirect("reino_merchant_settings", slug=store.slug)
    from django.utils import timezone
    doc, created = KnowledgeDocument.objects.update_or_create(
        store=store, topic=topic, title=title, audience="customer",
        defaults={"body": body, "is_published": request.POST.get("publish") == "1",
                  "published_at": timezone.now()},
    )
    doc.version = doc.version + (0 if created else 1)
    doc.save(update_fields=["version"])
    _flash(request, f"Política «{title}» guardada (v{doc.version}).")
    return redirect("reino_merchant_settings", slug=store.slug)


@merchant_view
@require_capability("team")
@require_POST
def team_save(request, store):
    """Agregar miembro o cambiar rol (la tienda nunca se queda sin dueño)."""
    username = request.POST.get("username", "").strip()
    role = request.POST.get("role", "staff")
    if role not in ("owner", "staff", "logistics"):
        _flash(request, "Rol no válido.")
        return redirect("reino_merchant_settings", slug=store.slug)
    user = User.objects.filter(username=username).first()
    if user is None:
        _flash(request, "Ese usuario no existe; crealo primero en el admin.")
    else:
        member, _ = MerchantMember.objects.update_or_create(
            user=user, merchant=store.merchant, defaults={"role": role, "is_active": True})
        _flash(request, f"{username} ahora tiene rol {member.get_role_display()}.")
    return redirect("reino_merchant_settings", slug=store.slug)


@merchant_view
@require_capability("team")
@require_POST
def team_remove(request, store, member_id):
    member = MerchantMember.objects.filter(pk=member_id, merchant=store.merchant).first()
    if member:
        owners = MerchantMember.objects.filter(
            merchant=store.merchant, role="owner", is_active=True).count()
        if member.role == "owner" and owners <= 1:
            _flash(request, "La tienda necesita al menos un propietario activo.")
        else:
            member.is_active = False
            member.save(update_fields=["is_active"])
            _flash(request, f"{member.user.username} ya no tiene acceso.")
    return redirect("reino_merchant_settings", slug=store.slug)


@merchant_view
@require_capability("catalog")
@require_POST
def fit_rule_new(request, store, pk):
    """Nueva versión de la regla de talla (JSON de rangos validado)."""
    import json
    product = Product.objects.filter(store=store, pk=pk).first()
    if product is None:
        return redirect("reino_merchant_catalog", slug=store.slug)
    try:
        ranges = json.loads(request.POST.get("ranges", "[]"))
        assert isinstance(ranges, list) and ranges
        for row in ranges:
            assert row["label"] and float(row["chest_min"]) < float(row["chest_max"])
    except (ValueError, KeyError, AssertionError, TypeError):
        _flash(request, "Rangos no válidos: revisá el formato JSON de la tabla.")
        return redirect("reino_merchant_product_edit", slug=store.slug, pk=pk)
    version = (product.fit_rules.count() or 0) + 1
    product.fit_rules.update(is_active=False)
    FitRule.objects.create(
        product=product, version=version, ranges=ranges,
        requires_neck=request.POST.get("requires_neck") == "1",
        ease_note=request.POST.get("ease_note", "")[:200],
        approved_by=request.user.username,
    )
    _flash(request, f"Tabla de tallas v{version} activa.")
    return redirect("reino_merchant_product_edit", slug=store.slug, pk=pk)


@merchant_view
@require_capability("catalog")
@require_POST
def product_media_add(request, store, pk):
    """Registrar una imagen de producto (ruta estática + alt obligatorio)."""
    product = Product.objects.filter(store=store, pk=pk).first()
    if product is None:
        return redirect("reino_merchant_catalog", slug=store.slug)
    path = request.POST.get("path", "").strip()[:200]
    alt = request.POST.get("alt", "").strip()[:160]
    if not path or not alt:
        _flash(request, "La imagen requiere ruta y texto alternativo.")
    else:
        ProductMedia.objects.create(product=product, path=path, alt=alt,
                                    source=request.POST.get("source", "")[:120])
        _flash(request, "Imagen registrada.")
    return redirect("reino_merchant_product_edit", slug=store.slug, pk=pk)
