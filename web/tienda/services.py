"""Smart Quote: cotización calculada siempre en el servidor.

El cliente solo indica qué perro y qué producto; el precio se toma del
catálogo controlado (`tienda.views.PRODUCTOS`) y nunca de datos del navegador.

La regla de ajuste por talla/peso/materiales NO está definida por el negocio,
así que toda cotización es PROVISIONAL (precio base, sin ajuste).
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .models import Quote
from .views import PRODUCTOS


# Precio final máximo por producto indicado en la guía. Es solo un tope
# técnico: no existe aún una fórmula de ajuste por talla.
UNIT_PRICE_CAP = Decimal("850.00")


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
    if price <= 0 or price > UNIT_PRICE_CAP:
        raise InvalidCatalogPrice(raw)
    return price.quantize(Decimal("0.01"))


MAX_QUANTITY = 10  # supuesto técnico, pendiente de aprobación del negocio


class QuantityError(Exception):
    pass


def normalize_quantity(raw):
    """Cantidad entera entre 1 y MAX_QUANTITY; lanza QuantityError si no."""
    try:
        qty = int(str(raw).strip())
    except (TypeError, ValueError):
        raise QuantityError("Enter a whole number of units.") from None
    if qty < 1 or qty > MAX_QUANTITY:
        raise QuantityError(f"Quantity must be between 1 and {MAX_QUANTITY}.")
    return qty


def create_quote(dog, slug, quantity=1):
    """Crea (o reutiliza) la cotización provisional borrador de un perro/producto."""
    base_price = get_base_price(slug)
    quantity = normalize_quantity(quantity)
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
        changed = []
        if existing.base_price != base_price:
            existing.base_price = base_price
            changed.append("base_price")
        if existing.quantity != quantity:
            existing.quantity = quantity
            changed.append("quantity")
        if changed:
            existing.save(update_fields=changed)
        return existing
    return Quote.objects.create(
        dog=dog, product_slug=slug, base_price=base_price, quantity=quantity
    )


def set_quote_quantity(quote, quantity):
    """Corrige la cantidad de una cotización borrador (solo sin pedido)."""
    quantity = normalize_quantity(quantity)
    if quote.status != Quote.Status.DRAFT or hasattr(quote, "order"):
        raise QuantityError("This quote can no longer be changed.")
    quote.quantity = quantity
    quote.save(update_fields=["quantity"])
    return quote


def compute_totals(quote, payment_method="unspecified"):
    """Importes de una cotización, siempre calculados en el servidor.

    - Precio unitario: catálogo (o total_price si una regla futura lo fija).
    - Subtotal de productos = unitario × cantidad.
    - Descuento Bitcoin: 15 % del subtotal de productos; el envío no entra.
    - Envío: sin tarifa definida, se muestra como pendiente.
    """
    unit_base = get_base_price(quote.product_slug)
    is_final = quote.pricing == Quote.Pricing.FINAL and quote.total_price is not None
    unit = quote.total_price if is_final else unit_base
    subtotal = _money(unit * quote.quantity)
    rate, discount = compute_discount(subtotal, payment_method)
    return {
        "unit_base_price": unit_base,
        "unit_price": unit,
        "quantity": quote.quantity,
        "subtotal": subtotal,
        "is_final": is_final,
        "discount_rate": rate,
        "discount_amount": discount,
        "shipping": None,  # por confirmar
        "amount_due": subtotal,  # el descuento aplica al verificar el pago
        "total_if_discount": _money(subtotal - discount),
    }


def build_breakdown(quote, payment_method="unspecified"):
    """Desglose legible; provisional mientras no haya regla de ajuste por talla."""
    t = compute_totals(quote, payment_method)
    name = get_product(quote.product_slug)["nombre"]
    lines = [
        {"label": f"{name} — unit base price", "amount": t["unit_price"], "note": ""},
        {"label": "Quantity", "amount": None, "note": str(t["quantity"]), "plain": True},
        {
            "label": "Size adjustment",
            "amount": None,
            "note": "Not calculated yet. The sizing rule is pending business approval.",
        },
        {"label": "Products subtotal", "amount": t["subtotal"], "note": ""},
    ]
    if t["discount_rate"]:
        lines.append(
            {
                "label": "Bitcoin discount (15%)",
                "amount": -t["discount_amount"],
                "note": "Applied once your payment is verified.",
            }
        )
    lines.append(
        {"label": "Shipping", "amount": None, "note": "To be confirmed."}
    )
    return {
        "lines": lines,
        "total": t["subtotal"],
        "is_final": t["is_final"],
        "totals": t,
    }


# --- Estados del pedido (panel) ---------------------------------------------
# Supuestos técnicos pendientes de aprobación del negocio: transiciones
# secuenciales, sin retrocesos, y no enviar antes de terminar la producción.

TARGET_MANUFACTURING_COST = Decimal("175.00")  # objetivo, NO costo comprobado
CENT = Decimal("0.01")
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
        frozen = (order.snapshot or {}).get("cost_estimate")
        live = None if frozen else product_cost_summary(
            (order.snapshot or {}).get("product", {}).get("slug", "")
        )
        if frozen:
            cost = Decimal(frozen["total_cost"]) * order.quantity
            source = "product_estimate"
        elif live:
            cost, source = live["total_cost"] * order.quantity, "product_estimate"
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
        "margin_negative": margin < 0,
        "target_cost": TARGET_MANUFACTURING_COST,
    }



class CostError(Exception):
    def __init__(self, messages):
        super().__init__("; ".join(messages))
        self.messages = messages


def _money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def product_cost_summary(slug):
    """Presupuesto interno de un producto: partidas, totales y margen bruto.

    El total de materiales se deriva de las partidas (consumo × precio
    unitario); nunca se guarda como constante. Devuelve None si no hay perfil.
    """
    from .models import ProductCost

    profile = ProductCost.objects.filter(product_slug=slug).first()
    if profile is None:
        return None
    lines = []
    for line in profile.lines.all():
        lines.append(
            {
                "id": line.pk,
                "name": line.name,
                "unit": line.unit,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "subtotal": line.subtotal,
                "is_reserve": line.is_provisional_reserve,
                "is_validated": line.is_validated,
            }
        )
    materials = _money(sum((l["subtotal"] for l in lines), Decimal("0")))
    total_cost = _money(materials + profile.labor_cost + profile.other_costs)
    try:
        sale_price = get_base_price(slug)
    except (UnknownProduct, InvalidCatalogPrice):
        sale_price = None
    margin = None if sale_price is None else _money(sale_price - total_cost)
    pct = None
    if margin is not None and sale_price:
        pct = (margin / sale_price * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    all_validated = profile.is_validated and all(l["is_validated"] for l in lines)
    return {
        "slug": slug,
        "name": PRODUCTOS.get(slug, {}).get("nombre", slug),
        "lines": lines,
        "materials_total": materials,
        "labor_cost": profile.labor_cost,
        "other_costs": profile.other_costs,
        "total_cost": total_cost,
        "sale_price": sale_price,
        "margin": margin,
        "margin_pct": pct,
        "margin_negative": margin is not None and margin < 0,
        "has_reserve": any(l["is_reserve"] for l in lines),
        "is_validated": all_validated,
        "notes": profile.notes,
        "updated_at": profile.updated_at,
    }


def all_product_costs():
    return [s for s in (product_cost_summary(slug) for slug in PRODUCTOS) if s]


def _dec_field(raw, label, errors, minimum=Decimal("0"), required=True):
    raw = (raw or "").strip()
    if raw == "":
        if required:
            errors.append(f"{label}: a value is required.")
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        errors.append(f"{label}: enter a valid number.")
        return None
    if not value.is_finite() or value < minimum:
        errors.append(f"{label}: must be {minimum} or more.")
        return None
    return value


def update_product_cost(slug, data, user=None):
    """Aplica ediciones del formulario interno (todo o nada).

    `data` es un dict tipo POST. Campos: labor_cost, other_costs, notes,
    is_validated, qty_<id>, price_<id>, validated_<id>, delete_<id> y una
    partida nueva (new_name, new_unit, new_qty, new_price).
    """
    from django.db import transaction

    from .models import MaterialLine, ProductCost

    errors = []
    with transaction.atomic():
        profile = ProductCost.objects.select_for_update().filter(product_slug=slug).first()
        if profile is None:
            raise CostError(["Unknown product cost profile."])
        labor = _dec_field(data.get("labor_cost"), "Labor cost", errors)
        other = _dec_field(data.get("other_costs"), "Other production costs", errors)
        edits = []
        for line in profile.lines.all():
            if data.get(f"delete_{line.pk}"):
                edits.append((line, None, None, None, True))
                continue
            qty = _dec_field(data.get(f"qty_{line.pk}"), f"{line.name} — consumption", errors)
            price = _dec_field(data.get(f"price_{line.pk}"), f"{line.name} — unit price", errors)
            edits.append((line, qty, price, bool(data.get(f"validated_{line.pk}")), False))

        new_line = None
        new_name = (data.get("new_name") or "").strip()
        if new_name or (data.get("new_qty") or "").strip() or (data.get("new_price") or "").strip():
            qty = _dec_field(data.get("new_qty"), "New line — consumption", errors)
            price = _dec_field(data.get("new_price"), "New line — unit price", errors)
            if not new_name:
                errors.append("New line: a name is required.")
            unit = (data.get("new_unit") or "").strip()[:20] or "unidad"
            new_line = (new_name[:120], unit, qty, price)

        if errors:
            raise CostError(errors)

        profile.labor_cost = labor
        profile.other_costs = other
        profile.is_validated = bool(data.get("is_validated"))
        profile.notes = (data.get("notes") or "").strip()[:300]
        profile.updated_by = user if getattr(user, "pk", None) else None
        profile.save()
        for line, qty, price, validated, delete in edits:
            if delete:
                line.delete()
                continue
            line.quantity = qty
            line.unit_price = price
            line.is_validated = validated
            line.save()
        if new_line:
            last = profile.lines.order_by("-position").first()
            MaterialLine.objects.create(
                product_cost=profile,
                position=(last.position + 1) if last else 1,
                name=new_line[0],
                unit=new_line[1],
                quantity=new_line[2],
                unit_price=new_line[3],
            )
    return product_cost_summary(slug)


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

        totals = compute_totals(quote, payment_method)
        base_price = totals["unit_base_price"]
        is_final = totals["is_final"]
        total = totals["subtotal"]
        product = get_product(quote.product_slug)
        dog = quote.dog
        rate, discount_amount = totals["discount_rate"], totals["discount_amount"]
        cost = product_cost_summary(quote.product_slug)
        size = classify_size(dog)
        snapshot = {
            "currency": "USD",
            "product": {"slug": quote.product_slug, "name": product["nombre"]},
            "base_price": _dec(base_price),
            "total": _dec(total),
            "pricing": "final" if is_final else "provisional",
            "quantity": quote.quantity,
            "unit_price": _dec(totals["unit_price"]),
            "subtotal": _dec(total),
            "shipping": {"status": "pending", "amount": None},
            "dog": {
                "name": dog.name,
                "breed": dog.breed,
                "weight_kg": _dec(dog.weight_kg),
                "back_length_cm": _dec(dog.back_length_cm),
                "chest_girth_cm": _dec(dog.chest_girth_cm),
                "neck_girth_cm": _dec(dog.neck_girth_cm),
            },
            "quote_public_id": str(quote.public_id),
            "size_reference": {
                "status": size["status"],
                "candidates": [c["text"] for c in size["candidates"]],
                "validated": size["validated"],
                "note": "Reference only; size table not validated with tailoring.",
            },
            "required_measurements": measurement_requirements(quote.product_slug),
            "cost_estimate": None if cost is None else {
                "status": "estimate_not_verified",
                "materials_total": _dec(cost["materials_total"]),
                "labor_cost": _dec(cost["labor_cost"]),
                "other_costs": _dec(cost["other_costs"]),
                "total_cost": _dec(cost["total_cost"]),
                "lines": [
                    {
                        "name": l["name"],
                        "unit": l["unit"],
                        "quantity": _dec(l["quantity"]),
                        "unit_price": _dec(l["unit_price"]),
                        "subtotal": _dec(l["subtotal"]),
                    }
                    for l in cost["lines"]
                ],
            },
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
                    quantity=quote.quantity,
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


# --- Medidas y talla de referencia (Smart Fit) --------------------------------

def measurement_requirements(slug):
    """Medidas extra que exige la prenda (configurable en el panel)."""
    from .models import ProductMeasurement

    pm = ProductMeasurement.objects.filter(product_slug=slug).first()
    return {
        "neck_girth": bool(pm and pm.requires_neck),
        "validated": bool(pm and pm.is_validated),
    }


def missing_measurements(dog, slug):
    """Campos que la prenda exige y el perfil aún no tiene."""
    missing = []
    if measurement_requirements(slug)["neck_girth"] and dog.neck_girth_cm is None:
        missing.append("neck_girth")
    return missing


def classify_size(dog):
    """Talla de referencia a partir de las MEDIDAS (nunca por raza).

    Resultado informativo y no validado: no cambia precios ni cotizaciones.
    Estados: matched (una fila), ambiguous (varias) u outside (ninguna).
    """
    from .models import SizeRange

    def inside(value, low, high):
        return low <= value <= high

    candidates = []
    for row in SizeRange.objects.all():
        if not inside(dog.chest_girth_cm, row.chest_min, row.chest_max):
            continue
        if not inside(dog.back_length_cm, row.back_min, row.back_max):
            continue
        if dog.neck_girth_cm is not None and not inside(
            dog.neck_girth_cm, row.neck_min, row.neck_max
        ):
            continue
        candidates.append(row)
    status = "matched" if len(candidates) == 1 else "ambiguous" if candidates else "outside"
    return {
        "status": status,
        "candidates": [
            {"label": r.label, "group": r.group, "text": r.display} for r in candidates
        ],
        "validated": bool(candidates) and all(r.is_validated for r in candidates),
        "used_neck": dog.neck_girth_cm is not None,
    }


def update_measurement_config(post, user=None):
    """Guarda requisitos por prenda y tabla de tallas (todo o nada)."""
    from django.db import transaction

    from .models import ProductMeasurement, SizeRange

    errors = []
    rows = list(SizeRange.objects.all())
    parsed = {}
    for row in rows:
        values = {}
        for field in ("neck_min", "neck_max", "chest_min", "chest_max", "back_min", "back_max"):
            raw = (post.get(f"{field}_{row.pk}") or "").strip()
            try:
                v = Decimal(raw)
            except InvalidOperation:
                errors.append(f"{row.display} — {field}: enter a number.")
                continue
            if not v.is_finite() or v <= 0 or v > Decimal("300"):
                errors.append(f"{row.display} — {field}: must be between 0 and 300.")
                continue
            values[field] = v
        for lo, hi in (("neck_min", "neck_max"), ("chest_min", "chest_max"), ("back_min", "back_max")):
            if lo in values and hi in values and values[lo] > values[hi]:
                errors.append(f"{row.display}: {lo} is greater than {hi}.")
        parsed[row.pk] = values
    if errors:
        raise CostError(errors)
    with transaction.atomic():
        for row in rows:
            for field, value in parsed[row.pk].items():
                setattr(row, field, value)
            row.is_validated = bool(post.get(f"svalid_{row.pk}"))
            row.save()
        for slug in PRODUCTOS:
            pm, _ = ProductMeasurement.objects.get_or_create(product_slug=slug)
            pm.requires_neck = bool(post.get(f"neck_{slug}"))
            pm.is_validated = bool(post.get(f"valid_{slug}"))
            pm.save()
