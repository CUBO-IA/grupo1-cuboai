"""G4 · Pagos (A42–A50 a nivel de contrato LOCAL con adaptador fake marcado;
la verificación EXTERNA con sandbox real queda como bloqueo documentado)."""

from reino import services_commerce as c
from reino import services_payments as pay
from reino.models import PaymentAttempt
from reino.tests import ReinoTestCase


class PaymentBase(ReinoTestCase):
    def _order(self, session="pay-1"):
        cart = c.get_open_cart(self.store_a, session, create=True)
        c.add_item(cart, self.product.variants.get(option_label="Talla M"), 1)
        ch = c.prepare_checkout(cart, "manual", idempotency_key=session)
        return c.confirm_checkout(ch, {"name": "P", "email": "p@e.invalid"},
                                  ch.idempotency_key)


class AttemptLifecycleTests(PaymentBase):
    def test_crear_intento_idempotente(self):
        order = self._order()
        a1, _ = pay.create_attempt(order, "fake", "idem-1")
        a2, _ = pay.create_attempt(order, "fake", "idem-1")
        self.assertEqual(a1.pk, a2.pk)
        self.assertEqual(PaymentAttempt.objects.count(), 1)
        self.assertEqual(a1.state, "requires_action")

    def test_captura_aplica_efectos_una_sola_vez(self):
        order = self._order()
        attempt, _ = pay.create_attempt(order, "fake", "idem-2")
        pay.apply_provider_state(attempt, "captured", event_id="ev-1")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        # Webhook duplicado: no duplica efectos ni eventos.
        pay.apply_provider_state(attempt, "captured", event_id="ev-1")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.events.filter(to_value="paid").count(), 1)

    def test_estado_final_no_retrocede(self):
        order = self._order()
        attempt, _ = pay.create_attempt(order, "fake", "idem-3")
        pay.apply_provider_state(attempt, "captured")
        attempt, changed = pay.apply_provider_state(attempt, "pending")
        self.assertFalse(changed)
        self.assertEqual(attempt.state, "captured")

    def test_fuera_de_orden_se_admite_sin_retroceder(self):
        order = self._order()
        attempt, _ = pay.create_attempt(order, "fake", "idem-4")
        pay.apply_provider_state(attempt, "captured")
        pay.apply_provider_state(attempt, "refunded")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "refunded")
        attempt, changed = pay.apply_provider_state(attempt, "captured")
        self.assertFalse(changed, "un reembolso no vuelve a capturado")

    def test_reembolso_parcial_y_total_con_limites(self):
        order = self._order()
        attempt, _ = pay.create_attempt(order, "fake", "idem-5")
        pay.apply_provider_state(attempt, "captured")
        attempt.refresh_from_db()
        attempt.captured_amount = attempt.amount
        attempt.save()
        pay.refund_attempt(attempt, amount=20, note="devolución parcial")
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "partially_refunded")
        with self.assertRaises(c.CartError):
            pay.refund_attempt(attempt, amount=999, note="exceso")
        pay.refund_attempt(attempt, amount=attempt.amount - 20, note="resto")
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "refunded")

    def test_metodo_no_conectado_no_se_ofrece(self):
        with self.assertRaises(c.CartError):
            pay.create_attempt(self._order("pay-x"), "paypal", "idem-x")


class WebhookTests(PaymentBase):
    def test_firma_invalida_no_cambia_estado(self):
        order = self._order("wh-1")
        attempt, _ = pay.create_attempt(order, "fake", "wh-1")
        attempt2, err = pay.verify_and_apply_notification(
            "fake", {"X-Fake-Signature": "mala"}, b"{}", {"external_ref": attempt.external_ref})
        self.assertEqual(err, "firma inválida")
        self.assertIsNone(attempt2)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "requires_action")

    def test_monto_incorrecto_rechazado(self):
        order = self._order("wh-2")
        attempt, _ = pay.create_attempt(order, "fake", "wh-2")
        attempt, err = pay.verify_and_apply_notification(
            "fake", {"X-Fake-Signature": "firma-de-prueba"}, b"{}",
            {"external_ref": attempt.external_ref, "amount": "1.00"})
        self.assertEqual(err, "monto o moneda no coinciden")

    def test_notificacion_valida_confirma(self):
        order = self._order("wh-3")
        attempt, _ = pay.create_attempt(order, "fake", "wh-3")
        attempt, err = pay.verify_and_apply_notification(
            "fake", {"X-Fake-Signature": "firma-de-prueba"}, b"{}",
            {"external_ref": attempt.external_ref, "amount": str(attempt.amount),
             "currency": "USD"})
        self.assertIsNone(err)
        pay.apply_provider_state(attempt, "captured", event_id="ev-wh")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")


class ReconcileAndGroupTests(PaymentBase):
    def test_conciliacion_recupera_estado(self):
        order = self._order("rec-1")
        attempt, _ = pay.create_attempt(order, "fake", "rec-1")
        attempt, err = pay.reconcile_attempt(attempt)
        self.assertIsNone(err)

    def test_grupo_dos_tiendas_dos_pagos(self):
        o1 = self._order("grp-1")
        cart = c.get_open_cart(self.store_b, "grp-2", create=True)
        c.add_item(cart, self.product_b.variants.get(), 1)
        ch = c.prepare_checkout(cart, "manual", idempotency_key="grp-2")
        o2 = c.confirm_checkout(ch, {"name": "G", "email": "g@e.invalid"}, ch.idempotency_key)
        group = pay.group_payment_status([o1, o2])
        self.assertEqual(group["count"], 2)
        self.assertFalse(group["all_paid"])  # parcial NUNCA se muestra pagado
        c.apply_transition(o1, "payment_status", "paid", note="T-1")
        c.apply_transition(o2, "payment_status", "paid", note="T-2")
        group = pay.group_payment_status([o1, o2])
        self.assertTrue(group["all_paid"])
