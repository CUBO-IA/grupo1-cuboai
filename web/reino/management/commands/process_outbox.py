"""Consumidor del outbox: trabajos diferidos recuperables (revisión 2, §18).

- Claim con vencimiento: cada worker reclama la fila (token + claimed_until)
  en una transacción CORTA y ejecuta la llamada externa FUERA del bloqueo.
  Si el proceso cae después del envío y antes de persistir, el evento vuelve
  a ser reclamable (entrega al menos una vez, documentada; con proveedor que
  soporte idempotencia se envía una clave estable).
- Correo transaccional REAL con backend configurable (django.core.mail):
  plantilla propia, destinatario del pedido, resultado observable. Sin
  configuración habilitada el evento queda BLOCKED con causa precisa; jamás
  marcado como enviado (AC19).
- Reintentos con backoff exponencial acotado y conteos exactos.

Uso:  python manage.py process_outbox [--loop SEGUNDOS]
"""

import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.utils import timezone

from reino.models import Order, OutboxEvent

MAX_RETRIES = 4
CLAIM_SECONDS = 60
BACKOFF_BASE_SECONDS = 30


class Command(BaseCommand):
    help = "Procesa eventos diferidos del outbox (correo, métricas) de forma idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--loop", type=int, default=0,
                            help="Reejecutar cada N segundos (0 = una sola pasada).")

    def handle(self, *args, **options):
        while True:
            done, failed, blocked, claimed = self._pass()
            self.stdout.write(
                f"outbox: {done} procesados, {failed} fallidos, "
                f"{blocked} bloqueados, {claimed} reclamados por otro worker")
            if not options["loop"]:
                return
            time.sleep(options["loop"])

    # --------------------------------------------------------------- cola --
    def _claim(self):
        """Reclama UN evento disponible con token y vencimiento."""
        now = timezone.now()
        with transaction.atomic():
            event = (OutboxEvent.objects
                     .select_for_update(skip_locked=True)
                     .filter(status=OutboxEvent.Status.PENDING)
                     .filter(models.Q(available_at__isnull=True)
                             | models.Q(available_at__lte=now))
                     .filter(models.Q(claimed_until__isnull=True)
                             | models.Q(claimed_until__lt=now))
                     .order_by("pk").first())
            if event is None:
                return None
            event.claim_token = uuid.uuid4().hex[:24]
            event.claimed_until = now + timedelta(seconds=CLAIM_SECONDS)
            event.save(update_fields=["claim_token", "claimed_until"])
            return event

    def _pass(self):
        done = failed = blocked = claimed = 0
        while True:
            event = self._claim()
            if event is None:
                return done, failed, blocked, claimed
            outcome, detail = self._dispatch(event)
            event.refresh_from_db()
            if outcome == "done":
                event.status = OutboxEvent.Status.DONE
                event.processed_at = timezone.now()
                event.payload["result"] = detail
                done += 1
            elif outcome == "blocked":
                # Sin proveedor/configuración: estado PRECISO, no «enviado».
                event.status = OutboxEvent.Status.BLOCKED
                event.last_error = detail[:200]
                blocked += 1
            else:  # retry / failed
                event.retries += 1
                event.last_error = detail[:200]
                if event.retries >= MAX_RETRIES:
                    event.status = OutboxEvent.Status.FAILED
                    failed += 1
                else:
                    delay = BACKOFF_BASE_SECONDS * (2 ** (event.retries - 1))
                    event.available_at = timezone.now() + timedelta(seconds=delay)
                    claimed += 1
            event.claim_token = ""
            event.claimed_until = None
            event.save()

    # ------------------------------------------------------------ envío ---
    def _dispatch(self, event):
        """Devuelve (outcome, detalle): done | blocked | retry."""
        if event.type == "order_confirmation_email":
            return self._send_order_confirmation(event)
        if event.type == "metric":
            return "done", "recorded"
        return "blocked", f"tipo desconocido: {event.type}"

    def _send_order_confirmation(self, event):
        if not settings.REINO_EMAIL_ENABLED:
            return "blocked", "correo transaccional no habilitado (REINO_EMAIL_ENABLED=0)"
        order = Order.objects.filter(
            public_id=event.payload.get("order_id")).first()
        if order is None:
            return "retry", "pedido no encontrado"
        if not order.customer_email:
            return "blocked", "el pedido no tiene correo del comprador"

        from django.core.mail import send_mail
        subject = f"Tu pedido {order.reference} está pendiente de pago"
        lines = [
            f"Hola {order.customer_name},",
            "",
            f"Recibimos tu pedido {order.reference} en {order.store.name}.",
            f"Total: {order.total} {order.currency}.",
            "",
            "Estado: PENDIENTE DE PAGO. El pedido se confirma cuando el negocio",
            "verifique tu pago con la evidencia correspondiente.",
            "",
            "Piezas:",
        ]
        for item in order.items.all():
            lines.append(f"· {item.title} {item.option_label} ×{item.quantity} — "
                         f"{item.subtotal} {order.currency}")
        lines += ["", f"Seguimiento privado: /s/{order.store.slug}/pedido/"
                       f"{order.public_id}/{order.access_token}/",
                  "", "— Enviado por la plataforma Reino Commerce"]
        try:
            sent = send_mail(subject, "\n".join(lines),
                             settings.DEFAULT_FROM_EMAIL, [order.customer_email],
                             fail_silently=False)
        except Exception as exc:  # fallo recuperable: reintento con backoff
            return "retry", f"error del backend de correo: {exc}"[:200]
        if sent != 1:
            return "retry", "el backend no confirmó el envío"
        return "done", f"enviado a {order.customer_email}"

