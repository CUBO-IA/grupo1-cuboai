"""Revisión independiente 2 · sondas N01–N11 (apéndice §26 del encargo).

Estas pruebas expresan el comportamiento deseado. Fallaban en daf4600 (11/11).
"""
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone

from reino import services_commerce as c, services_memory as mem
from reino.ai import adapter, orchestrator
from reino.ai.tools import ToolContext, run_tool
from reino.models import AIMessage, Consent, MerchantMember, Order, StockReservation
from reino.tests import ReinoTestCase


class RoundTwoProbes(ReinoTestCase):
    def variant(self):
        return self.product.variants.get(option_label="Talla M")

    def checkout_fixture(self, key="audit2"):
        v = self.variant()
        cart = c.get_open_cart(self.store_a, key, create=True)
        c.add_item(cart, v, 1)
        ch = c.prepare_checkout(cart, "manual", idempotency_key=key)
        return v, cart, ch

    def test_01_confirm_advisor_proposal_has_successful_http_response(self):
        self.client.get(f"/s/{self.store_a.slug}/asesor/")
        key = self.client.session.session_key
        token = orchestrator._propose_action("add_item_to_cart", {
            "variant_id": str(self.variant().public_id), "quantity": 1,
        }, ToolContext(self.store_a, key))
        self.client.raise_request_exception = False
        response = self.client.post(f"/s/{self.store_a.slug}/asesor/accion/",
                                    {"action_id": token.action_id})
        self.assertEqual(c.get_open_cart(self.store_a, key).items.get().quantity, 1)
        self.assertEqual(response.status_code, 302,
                         f"Action mutated cart but HTTP failed: {response.status_code}")

    def test_02_edited_review_can_actually_be_confirmed(self):
        url = f"/s/{self.store_a.slug}/checkout/"
        self.client.get(url)
        key = self.client.session.session_key
        cart = c.get_open_cart(self.store_a, key, create=True)
        c.add_item(cart, self.variant(), 1)
        form = {"step": "review", "name": "Audit", "email": "audit@example.invalid",
                "delivery_mode": "pickup", "payment_method": "manual",
                "idempotency_key": "round2-review"}
        first = self.client.post(url, form)
        self.assertEqual(first.status_code, 200)
        changed = self.client.post(url, dict(form, payment_method="bitcoin"))
        reviewed = changed.context["session"]
        result = self.client.post(url, dict(form, payment_method="bitcoin", step="confirm",
                                            session_id=str(reviewed.public_id)))
        self.assertEqual(Order.objects.count(), 1,
                         f"Confirmed edited review returns HTTP {result.status_code} with no order")
        self.assertEqual(result.status_code, 302)

    def test_03_expired_review_is_replaced_by_valid_reservation(self):
        _, cart, checkout = self.checkout_fixture()
        expired = timezone.now() - timedelta(minutes=1)
        checkout.expires_at = expired
        checkout.save(update_fields=["expires_at"])
        StockReservation.objects.filter(checkout=checkout).update(expires_at=expired)
        renewed = c.prepare_checkout(cart, "manual", idempotency_key="audit2")
        self.assertGreater(renewed.expires_at, timezone.now(), "Expired checkout reused forever")

    def test_04_separate_order_instances_do_not_restock_twice(self):
        v, _, checkout = self.checkout_fixture()
        initial_stock = v.stock
        order = c.confirm_checkout(checkout, {"name": "Audit", "email": "a@example.invalid"},
                                   checkout.idempotency_key)
        second_request_order = Order.objects.get(pk=order.pk)
        c.apply_transition(order, "status", "cancelled")
        c.apply_transition(second_request_order, "status", "cancelled")
        v.refresh_from_db()
        self.assertEqual(v.stock, initial_stock, "Two previously loaded requests over-restock")

    def test_05_unknown_action_id_does_not_create_authorization(self):
        result = run_tool("add_item_to_cart", {
            "action_id": "not-issued-or-approved", "variant_id": str(self.variant().public_id),
            "quantity": 1,
        }, ToolContext(self.store_a, "unknown-permission"))
        self.assertTrue(result.get("error"), f"Invented action id accepted: {result}")

    def test_06_price_is_not_validated_as_substring_of_other_price(self):
        _, errors = orchestrator._validate_answer("Cuesta $5.00.", ['{"price":"$45.00"}'])
        self.assertTrue(errors, "Price $5.00 accepted solely because evidence contains $45.00")

    def test_07_empty_shipping_evidence_does_not_validate_guarantee(self):
        _, errors = orchestrator._validate_answer("Entrega hoy garantizada.", ['{"zones":[]}'])
        self.assertTrue(errors, "Empty zones accepted as support for delivery today")

    @override_settings(REINO_AI={"API_KEY": "local-test-only", "MAX_TOOL_ROUNDS": 4})
    def test_08_revocation_also_excludes_measurements_from_chat_history(self):
        key = "revoked-history"
        profile = self._profile(self.store_a, session=key)
        mem.grant_consent(self.store_a, key, Consent.Purpose.MEASUREMENTS, profile)
        mem.save_measurement(profile, chest_cm=36, neck_cm=24, back_cm=28)
        conv = orchestrator.get_conversation(self.store_a, key)
        AIMessage.objects.create(conversation=conv, role="user",
                                 content="Bruno tiene pecho 36 cm y cuello 24 cm.")
        mem.revoke_consent(self.store_a, key, Consent.Purpose.MEASUREMENTS, profile)
        observed = []
        def fake_chat(messages, **kwargs):
            observed.extend(messages)
            return {"role": "assistant", "content": "Revisemos el catálogo."}
        with mock.patch.object(adapter, "chat", side_effect=fake_chat):
            orchestrator.respond(conv, "Busco un arnés.", ToolContext(self.store_a, key, profile))
        self.assertTrue(observed, "Provider boundary was not exercised")
        self.assertNotIn("pecho 36", json.dumps(observed, ensure_ascii=False),
                         "Revoked measurement still sent through raw history")

    def test_09_action_stays_bound_to_original_recipient(self):
        key = "proposal-profile"
        original = self._profile(self.store_a, session=key, alias="Bruno")
        other = self._profile(self.store_a, session=key, alias="Luna")
        token = orchestrator._propose_action("add_item_to_cart", {
            "variant_id": str(self.variant().public_id), "quantity": 1,
        }, ToolContext(self.store_a, key, original))
        result = run_tool("add_item_to_cart", {"action_id": token.action_id},
                          ToolContext(self.store_a, key, other))
        if result.get("error"):
            return  # Reconfirmation is also acceptable.
        cart = c.get_open_cart(self.store_a, key)
        self.assertEqual(cart.items.get().recipient_id, original.pk,
                         "Existing proposal silently changed recipient")

    def test_10_action_requires_reconfirmation_when_price_changes(self):
        key = "proposal-price"
        token = orchestrator._propose_action("add_item_to_cart", {
            "variant_id": str(self.variant().public_id), "quantity": 1,
        }, ToolContext(self.store_a, key))
        self.product.base_price = "999.00"
        self.product.save(update_fields=["base_price"])
        result = run_tool("add_item_to_cart", {"action_id": token.action_id},
                          ToolContext(self.store_a, key))
        self.assertTrue(result.get("error"), f"Price changed $63 to $999 without new review: {result}")

    def test_11_merchant_staff_does_not_get_platform_operator_access(self):
        owner = User.objects.create_user(username="merchant-only", is_staff=True)
        MerchantMember.objects.create(user=owner, merchant=self.merchant_a, role="owner")
        self.client.force_login(owner)
        response = self.client.get("/plataforma/")
        self.assertNotEqual(response.status_code, 200,
                            "One merchant's staff can open platform-wide administration")
