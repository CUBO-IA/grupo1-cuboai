from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from . import assistant, services
from .models import Order, OrderEvent
from .test_panel import make_order


class AssistantTests(TestCase):
    def ask(self, **params):
        return self.client.get(reverse("assistant"), params)

    def test_page_renders_empty(self):
        r = self.client.get(reverse("assistant"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "does not know about orders")

    def test_occasion_recommendations_use_catalog(self):
        expected = {
            "wedding": ("Wedding Dog Suit Pair for Two", "$650"),
            "adventure": ("Tactical Dog", "$300"),
            "holiday": ("Christmas Dog", "$250"),
            "warmth": ("Luxury Cable Knit Dachshund Jumper", "$150"),
            "bath": ("Bamboo Dachshund Drying Robe", "$88"),
            "walks": ("Walnut Whip Dachshund Harness Fleece", "$250"),
        }
        for key, (name, price) in expected.items():
            r = self.ask(occasion=key)
            self.assertContains(r, name)
            self.assertContains(r, price)

    def test_price_question_uses_real_price(self):
        r = self.ask(q="How much is the cable knit jumper?")
        self.assertContains(r, "$150")
        self.assertContains(r, "confirmed by Weiner Kingdom")

    def test_measurement_question_points_to_smart_fit(self):
        r = self.ask(q="How do I measure my dog for the wedding suit?")
        self.assertContains(r, reverse("smart_fit"))
        self.assertContains(r, "do not calculate a size")

    def test_unsupported_topics_are_not_invented(self):
        for q in ("Do you ship to Guatemala?", "Can I pay with bitcoin?",
                  "Where is my order?", "What is your refund policy?"):
            reply = assistant.answer(q)
            self.assertTrue(reply["unknown"], q)
            self.assertIn("don't have confirmed information", reply["message"])
            self.assertEqual(reply["products"], [])
            self.assertNotRegex(reply["message"], r"\$\d")

    def test_ambiguous_question_asks_for_clarification(self):
        reply = assistant.answer("price of wedding and christmas")
        self.assertIn("more than one product", reply["message"])
        self.assertEqual(len(reply["products"]), 2)

    def test_unknown_question_and_empty_input(self):
        self.assertTrue(assistant.answer("tell me a joke")["unknown"])
        self.assertTrue(assistant.answer("   ")["unknown"])
        r = self.ask(occasion="bogus")
        self.assertEqual(r.status_code, 200)

    def test_input_is_escaped_and_length_limited(self):
        r = self.ask(q="<script>alert(1)</script>" + "a" * 500)
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertEqual(r.status_code, 200)

    def test_assistant_does_not_write_data(self):
        self.ask(q="wedding", occasion="wedding")
        self.assertEqual(Order.objects.count(), 0)

    def test_prices_follow_catalog_changes(self):
        from unittest import mock

        changed = {**services.PRODUCTOS["cable-knit-jumper"], "precio": "$130"}
        with mock.patch.dict(services.PRODUCTOS, {"cable-knit-jumper": changed}):
            self.assertIn("$130", assistant.answer("price of the jumper")["message"])


class CostTests(TestCase):
    def setUp(self):
        self.order = make_order()
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.url = reverse("panel_order", args=[self.order.public_id])

    def test_default_is_product_estimate(self):
        s = services.cost_summary(self.order)
        self.assertEqual(s["cost_source"], "product_estimate")
        self.assertEqual(s["cost"], Decimal("175.00"))  # Tactical Dog: 100 + 60 + 15
        self.assertFalse(s["is_actual"])

    def test_components_sum_and_priority(self):
        services.update_costs(
            self.order, self.staff,
            estimated_materials=Decimal("120"), estimated_labor=Decimal("80"),
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.estimated_cost, Decimal("200"))
        s = services.cost_summary(self.order)
        self.assertEqual((s["cost_source"], s["margin"]), ("estimated", Decimal("100.00")))
        services.update_costs(
            self.order, self.staff,
            estimated_materials=Decimal("120"), estimated_labor=Decimal("80"),
            actual_materials=Decimal("100.25"), actual_labor=Decimal("80.25"),
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.actual_cost, Decimal("180.50"))
        s = services.cost_summary(self.order)
        self.assertEqual((s["cost_source"], s["margin"]), ("actual", Decimal("119.50")))
        self.assertTrue(s["is_actual"])

    def test_partial_component_is_enough(self):
        services.update_costs(self.order, self.staff, actual_materials=Decimal("90"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.actual_cost, Decimal("90"))
        self.assertIsNone(self.order.estimated_cost)

    def test_negative_rejected_in_service_and_form(self):
        with self.assertRaises(services.TransitionError):
            services.update_costs(self.order, self.staff, actual_labor=Decimal("-1"))
        self.client.force_login(self.staff)
        r = self.client.post(self.url, {"form": "costs", "actual_labor": "-5"})
        self.assertEqual(r.status_code, 400)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.actual_cost)

    def test_invalid_text_rejected(self):
        self.client.force_login(self.staff)
        r = self.client.post(self.url, {"form": "costs", "actual_materials": "abc"})
        self.assertEqual(r.status_code, 400)

    def test_edit_via_panel_labels_and_history(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            self.url,
            {"form": "costs", "actual_materials": "100.25", "actual_labor": "90",
             "cost_notes": "fabric invoice"},
        )
        self.assertRedirects(r, self.url)
        page = self.client.get(self.url)
        self.assertContains(page, "ACTUAL cost recorded")
        self.assertContains(page, "(actual)")
        self.assertNotContains(page, "ESTIMATE — not verified")
        self.order.refresh_from_db()
        self.assertEqual(self.order.actual_cost, Decimal("190.25"))
        self.assertEqual(self.order.cost_notes, "fabric invoice")
        fields = set(OrderEvent.objects.values_list("field", flat=True))
        self.assertEqual(fields, {"actual_materials", "actual_labor", "actual_cost"})

    def test_costs_require_staff_and_csrf(self):
        r = self.client.post(self.url, {"form": "costs", "actual_labor": "1"})
        self.assertEqual(r.status_code, 302)
        self.client.force_login(User.objects.create_user("u", password="x"))
        r = self.client.post(self.url, {"form": "costs", "actual_labor": "1"})
        self.assertEqual(r.status_code, 403)
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.staff)
        self.assertEqual(c.post(self.url, {"form": "costs", "actual_labor": "1"}).status_code, 403)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.actual_cost)

    def test_costs_never_shown_to_customer(self):
        services.update_costs(
            self.order, self.staff, actual_materials=Decimal("100.23"),
            actual_labor=Decimal("71"), notes="secret note",
        )
        page = self.client.get(reverse("order_detail", args=[self.order.public_id]))
        self.assertNotContains(page, "171.23")
        self.assertNotContains(page, "100.23")
        self.assertNotContains(page, "secret note")
        self.assertNotContains(page, "margin", html=False)


class TrackingTests(TestCase):
    def test_states_explained_and_not_overstated(self):
        order = make_order()
        page = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertContains(page, "What the states mean")
        self.assertContains(page, "no carrier tracking is connected")
        self.assertContains(page, "No updates yet")
        self.assertNotContains(page, "Shipped</dd>")
        self.assertNotContains(page, "Paid</dd>")

    def test_updates_visible_without_internal_notes(self):
        order = make_order()
        staff = User.objects.create_user("s", password="x", is_staff=True)
        services.apply_transition(order, "payment_status", "paid", user=staff, note="BANK-SECRET-9")
        services.apply_transition(order, "production_status", "in_production", user=staff)
        page = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertContains(page, "Payment: paid")
        self.assertContains(page, "Production: in production")
        self.assertNotContains(page, "BANK-SECRET-9")
        self.assertNotContains(page, "staff")
