"""Regresiones de la auditoría independiente del PR #3 (23-oct-2026).

Procedencia: documento «WIENER KINGDOM · Auditoría del PR #3 y encargo de
corrección para Fluso», sección 13, contra el commit 95df61f. Se integran
SIN cambiar su significado; cada caso fallaba en el commit auditado y debe
pasar tras la corrección por la razón correcta. IDs R01–R13 del informe.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings

from reino import services_commerce as c, services_memory as mem
from reino.ai import adapter, orchestrator
from reino.ai.tools import ToolContext, run_tool
from reino.models import (
    AIConversation, Consent, MerchantMember, Order, ShippingZone,
)
from reino.tests import ReinoTestCase
from reino.views_looklab import _reveal

CUSTOMER = {"name": "Audit", "email": "audit@example.invalid"}
AI = {"API_KEY": "fake-for-local-tests", "MAX_TOOL_ROUNDS": 4}


class AuditRegressions(ReinoTestCase):
    def profile_with_s(self):
        p = self._profile(self.store_a, session="audit")
        mem.grant_consent(self.store_a, "audit", Consent.Purpose.MEASUREMENTS, p)
        mem.save_measurement(p, chest_cm=36, neck_cm=24, back_cm=28)
        return p

    def new_checkout(self, key="audit-order"):
        v = self.product.variants.get(option_label="Talla M")
        cart = c.get_open_cart(self.store_a, key, create=True)
        c.add_item(cart, v, 1)
        ch = c.prepare_checkout(cart, "manual", idempotency_key=key)
        return v, cart, ch

    def test_01_revoked_measurements_must_not_enter_model_context(self):
        p = self.profile_with_s()
        mem.revoke_consent(self.store_a, "audit", Consent.Purpose.MEASUREMENTS, p)
        context = orchestrator._memory_context(ToolContext(self.store_a, "audit", p))
        self.assertNotIn("pecho 36", context)

    def test_02_total_budget_must_limit_entire_look(self):
        result = _reveal(None, self.store_a, {"budget": "100", "budget_scope": "total",
                                              "occasion": "celebracion"}, None)
        self.assertLessEqual(result["selection_total"], Decimal("100"))

    def test_03_no_other_size_when_compatible_size_sold_out(self):
        p = self.profile_with_s()
        self.product.variants.filter(option_label="Talla S").update(stock=0)
        result = _reveal(None, self.store_a, {"occasion": "paseo"}, p)
        rows = [x for x in result["selection"] if x["product"].pk == self.product.pk]
        self.assertEqual(rows, [], "S sold out but another size is offered as compatible")

    def test_04_new_temporary_measurements_override_old_saved_measurements(self):
        p = self.profile_with_s()
        result = _reveal(None, self.store_a,
                         {"occasion": "paseo",
                          "converted": {"chest": "43", "neck": "29", "back": "35"},
                          "measurement_saved": False}, p)
        row = next(x for x in result["selection"] if x["product"].pk == self.product.pk)
        self.assertEqual(row["variant"].option_label, "Talla M")

    @override_settings(REINO_AI=AI)
    def test_05_model_cannot_add_cart_without_buyer_authorization(self):
        variant = self.product.variants.get(option_label="Talla M")
        conv = AIConversation.objects.create(store=self.store_a, session_key="audit")
        first = {"role": "assistant", "content": None,
                 "tool_calls": [{"id": "x", "type": "function",
                                 "function": {"name": "add_item_to_cart",
                                              "arguments": '{"variant_id":"' + str(variant.public_id) + '","quantity":1}'}}]}
        last = {"role": "assistant", "content": "Listo"}
        with mock.patch.object(adapter, "chat", side_effect=[first, last]):
            orchestrator.respond(conv, "¿Qué materiales tiene?", ToolContext(self.store_a, "audit"))
        cart = c.get_open_cart(self.store_a, "audit")
        self.assertTrue(cart is None or cart.items.count() == 0)

    @override_settings(REINO_AI=AI)
    def test_06_unbacked_model_prices_and_promises_are_rejected(self):
        conv = AIConversation.objects.create(store=self.store_a, session_key="audit")
        fake = "El arnés cuesta $1.00 y su entrega hoy está garantizada."
        with mock.patch.object(adapter, "chat", return_value={"role": "assistant", "content": fake}):
            reply = orchestrator.respond(conv, "¿Cuánto cuesta y cuándo llega?", ToolContext(self.store_a, "audit"))
        self.assertNotEqual(reply["answer_text"], fake)

    def test_07_duplicate_ai_action_must_not_double_quantity(self):
        # Preparación corregida (revisión 2, §3): se EMITE una propuesta real
        # y luego se repite su confirmación; un identificador inventado jamás
        # constituye autorización.
        v = self.product.variants.get(option_label="Talla M")
        ctx = ToolContext(self.store_a, "audit")
        token = orchestrator._propose_action("add_item_to_cart", {
            "variant_id": str(v.public_id), "quantity": 1}, ctx)
        args = {"action_id": token.action_id}
        run_tool("add_item_to_cart", args, ctx)
        run_tool("add_item_to_cart", args, ctx)
        self.assertEqual(c.get_open_cart(self.store_a, "audit").items.get().quantity, 1)

    def test_08_cancel_unpaid_order_releases_stock_once(self):
        v, cart, ch = self.new_checkout()
        initial = v.stock
        order = c.confirm_checkout(ch, CUSTOMER, "audit-order")
        c.apply_transition(order, "status", "cancelled")
        v.refresh_from_db()
        self.assertEqual(v.stock, initial)

    def test_09_same_sku_two_recipients_respects_total_stock(self):
        v = self.product.variants.get(option_label="Talla M")
        v.stock = 1
        v.save()
        cart = c.get_open_cart(self.store_a, "audit", create=True)
        c.add_item(cart, v, 1, recipient=self._profile(self.store_a, session="audit", alias="A"))
        c.add_item(cart, v, 1, recipient=self._profile(self.store_a, session="audit", alias="B"))
        with self.assertRaises(c.StockConflict):
            c.prepare_checkout(cart, "manual", idempotency_key="two-recipients")

    def test_10_edit_delivery_requires_new_current_summary(self):
        self.client.get(f"/s/{self.store_a.slug}/")
        cart = c.get_open_cart(self.store_a, self.client.session.session_key, create=True)
        c.add_item(cart, self.product.variants.get(option_label="Talla M"), 1)
        url = f"/s/{self.store_a.slug}/checkout/"
        form = {"step": "review", "name": "Audit", "email": "a@example.invalid",
                "delivery_mode": "pickup", "payment_method": "manual", "idempotency_key": "audit-ui"}
        self.client.post(url, form)
        zone = ShippingZone.objects.get(store=self.store_a, mode="local")
        form.update(payment_method="bitcoin", delivery_mode="local", zone=zone.name,
                    address="Example street")
        response = self.client.post(url, form)
        edited = response.context["session"]
        self.assertEqual(edited.summary["payment_method"], "bitcoin")
        self.assertEqual(edited.summary["shipping"], "3.50")

    def test_11_logistics_role_cannot_mark_payment_paid(self):
        v, cart, ch = self.new_checkout()
        order = c.confirm_checkout(ch, CUSTOMER, "audit-order")
        user = User.objects.create_user(username="local-logistics", password="local-only", is_staff=True)
        MerchantMember.objects.create(user=user, merchant=self.merchant_a, role="logistics")
        self.client.force_login(user)
        self.client.post(f"/negocio/{self.store_a.slug}/pedidos/{order.public_id}/transicion/",
                         {"field": "payment_status", "to": "paid"})
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")

    def test_12_scope_idempotency_to_current_cart(self):
        self.client.get(f"/s/{self.store_a.slug}/")
        session_key = self.client.session.session_key
        cart = c.get_open_cart(self.store_a, session_key, create=True)
        c.add_item(cart, self.product.variants.get(option_label="Talla M"), 1)
        other = c.get_open_cart(self.store_b, session_key, create=True)
        c.add_item(other, self.product_b.variants.first(), 1)
        form = {"step": "review", "name": "Audit", "email": "a@example.invalid",
                "delivery_mode": "pickup", "payment_method": "manual", "idempotency_key": "audit-a"}
        self.client.post(f"/s/{self.store_a.slug}/checkout/", form)
        form["idempotency_key"] = "audit-b"
        response = self.client.post(f"/s/{self.store_b.slug}/checkout/", form)
        self.assertEqual(response.context["session"].cart_id, other.pk)

    def test_13_delivery_cannot_use_pickup_zone_for_free_shipping(self):
        self.client.get(f"/s/{self.store_a.slug}/")
        cart = c.get_open_cart(self.store_a, self.client.session.session_key, create=True)
        c.add_item(cart, self.product.variants.get(option_label="Talla M"), 1)
        form = {"step": "review", "name": "Audit", "email": "a@example.invalid",
                "delivery_mode": "local", "zone": "Retiro", "address": "Example street",
                "payment_method": "manual", "idempotency_key": "wrong-zone"}
        response = self.client.post(url := f"/s/{self.store_a.slug}/checkout/", form)
        self.assertIsNone(response.context.get("session"), "Local delivery accepted with pickup tariff")

    def test_14_bitcoin_discount_preserves_historical_eligibility(self):
        from tienda.models import ProductPaymentRule
        self.product.legacy_slug = "beige-anti-rub-harness"
        self.product.save()
        rule = ProductPaymentRule.objects.get(product_slug=self.product.legacy_slug)
        self.assertFalse(rule.bitcoin_discount_eligible)
        v, cart, ch = self.new_checkout()
        summary = c.cart_summary(cart, "bitcoin")
        self.assertEqual(summary["discount"], Decimal("0"))
