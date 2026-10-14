from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from . import services
from .forms import CostForm
from .models import Order

PAGE_SIZE = 25


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (user.is_active and user.is_staff):
            return HttpResponseForbidden("Staff access only.")
        return view(request, *args, **kwargs)

    return wrapper


@staff_required
def orders(request):
    qs = Order.objects.order_by("-created_at", "-pk")
    q = request.GET.get("q", "").strip()
    if q:
        cond = (
            Q(customer_name__icontains=q)
            | Q(customer_email__icontains=q)
            | Q(snapshot__product__name__icontains=q)
        )
        digits = q.upper().removeprefix("WK-").lstrip("0")
        if digits.isdigit():
            cond |= Q(pk=int(digits))
        qs = qs.filter(cond)
    filters = {}
    for field, choices in (
        ("status", Order.Status),
        ("payment_status", Order.PaymentStatus),
        ("production_status", Order.ProductionStatus),
        ("shipping_status", Order.ShippingStatus),
    ):
        value = request.GET.get(field, "")
        if value in choices.values:
            qs = qs.filter(**{field: value})
            filters[field] = value
    return render(
        request,
        "tienda/panel_orders.html",
        {
            "orders": qs[:PAGE_SIZE],
            "total_count": qs.count(),
            "page_size": PAGE_SIZE,
            "q": q,
            "filters": filters,
            "status_choices": Order.Status.choices,
            "payment_choices": Order.PaymentStatus.choices,
            "production_choices": Order.ProductionStatus.choices,
            "shipping_choices": Order.ShippingStatus.choices,
        },
    )


@staff_required
def payments(request):
    from .models import ProductPaymentRule

    if request.method == "POST":
        services.update_payment_rules(request.POST)
        return redirect("panel_payments")
    flags = {r.product_slug: r.bitcoin_discount_eligible for r in ProductPaymentRule.objects.all()}
    products = [
        {"slug": slug, "name": item["nombre"], "eligible": flags.get(slug, True)}
        for slug, item in services.PRODUCTOS.items()
    ]
    return render(request, "tienda/panel_payments.html", {"products": products})


@staff_required
def measurements(request):
    from .models import ProductMeasurement, SizeRange

    errors = []
    status = 200
    if request.method == "POST":
        try:
            services.update_measurement_config(request.POST, user=request.user)
        except services.CostError as exc:
            errors, status = exc.messages, 400
        else:
            return redirect("panel_measurements")
    flags = {m.product_slug: m for m in ProductMeasurement.objects.all()}
    products = [
        {
            "slug": slug,
            "name": item["nombre"],
            "requires_neck": getattr(flags.get(slug), "requires_neck", False),
            "is_validated": getattr(flags.get(slug), "is_validated", False),
        }
        for slug, item in services.PRODUCTOS.items()
    ]
    return render(
        request,
        "tienda/panel_measurements.html",
        {"products": products, "sizes": SizeRange.objects.all(), "errors": errors},
        status=status,
    )


@staff_required
def costs(request):
    return render(request, "tienda/panel_costs.html", {"products": services.all_product_costs()})


@staff_required
def product_cost(request, slug):
    summary = services.product_cost_summary(slug)
    if summary is None:
        raise Http404
    errors = []
    status = 200
    if request.method == "POST":
        try:
            services.update_product_cost(slug, request.POST, user=request.user)
        except services.CostError as exc:
            errors = exc.messages
            status = 400
        else:
            return redirect("panel_product_cost", slug=slug)
    return render(
        request,
        "tienda/panel_cost_product.html",
        {"cost": summary, "errors": errors, "posted": request.POST if errors else None},
        status=status,
    )


@staff_required
def order(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    error = None
    cost_form = CostForm(initial={
        "estimated_materials": order.estimated_materials,
        "estimated_labor": order.estimated_labor,
        "actual_materials": order.actual_materials,
        "actual_labor": order.actual_labor,
        "cost_notes": order.cost_notes,
    })
    if request.method == "POST" and request.POST.get("form") == "costs":
        cost_form = CostForm(request.POST)
        if cost_form.is_valid():
            d = cost_form.cleaned_data
            services.update_costs(
                order,
                user=request.user,
                estimated_materials=d["estimated_materials"],
                estimated_labor=d["estimated_labor"],
                actual_materials=d["actual_materials"],
                actual_labor=d["actual_labor"],
                notes=d["cost_notes"],
            )
            return redirect("panel_order", public_id=order.public_id)
        order.refresh_from_db()
    elif request.method == "POST" and request.POST.get("form") == "payment_method":
        try:
            services.set_payment_method(
                order, request.POST.get("payment_method", ""), user=request.user
            )
        except services.TransitionError as exc:
            error = str(exc)
            order.refresh_from_db()
        else:
            return redirect("panel_order", public_id=order.public_id)
    elif request.method == "POST":
        try:
            services.apply_transition(
                order,
                request.POST.get("field", ""),
                request.POST.get("value", ""),
                user=request.user,
                note=request.POST.get("note", ""),
            )
        except services.TransitionError as exc:
            error = str(exc)
            order.refresh_from_db()
        else:
            return redirect("panel_order", public_id=order.public_id)
    return render(
        request,
        "tienda/panel_order.html",
        {
            "order": order,
            "snap": order.snapshot,
            "events": order.events.select_related("by"),
            "allowed": services.allowed_transitions(order),
            "cost": services.cost_summary(order),
            "cost_form": cost_form,
            "settable_methods": [
                ("unspecified", "To be arranged"),
                ("bitcoin", "Bitcoin"),
            ],
            "error": error,
        },
        status=400 if (error or cost_form.errors) else 200,
    )
