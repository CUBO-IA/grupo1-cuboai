"""Núcleo de compra P0: carrito, checkout, pedido, reservas e idempotencia.

Reglas (§15):
- Agregar al carrito NO aparta inventario; preparar checkout crea una reserva
  corta (10 min) dentro de una transacción.
- Dinero en Decimal con money(); envío separado; nunca "total final" incompleto.
- El servidor reconstruye importes; doble clic no crea dos pedidos (clave
  idempotente única = misma operación devuelve el resultado previo).
- Pago manual/bitcoin: el pedido queda PENDIENTE de verificación; un
  comprobante es evidencia para revisar, nunca pago automático.
- Descuento Bitcoin 15 % preservado: sobre mercancía, pendiente de verificación.
"""

import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    Cart, CartItem, CheckoutSession, Order, OrderEvent, OrderItem, OutboxEvent,
    StockReservation, Variant,
)
from .money import BITCOIN_DISCOUNT_RATE, money

RESERVATION_MINUTES = 10
MAX_QUANTITY = 10


class CartError(Exception):
    pass


class StockConflict(Exception):
    """Stock insuficiente o carrito cambiado: conflicto recuperable (409)."""

    def __init__(self, message, lines=None):
        super().__init__(message)
        self.lines = lines or []


def get_open_cart(store, session_key, create=False):
    cart = Cart.objects.filter(
        store=store, session_key=session_key, status=Cart.Status.OPEN
    ).first()
    if cart is None and create:
        cart = Cart.objects.create(store=store, session_key=session_key)
    return cart


def cart_summary(cart, payment_method="manual"):
    """Totales del carrito calculados en servidor. Envío: por calcular."""
    lines, subtotal = [], money(0)
    for item in cart.items.select_related("variant__product", "recipient"):
        # Revalidación de precio: el snapshot puede diferir del precio vigente.
        current = item.variant.price
        line_subtotal = money(current * item.quantity)
        subtotal += line_subtotal
        lines.append({
            "item": item,
            "current_price": current,
            "price_changed": current != item.unit_price,
            "subtotal": line_subtotal,
            "available": item.variant.stock,
            "ok": item.variant.is_active and item.variant.stock >= item.quantity,
        })
    discount = money(0)
    if payment_method == "bitcoin":
        discount = money(subtotal * BITCOIN_DISCOUNT_RATE)
    return {
        "lines": lines,
        "subtotal": subtotal,
        "discount": discount,
        "discount_note": "Descuento Bitcoin (15 %), pendiente de verificación" if discount else "",
        "shipping": None,  # por calcular: nunca un total incompleto como "final"
        "merchandise_total": subtotal,
        "amount_due": subtotal,  # el descuento aplica al verificar el pago
        "total_if_discount": money(subtotal - discount),
        "has_issues": any(not l["ok"] for l in lines),
        "is_empty": not lines,
    }


def add_item(cart, variant: Variant, quantity=1, recipient=None):
    """Añade una variante válida. Revalida precio; no duplica (misma variante
    y destinatario actualizan cantidad). Una variante inexistente no entra."""
    if not variant.is_active or variant.product.status != "published":
        raise CartError("Esa variante ya no está disponible.")
    if variant.product.store_id != cart.store_id:
        raise CartError("La variante no pertenece a esta tienda.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise CartError("Ingresá una cantidad válida.") from None
    if quantity < 1 or quantity > MAX_QUANTITY:
        raise CartError(f"La cantidad debe ser entre 1 y {MAX_QUANTITY}.")
    if variant.stock < 1:
        raise StockConflict("Sin existencias por ahora.", [variant.sku])
    with transaction.atomic():
        item = (
            CartItem.objects.select_for_update()
            .filter(cart=cart, variant=variant, recipient=recipient)
            .first()
        )
        if item:
            item.quantity = min(item.quantity + quantity, MAX_QUANTITY)
            item.unit_price = variant.price
            item.save(update_fields=["quantity", "unit_price"])
        else:
            CartItem.objects.create(
                cart=cart, variant=variant, quantity=quantity,
                recipient=recipient, unit_price=variant.price,
            )
        _bump(cart)
    return cart


def update_item(cart, item_id, quantity):
    item = CartItem.objects.filter(cart=cart, pk=item_id).first()
    if item is None:
        raise CartError("Esa línea ya no existe.")
    quantity = int(quantity)
    if quantity < 1 or quantity > MAX_QUANTITY:
        raise CartError(f"La cantidad debe ser entre 1 y {MAX_QUANTITY}.")
    item.quantity = quantity
    item.unit_price = item.variant.price
    item.save(update_fields=["quantity", "unit_price"])
    _bump(cart)


def remove_item(cart, item_id):
    CartItem.objects.filter(cart=cart, pk=item_id).delete()
    _bump(cart)


def _bump(cart):
    cart.version = (cart.version or 0) + 1
    cart.save(update_fields=["version", "updated_at"])


def prepare_checkout(cart, payment_method, delivery_mode="pickup", zone=None,
                     idempotency_key=None):
    """Crea la sesión de checkout con reserva atómica de stock (10 min).

    - Misma clave idempotente => devuelve la sesión previa (A18).
    - Cambio de carrito (versión) => resumen nuevo; el anterior queda inválido.
    - Sin tarifa configurada para la zona => conflicto honesto, nunca $0 ficticio.
    """
    key = idempotency_key or uuid.uuid4().hex
    existing = CheckoutSession.objects.filter(idempotency_key=key).first()
    if existing:
        return existing

    summary = cart_summary(cart, payment_method)
    if summary["is_empty"]:
        raise CartError("Tu carrito está vacío.")
    if summary["has_issues"]:
        raise StockConflict(
            "Alguna línea ya no tiene existencias suficientes.",
            [l["item"].variant.sku for l in summary["lines"] if not l["ok"]],
        )

    shipping_amount = None
    if delivery_mode == "local":
        if zone is None:
            raise CartError("Elegí una zona de entrega para cotizar el envío.")
        shipping_amount = money(zone.fee)
    elif delivery_mode == "pickup":
        shipping_amount = money(0)

    expires = timezone.now() + timedelta(minutes=RESERVATION_MINUTES)
    with transaction.atomic():
        # Bloqueo en orden estable de filas para evitar interbloqueos.
        variants = list(
            Variant.objects.select_for_update()
            .filter(pk__in=[l["item"].variant_id for l in summary["lines"]])
            .order_by("pk")
        )
        by_pk = {v.pk: v for v in variants}
        for line in summary["lines"]:
            v = by_pk[line["item"].variant_id]
            reserved = sum(
                r.quantity
                for r in v.reservations.filter(
                    status=StockReservation.Status.ACTIVE, expires_at__gt=timezone.now()
                )
            )
            if v.stock - reserved < line["item"].quantity:
                raise StockConflict(
                    f"Quedan {max(v.stock - reserved, 0)} unidades de {v.option_label}.",
                    [v.sku],
                )
        checkout = CheckoutSession.objects.create(
            cart=cart, cart_version=cart.version, idempotency_key=key,
            summary={
                "subtotal": str(summary["subtotal"]),
                "discount": str(summary["discount"]),
                "shipping": str(shipping_amount) if shipping_amount is not None else None,
                "payment_method": payment_method,
                "delivery_mode": delivery_mode,
                "zone": zone.name if zone else "",
                "lines": [
                    {"variant_id": l["item"].variant_id, "quantity": l["item"].quantity,
                     "unit_price": str(l["current_price"])}
                    for l in summary["lines"]
                ],
            },
            expires_at=expires,
        )
        for line in summary["lines"]:
            StockReservation.objects.create(
                variant_id=line["item"].variant_id, checkout=checkout,
                quantity=line["item"].quantity, expires_at=expires,
            )
    return checkout


def confirm_checkout(checkout, customer, idempotency_key):
    """Convierte la sesión de checkout en pedido (idempotente).

    Mismo intento => mismo pedido; pago manual/bitcoin => pendiente de
    verificación; la reserva se consume y el stock se descuenta una sola vez.
    """
    existing = Order.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    if checkout.is_expired():
        raise CartError("La revisión venció. Volvé a confirmar tu carrito.")
    if checkout.cart.status != Cart.Status.OPEN or checkout.cart.version != checkout.cart_version:
        raise CartError("El carrito cambió; revisá el nuevo resumen antes de confirmar.")

    s = checkout.summary
    subtotal = money(s["subtotal"])
    discount = money(s.get("discount", "0"))
    shipping = money(s["shipping"]) if s.get("shipping") is not None else None
    payment_method = s.get("payment_method", "manual")
    total = money(subtotal - discount + (shipping or 0))

    with transaction.atomic():
        variants = list(
            Variant.objects.select_for_update()
            .filter(pk__in=[l["variant_id"] for l in s["lines"]]).order_by("pk")
        )
        by_pk = {v.pk: v for v in variants}
        for line in s["lines"]:
            v = by_pk[line["variant_id"]]
            if v.stock < line["quantity"]:
                raise StockConflict("Sin existencias suficientes.", [v.sku])
        order = Order.objects.create(
            store=checkout.cart.store,
            cart=checkout.cart,
            idempotency_key=idempotency_key,
            reference=_next_reference(checkout.cart.store),
            currency=checkout.cart.store.currency,
            subtotal=subtotal,
            discount_amount=discount,
            discount_note="Descuento Bitcoin (15 %) pendiente de verificación" if discount else "",
            shipping_amount=shipping,
            total=total,
            customer_name=customer["name"],
            customer_email=customer["email"],
            customer_phone=customer.get("phone", ""),
            delivery_mode=s.get("delivery_mode", "pickup"),
            zone=s.get("zone", ""),
            address=customer.get("address", ""),
            city=customer.get("city", ""),
            payment_method=payment_method,
        )
        for i, line in enumerate(s["lines"]):
            v = by_pk[line["variant_id"]]
            v.stock -= line["quantity"]
            v.save(update_fields=["stock"])
            OrderItem.objects.create(
                order=order, position=i, variant=v, sku=v.sku,
                title=v.product.short_title, option_label=v.option_label,
                recipient_alias=line.get("recipient_alias", ""),
                quantity=line["quantity"],
                unit_price=money(line["unit_price"]),
                subtotal=money(money(line["unit_price"]) * line["quantity"]),
            )
        StockReservation.objects.filter(checkout=checkout, status=StockReservation.Status.ACTIVE)\
            .update(status=StockReservation.Status.CONSUMED)
        cart = checkout.cart
        cart.status = Cart.Status.ORDERED
        cart.save(update_fields=["status", "updated_at"])
        OrderEvent.objects.create(order=order, field="status", to_value=Order.Status.PLACED,
                                  note="Pedido registrado")
        # Trabajo diferido recuperable: correo de confirmación (si hay sistema
        # transaccional configurado) y métricas. Se dispara una sola vez.
        OutboxEvent.objects.create(type="order_confirmation_email",
                                   payload={"order_id": str(order.public_id)})
        OutboxEvent.objects.create(type="metric",
                                   payload={"event": "order_placed", "order": order.reference})
    return order


def _next_reference(store):
    prefix = "".join(w[0] for w in store.name.split()[:2]).upper() or "RC"
    last = Order.objects.filter(store=store).count()
    return f"{prefix}-{last + 1:06d}"


# Transiciones de panel (máquina de estados, actor registrado) ---------------

TRANSITIONS = {
    "status": {
        Order.Status.PLACED: [Order.Status.CONFIRMED, Order.Status.CANCELLED],
        Order.Status.CONFIRMED: [Order.Status.CANCELLED, Order.Status.CLOSED],
    },
    "payment_status": {
        Order.PaymentStatus.PENDING: [Order.PaymentStatus.PAID, Order.PaymentStatus.FAILED,
                                      Order.PaymentStatus.EXPIRED],
        Order.PaymentStatus.PAID: [Order.PaymentStatus.REFUNDED,
                                   Order.PaymentStatus.PARTIALLY_REFUNDED,
                                   Order.PaymentStatus.DISPUTED],
    },
    "prep_status": {
        Order.PrepStatus.NOT_STARTED: [Order.PrepStatus.PREPARING, Order.PrepStatus.CANCELLED],
        Order.PrepStatus.PREPARING: [Order.PrepStatus.READY, Order.PrepStatus.CANCELLED],
    },
    "delivery_status": {
        Order.DeliveryStatus.UNASSIGNED: [Order.DeliveryStatus.SCHEDULED],
        Order.DeliveryStatus.SCHEDULED: [Order.DeliveryStatus.SHIPPED, Order.DeliveryStatus.INCIDENT],
        Order.DeliveryStatus.SHIPPED: [Order.DeliveryStatus.DELIVERED, Order.DeliveryStatus.INCIDENT,
                                       Order.DeliveryStatus.RETURNED],
        Order.DeliveryStatus.INCIDENT: [Order.DeliveryStatus.SCHEDULED, Order.DeliveryStatus.RETURNED],
    },
}


def apply_transition(order, field, to_value, user=None, note=""):
    """Cambio de estado validado; registra quién hizo cada cambio (auditoría)."""
    allowed = TRANSITIONS.get(field, {}).get(getattr(order, field), [])
    if to_value not in [str(v) for v in allowed]:
        raise CartError(f"Transición no permitida: {field} → {to_value}.")
    from_value = getattr(order, field)
    if from_value == to_value:
        return order
    setattr(order, field, to_value)
    order.save(update_fields=[field])
    OrderEvent.objects.create(order=order, field=field, from_value=from_value,
                              to_value=to_value, note=note, by=user)
    return order
