"""Servicio de cobros por tienda (§11): intentos, estados, notificaciones,
conciliación y reembolsos — con efectos de dominio exactamente una vez.

Reglas duras:
- Un carrito global se cobra por tienda: «2 tiendas, 2 pagos» (§11.1); un
  grupo parcialmente pagado NUNCA se muestra como pagado completo.
- El retorno web muestra estado y consulta; jamás declara éxito por un
  parámetro success=true. La confirmación viene de notificación verificada
  y/o consulta autenticada que valida cuenta, pedido, referencia, importe
  y moneda.
- Efectos (marcar pagado, habilitar descargas, preparar) una sola vez por
  intento: el estado CAPTURED se aplica idempotentemente bajo bloqueo.
- Reintentos y webhooks duplicados/fuera de orden no duplican efectos ni
  retroceden estados (REFUNDED no vuelve a PENDING).
"""

from django.db import transaction
from django.utils import timezone

from . import services_commerce as commerce
from .models import Order, PaymentAttempt, PaymentEvent
from .payments.fake import FakeAdapter
from .payments.manual import ManualAdapter

ADAPTERS = {a.key: a for a in (FakeAdapter(), ManualAdapter())}
FINAL_STATES = {PaymentAttempt.State.CANCELLED, PaymentAttempt.State.EXPIRED,
                PaymentAttempt.State.FAILED}
NO_REGRESS = {PaymentAttempt.State.REFUNDED, PaymentAttempt.State.DISPUTED,
              PaymentAttempt.State.PARTIALLY_REFUNDED, PaymentAttempt.State.CAPTURED}


def adapter_for(provider):
    adapter = ADAPTERS.get(provider)
    if adapter is None:
        raise commerce.CartError("Método de pago no disponible.")
    return adapter


def create_attempt(order, provider, idempotency_key, environment="test",
                   account_ref=""):
    """Registra un intento específico; idempotente por clave (§11.4.4)."""
    adapter = adapter_for(provider)
    with transaction.atomic():
        attempt, created = PaymentAttempt.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={"order": order, "provider": provider,
                      "amount": order.total, "currency": order.store.currency,
                      "environment": environment, "account_ref": account_ref,
                      "state": PaymentAttempt.State.CREATED})
    if not created:
        return attempt, None
    response = adapter.create_payment(attempt)
    if not response.ok:
        attempt.state = PaymentAttempt.State.FAILED
        attempt.provider_state = response.error[:60]
        attempt.save(update_fields=["state", "provider_state", "updated_at"])
        return attempt, response.error
    attempt.state = response.state or PaymentAttempt.State.PENDING
    attempt.external_ref = response.external_ref
    attempt.redirect_url = response.redirect_url
    attempt.qr_payload = response.qr_payload
    attempt.provider_state = response.provider_state
    attempt.save()
    return attempt, None


def _apply_effects_once(attempt, user=None):
    """Efectos de dominio del cobro confirmado, UNA sola vez (§11.4.8)."""
    order = attempt.order
    if order.payment_status != Order.PaymentStatus.PAID:
        commerce.apply_transition(order, "payment_status", "paid",
                                  note=f"Cobro confirmado ({attempt.provider} "
                                       f"{attempt.external_ref})", user=user)


def apply_provider_state(attempt, new_state, provider_state="", event_id="",
                         user=None):
    """Aplica un estado del proveedor con reglas de no-retroceso (A46).

    Devuelve (attempt, changed). Un estado final no se reescribe; un evento
    duplicado se deduplica por (attempt, event_id, kind).
    """
    with transaction.atomic():
        locked = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        if event_id:
            PaymentEvent.objects.get_or_create(
                attempt=locked, provider_event_id=event_id, kind="provider",
                defaults={"payload": {"state": new_state, "provider_state": provider_state}})
        if locked.state in NO_REGRESS and new_state not in (
                PaymentAttempt.State.REFUNDED, PaymentAttempt.State.PARTIALLY_REFUNDED,
                PaymentAttempt.State.DISPUTED, PaymentAttempt.State.REFUND_PENDING):
            return locked, False  # los estados terminales no retroceden
        if locked.state == new_state:
            return locked, False
        locked.state = new_state
        if provider_state:
            locked.provider_state = provider_state[:60]
        locked.save(update_fields=["state", "provider_state", "updated_at"])
    if new_state == PaymentAttempt.State.CAPTURED:
        locked.order.refresh_from_db()
        _apply_effects_once(locked, user=user)
    elif new_state in (PaymentAttempt.State.REFUNDED,
                       PaymentAttempt.State.PARTIALLY_REFUNDED,
                       PaymentAttempt.State.DISPUTED):
        # El proveedor reportó devolución/disputa: el pedido la refleja con
        # evidencia; el dinero real lo concilia refund_attempt o la operación.
        locked.order.refresh_from_db()
        target = {"refunded": "refunded", "partially_refunded": "partially_refunded",
                  "disputed": "disputed"}[new_state]
        if locked.order.payment_status != target:
            commerce.apply_transition(
                locked.order, "payment_status", target,
                note=f"Reportado por {locked.provider} ({locked.external_ref})",
                user=user,
                refund_amount=locked.refunded_amount or locked.captured_amount
                or locked.amount)
    return locked, True


def verify_and_apply_notification(provider, headers, raw_body, parsed):
    """Webhook: autenticidad + coincidencia estricta antes de tocar estados
    (A45): pedido, referencia, importe, moneda y cuenta deben coincidir."""
    adapter = adapter_for(provider)
    if not adapter.verify_notification(headers, raw_body):
        return None, "firma inválida"
    ref = str(parsed.get("external_ref") or "")
    attempt = PaymentAttempt.objects.filter(external_ref=ref, provider=provider).first()
    if attempt is None:
        return None, "referencia desconocida"
    if str(parsed.get("amount")) not in ("", str(attempt.amount)) or \
            (parsed.get("currency") and parsed["currency"] != attempt.currency):
        return None, "monto o moneda no coinciden"
    return attempt, None


def reconcile_attempt(attempt, user=None):
    """Recuperación sin retorno/webhook: consulta autenticada y aplica (A47)."""
    adapter = adapter_for(attempt.provider)
    response = adapter.get_payment(attempt)
    if not response.ok:
        return attempt, response.error
    if response.state != attempt.state:
        return apply_provider_state(attempt, response.state,
                                    response.provider_state, user=user)[0], None
    return attempt, None


def refund_attempt(attempt, amount=None, note="", user=None, member=None):
    """Reembolso total/parcial con límites (A48): nunca por encima de lo
    capturado menos lo ya devuelto; manual queda pendiente con evidencia."""
    if attempt.state not in (PaymentAttempt.State.CAPTURED,
                             PaymentAttempt.State.PARTIALLY_REFUNDED):
        raise commerce.CartError("Sólo se reembolsa un cobro confirmado.")
    amount = amount if amount is not None else attempt.captured_amount or attempt.amount
    remaining = (attempt.captured_amount or attempt.amount) - attempt.refunded_amount
    if amount <= 0 or amount > remaining:
        raise commerce.CartError("El reembolso excede lo cobrado disponible.")
    adapter = adapter_for(attempt.provider)
    response = adapter.refund(attempt, amount=amount, note=note)
    if not response.ok:
        raise commerce.CartError(response.error)
    with transaction.atomic():
        locked = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        locked.refunded_amount += amount
        locked.state = (PaymentAttempt.State.REFUNDED
                        if locked.refunded_amount >= (locked.captured_amount or locked.amount)
                        else PaymentAttempt.State.PARTIALLY_REFUNDED)
        locked.save(update_fields=["refunded_amount", "state", "updated_at"])
    # Estado del pedido: reembolso total/parcial con evidencia (R04/R13).
    order = attempt.order
    order.refresh_from_db()
    commerce.apply_transition(
        order, "payment_status",
        "refunded" if locked.state == PaymentAttempt.State.REFUNDED
        else "partially_refunded",
        note=note or f"Reembolso {attempt.provider} {attempt.external_ref}",
        user=user, member=member, refund_amount=amount)
    return locked


def group_payment_status(orders):
    """«2 tiendas, 2 pagos» (A49): el grupo sólo está pagado si TODOS lo
    están; el comprador ve cada pedido y su importe por separado."""
    for o in orders:
        o.refresh_from_db()
    parts = [{"order": o.reference, "total": str(o.total),
              "payment_status": o.payment_status} for o in orders]
    all_paid = bool(orders) and all(o.payment_status == Order.PaymentStatus.PAID for o in orders)
    return {"parts": parts, "all_paid": all_paid,
            "count": len(orders)}
