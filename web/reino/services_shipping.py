"""Servicio de envíos (§12): cotización vigente, creación idempotente,
despachos parciales sin doble despacho, tracking deduplicado y estados
coherentes. El flujo manual es completo; los adaptadores API se enchufan por
contrato sin tocar checkout (§12.3).
"""

from django.db import transaction
from django.utils import timezone

from . import services_commerce as commerce
from .models import Order, OrderEvent, Shipment, ShipmentEvent
from .shipping.manual import ManualShipping

ADAPTERS = {a.key: a for a in (ManualShipping(),)}

# «Etiqueta creada» no significa «en camino» (§12.4.9): orden de estados.
STATUS_ORDER = [Shipment.Status.PREPARING, Shipment.Status.READY,
                Shipment.Status.LABEL_CREATED, Shipment.Status.PICKED_UP,
                Shipment.Status.IN_TRANSIT, Shipment.Status.DELIVERED]


def adapter_for(provider):
    adapter = ADAPTERS.get(provider)
    if adapter is None:
        raise commerce.CartError("Proveedor de envío no disponible.")
    return adapter


def shipped_quantities(order):
    """Unidades ya despachadas por línea (impide doble despacho, §12.4)."""
    totals = {}
    for shipment in order.shipments.exclude(status=Shipment.Status.CANCELLED):
        for line in shipment.lines:
            totals[line["order_item_id"]] = totals.get(line["order_item_id"], 0) + line["quantity"]
    return totals


def shippable_lines(order):
    """Líneas FÍSICAS pendientes por despachar (digital/servicio no llevan
    paquete). Devuelve [{item, pending}]."""
    shipped = shipped_quantities(order)
    pending = []
    for item in order.items.select_related("variant__product"):
        if item.variant and item.variant.product.offer_type != "physical":
            continue
        left = item.quantity - shipped.get(item.pk, 0)
        if left > 0:
            pending.append({"item": item, "pending": left})
    return pending


def create_shipment(order, lines=None, provider="manual", service="",
                    user=None, address=None):
    """Crea un envío de forma idempotente: mismas líneas pendientes + mismo
    proveedor = el envío existente, nunca uno duplicado (A54)."""
    adapter = adapter_for(provider)
    if lines is None:
        lines = [{"order_item_id": p["item"].pk, "quantity": p["pending"]}
                 for p in shippable_lines(order)]
    if not lines:
        # Idempotencia ante doble clic tras despachar todo: si un envío vivo
        # cubre TODAS las líneas físicas, devolverlo (A54); si no, explicar.
        physical_ids = {i.pk for i in order.items.all()
                        if i.variant and i.variant.product.offer_type == "physical"}
        covered = set()
        for sh in order.shipments.exclude(status=Shipment.Status.CANCELLED):
            covered |= {l["order_item_id"] for l in sh.lines}
        if physical_ids and physical_ids <= covered:
            return order.shipments.exclude(
                status=Shipment.Status.CANCELLED).first()
        raise commerce.CartError("No quedan unidades físicas por despachar.")
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        shipped = shipped_quantities(locked)
        for line in lines:
            item = locked.items.get(pk=line["order_item_id"])
            left = item.quantity - shipped.get(item.pk, 0)
            if line["quantity"] < 1 or line["quantity"] > left:
                raise commerce.CartError(
                    f"No podés despachar {line['quantity']} de «{item.title}»: "
                    f"quedan {left}.")
        existing = locked.shipments.exclude(status=Shipment.Status.CANCELLED).filter(
            provider=provider, lines=lines).first()
        if existing:
            return existing  # idempotente
        shipment = Shipment.objects.create(
            order=locked, provider=provider, service=service,
            amount=locked.shipping_amount or 0, currency=locked.store.currency,
            lines=lines, address_snapshot=address or {})
    response = adapter.create_shipment(shipment)
    if not response.ok:
        raise commerce.CartError(response.error)
    shipment.external_ref = response.external_ref
    shipment.status = Shipment.Status.PREPARING
    shipment.save(update_fields=["external_ref", "status", "updated_at"])
    OrderEvent.objects.create(
        order=order, field="shipment", to_value=f"envío-{shipment.pk}",
        note=f"Envío {shipment.public_id} creado ({provider}, {len(lines)} línea/s)", by=user)
    return shipment


def mark_status(shipment, status, user=None, note="", event_id="",
                occurred_at=None):
    """Transición de estado del envío con reglas (A55/A56):

    - Sin retroceso en la línea de tiempo (DELIVERED no vuelve a IN_TRANSIT).
    - Eventos de tracking deduplicados por (event_id, code).
    - «Etiqueta creada» no implica recogido; entregado exige su evento.
    """
    with transaction.atomic():
        locked = Shipment.objects.select_for_update().get(pk=shipment.pk)
        if event_id:
            ShipmentEvent.objects.get_or_create(
                shipment=locked, provider_event_id=event_id, code=status,
                defaults={"occurred_at": occurred_at or timezone.now(),
                          "detail": note[:200]})
        current, target = locked.status, status
        if current in (Shipment.Status.DELIVERED, Shipment.Status.RETURNED,
                       Shipment.Status.CANCELLED) and target != current:
            return locked, False  # finales no retroceden
        if current == target:
            return locked, False
        if current in STATUS_ORDER and target in STATUS_ORDER and \
                STATUS_ORDER.index(target) < STATUS_ORDER.index(current):
            # Fuera de orden: se registra el evento pero el estado no retrocede.
            return locked, False
        locked.status = target
        locked.save(update_fields=["status", "updated_at"])
    return locked, True


def record_tracking(shipment, code, detail="", event_id="", occurred_at=None):
    """Registra un evento de tracking; duplicados = no-op exacto (A55)."""
    event, created = ShipmentEvent.objects.get_or_create(
        shipment=shipment, provider_event_id=event_id or f"local-{code}-{detail[:20]}",
        code=code,
        defaults={"occurred_at": occurred_at or timezone.now(),
                  "detail": detail[:200]})
    return event, created


def reconcile_before_retry(shipment, user=None):
    """Timeout al crear etiqueta/envío: CONSULTAR referencia antes de comprar
    otra (A54). Devuelve (shipment, estado_conocido)."""
    adapter = adapter_for(shipment.provider)
    response = adapter.track(shipment)
    if not response.ok:
        return shipment, None
    if response.state and response.state != shipment.status:
        mark_status(shipment, response.state, user=user,
                    note="Reconciliación tras timeout")
    return shipment, response.state
