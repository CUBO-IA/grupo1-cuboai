"""Outbox + correo transaccional (AC19): backend local REAL de prueba.

- Con correo habilitado y backend locmem, el evento se envía de verdad y
  queda DONE con resultado; el mensaje se ve en el capturador local.
- Sin habilitación, el evento queda BLOCKED con causa precisa, nunca DONE.
- Un backend que falla produce REINTENTO con backoff; agotados los
  reintentos, FAILED. Un claim vencido puede retomarse (recuperación).
"""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from reino import services_commerce as c
from reino.models import Order, OutboxEvent
from reino.tests import ReinoTestCase

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


class OutboxEmailTests(ReinoTestCase):
    def _order(self):
        v = self.product.variants.get(option_label="Talla M")
        cart = c.get_open_cart(self.store_a, "outbox-test", create=True)
        c.add_item(cart, v, 1)
        ch = c.prepare_checkout(cart, "manual", idempotency_key="outbox-test")
        return c.confirm_checkout(ch, {"name": "Correo", "email": "cliente@example.invalid"},
                                  ch.idempotency_key)

    def _run(self):
        call_command("process_outbox")

    @override_settings(REINO_EMAIL_ENABLED=True, EMAIL_BACKEND=LOCMEM)
    def test_email_sent_with_local_backend(self):
        order = self._order()  # crea el evento order_confirmation_email
        self._run()
        event = OutboxEvent.objects.get(type="order_confirmation_email")
        self.assertEqual(event.status, OutboxEvent.Status.DONE)
        self.assertIn("cliente@example.invalid", event.payload.get("result", ""))
        # El correo se VE en el capturador local (AC19):
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.reference, mail.outbox[0].subject)
        self.assertIn("pendiente de pago", mail.outbox[0].subject.lower())
        self.assertIn(order.reference, mail.outbox[0].body)

    @override_settings(REINO_EMAIL_ENABLED=False)
    def test_email_blocked_without_configuration(self):
        self._order()
        self._run()
        event = OutboxEvent.objects.get(type="order_confirmation_email")
        self.assertEqual(event.status, OutboxEvent.Status.BLOCKED)
        self.assertIn("no habilitado", event.last_error)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(REINO_EMAIL_ENABLED=True, EMAIL_BACKEND=LOCMEM)
    def test_backend_failure_retries_then_fails(self):
        self._order()
        with mock.patch("django.core.mail.send_mail", side_effect=OSError("smtp caído")):
            for _ in range(5):
                # Cada pasada simula el tiempo transcurrido (backoff vencido).
                OutboxEvent.objects.all().update(
                    available_at=timezone.now() - timedelta(seconds=1))
                self._run()
        event = OutboxEvent.objects.get(type="order_confirmation_email")
        self.assertEqual(event.status, OutboxEvent.Status.FAILED)
        self.assertIn("smtp caído", event.last_error)
        self.assertGreaterEqual(event.retries, 4)

    @override_settings(REINO_EMAIL_ENABLED=True, EMAIL_BACKEND=LOCMEM)
    def test_retry_with_backoff_becomes_available_later(self):
        self._order()
        with mock.patch("django.core.mail.send_mail", side_effect=OSError("caído")):
            self._run()  # primer intento: backoff
        event = OutboxEvent.objects.get(type="order_confirmation_email")
        self.assertEqual(event.status, OutboxEvent.Status.PENDING)
        self.assertIsNotNone(event.available_at)
        # Segunda pasada inmediata: no disponible todavía (backoff).
        self._run()
        event.refresh_from_db()
        self.assertEqual(event.status, OutboxEvent.Status.PENDING)
        # Vencido el backoff, reintenta y envía.
        OutboxEvent.objects.filter(pk=event.pk).update(
            available_at=timezone.now() - timedelta(seconds=1))
        self._run()
        event.refresh_from_db()
        self.assertEqual(event.status, OutboxEvent.Status.DONE)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(REINO_EMAIL_ENABLED=True, EMAIL_BACKEND=LOCMEM)
    def test_expired_claim_can_be_retaken(self):
        self._order()
        event = OutboxEvent.objects.get(type="order_confirmation_email")
        # Simular un worker muerto con el claim tomado y vencido.
        event.claim_token = "worker-muerto"
        event.claimed_until = timezone.now() - timedelta(seconds=5)
        event.save(update_fields=["claim_token", "claimed_until"])
        self._run()
        event.refresh_from_db()
        self.assertEqual(event.status, OutboxEvent.Status.DONE)

    def test_metric_event_is_recorded_once(self):
        OutboxEvent.objects.create(type="metric", payload={"event": "x"})
        self._run()
        self._run()
        event = OutboxEvent.objects.get(type="metric")
        self.assertEqual(event.status, OutboxEvent.Status.DONE)
        self.assertEqual(event.payload.get("result"), "recorded")
