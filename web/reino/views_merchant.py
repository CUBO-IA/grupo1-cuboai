"""M03–M10 · Panel del comerciante (P0 mínimo, sobrio y honesto).

- Acceso: is_staff + membresía del tenant (aislamiento A26).
- Las tareas urgentes antes que las gráficas; sin datos => «Sin datos
  suficientes», nunca porcentajes inventados (A28).
- Integraciones declaradas con su estado real: Sin configurar / Prueba /
  Producción / Error.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services_commerce
from .models import MerchantMember, Order, Product, Store


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
        return view_func(request, store, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


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
    })


@merchant_view
def catalog(request, store):
    """M04 mínimo: lista con imagen, SKU, variantes, precio y disponibilidad."""
    products = (Product.objects.filter(store=store)
                .prefetch_related("media", "variants").order_by("short_title"))
    return render(request, "reino/merchant_catalog.html", {"store": store, "products": products})


@merchant_view
def orders(request, store):
    """M05 · Pedidos por estado y antigüedad."""
    state = request.GET.get("estado", "")
    qs = Order.objects.filter(store=store).order_by("-created_at")
    if state:
        qs = qs.filter(status=state)
    return render(request, "reino/merchant_orders.html", {
        "store": store, "orders": qs, "selected": state,
        "states": Order.Status.choices,
    })


@merchant_view
def order_detail(request, store, public_id):
    order = Order.objects.filter(store=store, public_id=public_id).prefetch_related(
        "items", "events").first()
    if order is None:
        return render(request, "reino/merchant_orders.html",
                      {"store": store, "orders": [], "states": Order.Status.choices,
                       "selected": ""}, status=404)
    return render(request, "reino/merchant_order.html", {
        "store": store, "order": order,
        "transitions": {f: [str(v) for v in vs]
                        for f, vs in services_commerce.TRANSITIONS.items()},
        "current": {"status": order.status, "payment_status": order.payment_status,
                    "prep_status": order.prep_status, "delivery_status": order.delivery_status},
    })


@merchant_view
@require_POST
def order_transition(request, store, public_id):
    order = Order.objects.filter(store=store, public_id=public_id).first()
    if order:
        try:
            services_commerce.apply_transition(
                order, request.POST["field"], request.POST["to"],
                user=request.user, note=request.POST.get("note", "")[:200],
            )
        except (services_commerce.CartError, KeyError) as exc:
            request.session["reino_flash"] = str(exc)
    return redirect("reino_merchant_order", slug=store.slug, public_id=public_id)


@merchant_view
def settings_view(request, store):
    """M10 mínimo: identidad, integraciones con estado real y uso de IA."""
    from django.conf import settings as djsettings
    integrations = [
        {"name": "Pasarela de pagos", "state": "Sin configurar",
         "detail": "Pago manual con verificación del equipo (flujo aprobado P0)."},
        {"name": "Bitcoin (manual)", "state": "Prueba",
         "detail": "Descuento 15 % pendiente de verificación por el equipo."},
        {"name": "Correo transaccional", "state": "Sin configurar",
         "detail": "La pantalla de pedido no promete envío de correo."},
        {"name": "IA (Royal Stylist)",
         "state": "Producción" if djsettings.REINO_AI.get("API_KEY") else "Sin configurar",
         "detail": "Sin clave el asesor informa su modo por reglas."},
        {"name": "Operador logístico", "state": "Sin configurar",
         "detail": "Matriz de zonas manual (retiro y tarifas por zona)."},
    ]
    return render(request, "reino/merchant_settings.html",
                  {"store": store, "integrations": integrations})
