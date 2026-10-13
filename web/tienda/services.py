"""Smart Quote: cotización calculada siempre en el servidor.

El cliente solo indica qué perro y qué producto; el precio se toma del
catálogo controlado (`tienda.views.PRODUCTOS`) y nunca de datos del navegador.

La regla de ajuste por talla/peso/materiales NO está definida por el negocio,
así que toda cotización es PROVISIONAL (precio base, sin ajuste).
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .models import Quote
from .views import PRODUCTOS


class UnknownProduct(Exception):
    pass


class InvalidCatalogPrice(Exception):
    pass


def get_product(slug):
    try:
        return PRODUCTOS[slug]
    except KeyError:
        raise UnknownProduct(slug) from None


def get_base_price(slug):
    """Precio base como Decimal, a partir del catálogo (p. ej. "$650")."""
    raw = get_product(slug)["precio"]
    try:
        price = Decimal(str(raw).strip().lstrip("$").replace(",", ""))
    except InvalidOperation:
        raise InvalidCatalogPrice(raw) from None
    if price <= 0:
        raise InvalidCatalogPrice(raw)
    return price.quantize(Decimal("0.01"))


def create_quote(dog, slug):
    """Crea (o reutiliza) la cotización provisional borrador de un perro/producto."""
    base_price = get_base_price(slug)
    existing = (
        Quote.objects.filter(
            dog=dog,
            product_slug=slug,
            status=Quote.Status.DRAFT,
            pricing=Quote.Pricing.PROVISIONAL,
        )
        .order_by("-pk")
        .first()
    )
    if existing:
        # Si el catálogo cambió, el precio del borrador se refresca.
        if existing.base_price != base_price:
            existing.base_price = base_price
            existing.save(update_fields=["base_price"])
        return existing
    return Quote.objects.create(dog=dog, product_slug=slug, base_price=base_price)


def build_breakdown(quote):
    """Desglose legible; el total mostrado es provisional mientras no haya regla."""
    lines = [
        {
            "label": f"{get_product(quote.product_slug)['nombre']} — base price",
            "amount": quote.base_price,
            "note": "",
        },
        {
            "label": "Size adjustment",
            "amount": None,
            "note": "Not calculated yet. The sizing rule is pending business approval.",
        },
    ]
    is_final = quote.pricing == Quote.Pricing.FINAL and quote.total_price is not None
    return {
        "lines": lines,
        "total": quote.total_price if is_final else quote.base_price,
        "is_final": is_final,
    }


# --- Estados del pedido (panel) ---------------------------------------------
# Supuestos técnicos pendientes de aprobación del negocio: transiciones
# secuenciales, sin retrocesos, y no enviar antes de terminar la producción.

TARGET_MANUFACTURING_COST = Decimal("175.00")  # objetivo, NO costo comprobado
BITCOIN_DISCOUNT_RATE = Decimal("0.15")  # sobre el subtotal de productos, sin envío

TRANSITIONS = {
    "status": {"pending": ["confirmed", "cancelled"], "confirmed": ["cancelled"]},
    "payment_status": {"unpaid": ["paid"]},
    "production_status": {
        "not_started": ["in_production"],
        "in_production": ["completed"],
    },
    "shipping_status": {"not_shipped": ["shipped"], "shipped": ["delivered"]},
}


class TransitionError(Exception):
    pass


def _check_rules(order, field, new_value):
    """Devuelve un mensaje de error o None si la transición es válida."""
    if order.status == "cancelled" and field != "status":
        return "Cancelled orders cannot change state."
    if field == "production_status" and new_value == "in_production":
        if order.payment_status != "paid":
            return "Payment must be verified before production can start."
    if field == "shipping_status" and new_value == "shipped":
        if order.production_status != "completed":
            return "Production must be completed before shipping."
    if field == "status" and new_value == "cancelled":
        if order.shipping_status != "not_shipped":
            return "A shipped order cannot be cancelled."
    return None


def allowed_transitions(order):
    result = {}
    for field, table in TRANSITIONS.items():
        current = getattr(order, field)
        result[field] = [
            t for t in table.get(current, []) if _check_rules(order, field, t) is None
        ]
    return result


def apply_transition(order, field, new_value, user=None, note=""):
    from django.db import transaction

    from .models import Order, OrderEvent

    if field not in TRANSITIONS:
        raise TransitionError("Unknown state field.")
    note = (note or "").strip()
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        current = getattr(order, field)
        if new_value not in TRANSITIONS[field].get(current, []):
            raise TransitionError(f"Cannot change {field} from {current} to {new_value}.")
        error = _check_rules(order, field, new_value)
        if error:
            raise TransitionError(error)
        if field == "payment_status":
            # Pago manual: exige referencia como evidencia; no se simula ningún proveedor.
            if not note:
                raise TransitionError(
                    "A payment reference is required to mark an order as paid."
                )
            order.payment_reference = note[:120]
        setattr(order, field, new_value)
        discount_event = None
        if (
            field == "payment_status"
            and new_value == "paid"
            and order.discount_status == "pending_verification"
        ):
            # El pago (con su referencia) quedó verificado por el personal.
            order.discount_status = "applied"
            discount_event = ("pending_verification", "applied")
        order.save()
        if discount_event:
            OrderEvent.objects.create(
                order=order,
                field="discount_status",
                from_value=discount_event[0],
                to_value=discount_event[1],
                note=note[:200],
                by=user if getattr(user, "pk", None) else None,
            )
        OrderEvent.objects.create(
            order=order,
            field=field,
            from_value=current,
            to_value=new_value,
            note=note[:200],
            by=user if getattr(user, "pk", None) else None,
        )
    return order


def cost_summary(order):
    """Costo y margen internos, indicando de dónde sale cada valor.

    Prioridad: costo real > costo estimado cargado > objetivo provisional.
    Los ingresos son el importe a pagar (el descuento Bitcoin solo cuenta
    cuando está aplicado).
    """
    if order.actual_cost is not None:
        cost, source = order.actual_cost, "actual"
    elif order.estimated_cost is not None:
        cost, source = order.estimated_cost, "estimated"
    else:
        cost, source = TARGET_MANUFACTURING_COST, "target"
    revenue = order.amount_due
    margin = revenue - cost
    pct = (margin / revenue * 100).quantize(Decimal("0.1")) if revenue else None
    return {
        "total": order.total,
        "revenue": revenue,
        "discount_pending": order.discount_status == "pending_verification",
        "discount_amount": order.discount_amount,
        "total_is_provisional": order.price_is_provisional,
        "cost": cost,
        "cost_source": source,
        "is_actual": source == "actual",
        "margin": margin,
        "margin_pct": pct,
        "target_cost": TARGET_MANUFACTURING_COST,
    }


def _sum_parts(*parts):
    present = [p for p in parts if p is not None]
    return sum(present, Decimal("0")) if present else None


def update_costs(
    order,
    user=None,
    estimated_materials=None,
    estimated_labor=None,
    actual_materials=None,
    actual_labor=None,
    notes="",
):
    """Guarda costos internos (materiales y mano de obra) y registra el cambio."""
    from django.db import transaction

    from .models import Order, OrderEvent

    values = (estimated_materials, estimated_labor, actual_materials, actual_labor)
    if any(v is not None and v < 0 for v in values):
        raise TransitionError("Costs cannot be negative.")
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        new = {
            "estimated_materials": estimated_materials,
            "estimated_labor": estimated_labor,
            "actual_materials": actual_materials,
            "actual_labor": actual_labor,
            "estimated_cost": _sum_parts(estimated_materials, estimated_labor),
            "actual_cost": _sum_parts(actual_materials, actual_labor),
        }
        for field, value in new.items():
            old = getattr(order, field)
            if old != value:
                setattr(order, field, value)
                OrderEvent.objects.create(
                    order=order,
                    field=field,
                    from_value="" if old is None else str(old),
                    to_value="" if value is None else str(value),
                    note="",
                    by=user if getattr(user, "pk", None) else None,
                )
        order.cost_notes = (notes or "").strip()[:300]
        order.save()
    return order


class QuoteNotOrderable(Exception):
    pass


def _dec(value):
    return None if value is None else str(value)


def compute_discount(subtotal, payment_method):
    """(tasa, importe) del descuento; solo Bitcoin tiene descuento aprobado."""
    if payment_method == "bitcoin":
        amount = (subtotal * BITCOIN_DISCOUNT_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return BITCOIN_DISCOUNT_RATE, amount
    return Decimal("0"), Decimal("0.00")


def create_order(quote, customer):
    """Crea el pedido de una cotización; idempotente por cotización.

    El total se recalcula aquí desde el catálogo; nada del navegador influye.
    Si la cotización ya tiene pedido, devuelve (pedido_existente, False).
    """
    from django.db import IntegrityError, transaction

    from .models import Order

    customer = dict(customer)
    payment_method = customer.pop("payment_method", "unspecified")
    if payment_method not in ("unspecified", "bitcoin"):
        payment_method = "unspecified"

    with transaction.atomic():
        quote = Quote.objects.select_for_update().select_related("dog").get(pk=quote.pk)
        existing = Order.objects.filter(quote=quote).first()
        if existing:
            return existing, False
        if quote.status == Quote.Status.CANCELLED:
            raise QuoteNotOrderable("cancelled")

        base_price = get_base_price(quote.product_slug)
        is_final = quote.pricing == Quote.Pricing.FINAL and quote.total_price is not None
        total = quote.total_price if is_final else base_price
        product = get_product(quote.product_slug)
        dog = quote.dog
        rate, discount_amount = compute_discount(total, payment_method)
        snapshot = {
            "currency": "USD",
            "product": {"slug": quote.product_slug, "name": product["nombre"]},
            "base_price": _dec(base_price),
            "total": _dec(total),
            "pricing": "final" if is_final else "provisional",
            "dog": {
                "name": dog.name,
                "breed": dog.breed,
                "weight_kg": _dec(dog.weight_kg),
                "back_length_cm": _dec(dog.back_length_cm),
                "chest_girth_cm": _dec(dog.chest_girth_cm),
                "neck_girth_cm": _dec(dog.neck_girth_cm),
            },
            "quote_public_id": str(quote.public_id),
            "payment_method": payment_method,
            "discount": {
                "rate": _dec(rate),
                "amount": _dec(discount_amount),
                "status": "pending_verification" if rate else "none",
            },
        }
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    quote=quote,
                    total=total,
                    price_is_provisional=not is_final,
                    snapshot=snapshot,
                    payment_method=payment_method,
                    discount_rate=rate,
                    discount_amount=discount_amount,
                    discount_status="pending_verification" if rate else "none",
                    **customer,
                )
        except IntegrityError:
            return Order.objects.get(quote=quote), False
        quote.base_price = base_price
        quote.status = Quote.Status.ACCEPTED
        quote.save(update_fields=["base_price", "status"])
        return order, True
