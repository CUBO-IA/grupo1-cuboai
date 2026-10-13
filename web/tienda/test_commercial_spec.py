"""Reglas de la especificación comercial: descuento Bitcoin, producción
condicionada al pago verificado y revisión manual de cotizaciones."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from . import services
from .models import DogProfile, Order, OrderEvent, Quote

CUSTOMER = {
    "customer_name": "Ana Perez",
    "customer_email": "ana@example.com",
    "customer_phone": "+503 7000 0000",
    "country": "El Salvador",
    "city": "San Salvador",
    "address": "Calle 1",
}


def make_order(slug="wedding-dog", payment_method="unspecified"):
    dog = DogProfile.objects.create(
        name="Rex", breed="Dachshund", weight_kg=Decimal("7.50"),
        back_length_cm=Decimal("35.0"), chest_girth_cm=Decimal("42.5"),
    )
    quote = services.create_quote(dog, slug)
    order, _ = services.create_order(quote, {**CUSTOMER, "payment_method": payment_method})
    return order


class BitcoinDiscountTests(TestCase):
    def test_discount_is_15_percent_of_product_subtotal(self):
        for slug, subtotal, discount in (
            ("wedding-dog", "650.00", "97.50"),
            ("tactical-dog", "300.00", "45.00"),
            ("christmas-dog", "250.00", "37.50"),
            ("dog-sweater", "125.00", "18.75"),
        ):
            order = make_order(slug, "bitcoin")
            self.assertEqual(order.total, Decimal(subtotal))
            self.assertEqual(order.discount_amount, Decimal(discount))
            self.assertEqual(order.discount_rate, Decimal("0.15"))

    def test_compute_discount_rounding_and_other_methods(self):
        rate, amount = services.compute_discount(Decimal("100.03"), "bitcoin")
        self.assertEqual(amount, Decimal("15.00"))  # 15.0045 -> 15.00
        rate, amount = services.compute_discount(Decimal("100.10"), "bitcoin")
        self.assertEqual(amount, Decimal("15.02"))  # 15.015 -> 15.02 (half up)
        self.assertEqual(services.compute_discount(Decimal("650"), "unspecified"),
                         (Decimal("0"), Decimal("0.00")))
        self.assertEqual(services.compute_discount(Decimal("650"), "card")[1], Decimal("0.00"))

    def test_discount_pending_until_payment_verified(self):
        order = make_order("wedding-dog", "bitcoin")
        self.assertEqual(order.discount_status, Order.DiscountStatus.PENDING)
        self.assertEqual(order.amount_due, Decimal("650.00"))
        self.assertEqual(order.amount_if_discount, Decimal("552.50"))
        self.assertEqual(order.payment_status, "unpaid")

    def test_discount_applied_when_payment_recorded_with_reference(self):
        order = make_order("wedding-dog", "bitcoin")
        staff = User.objects.create_user("s", password="x", is_staff=True)
        with self.assertRaises(services.TransitionError):
            services.apply_transition(order, "payment_status", "paid", user=staff, note="")
        order.refresh_from_db()
        self.assertEqual(order.discount_status, Order.DiscountStatus.PENDING)
        services.apply_transition(order, "payment_status", "paid", user=staff, note="BTC-TX-1")
        order.refresh_from_db()
        self.assertEqual(order.discount_status, Order.DiscountStatus.APPLIED)
        self.assertEqual(order.amount_due, Decimal("552.50"))
        self.assertTrue(
            OrderEvent.objects.filter(field="discount_status", to_value="applied").exists()
        )

    def test_no_discount_without_bitcoin(self):
        order = make_order("wedding-dog", "unspecified")
        self.assertEqual(order.discount_status, Order.DiscountStatus.NONE)
        self.assertEqual(order.discount_amount, Decimal("0.00"))
        staff = User.objects.create_user("s", password="x", is_staff=True)
        services.apply_transition(order, "payment_status", "paid", user=staff, note="REF")
        order.refresh_from_db()
        self.assertEqual(order.discount_status, Order.DiscountStatus.NONE)
        self.assertEqual(order.amount_due, Decimal("650.00"))

    def test_checkout_uses_server_side_discount(self):
        dog = DogProfile.objects.create(
            name="Rex", breed="Dachshund", weight_kg=Decimal("7.5"),
            back_length_cm=Decimal("35"), chest_girth_cm=Decimal("42"),
        )
        quote = services.create_quote(dog, "dog-sweater")
        data = {**CUSTOMER, "payment_method": "bitcoin",
                "discount_amount": "99", "discount_status": "applied", "total": "1"}
        r = self.client.post(reverse("checkout", args=[quote.public_id]), data)
        order = Order.objects.get()
        self.assertEqual(order.discount_amount, Decimal("18.75"))
        self.assertEqual(order.discount_status, Order.DiscountStatus.PENDING)
        self.assertEqual(order.total, Decimal("125.00"))
        page = self.client.get(r.url)
        self.assertContains(page, "Bitcoin discount (15%)")
        self.assertContains(page, "-$18.75")
        self.assertContains(page, "Pending payment verification")
        self.assertContains(page, "Shipping cost")

    def test_snapshot_records_discount(self):
        order = make_order("tactical-dog", "bitcoin")
        self.assertEqual(order.snapshot["payment_method"], "bitcoin")
        self.assertEqual(order.snapshot["discount"]["amount"], "45.00")
        self.assertEqual(order.snapshot["discount"]["status"], "pending_verification")

    def test_margin_uses_amount_due(self):
        order = make_order("wedding-dog", "bitcoin")
        summary = services.cost_summary(order)
        self.assertEqual(summary["revenue"], Decimal("650.00"))
        self.assertTrue(summary["discount_pending"])
        staff = User.objects.create_user("s", password="x", is_staff=True)
        services.apply_transition(order, "payment_status", "paid", user=staff, note="BTC")
        order.refresh_from_db()
        summary = services.cost_summary(order)
        self.assertEqual(summary["revenue"], Decimal("552.50"))
        self.assertEqual(summary["margin"], Decimal("377.50"))


class ProductionGateTests(TestCase):
    def test_production_blocked_until_payment_verified(self):
        order = make_order()
        with self.assertRaises(services.TransitionError) as ctx:
            services.apply_transition(order, "production_status", "in_production")
        self.assertIn("Payment must be verified", str(ctx.exception))
        self.assertEqual(
            services.allowed_transitions(order)["production_status"], []
        )
        services.apply_transition(order, "payment_status", "paid", note="REF")
        order.refresh_from_db()
        self.assertEqual(
            services.allowed_transitions(order)["production_status"], ["in_production"]
        )
        services.apply_transition(order, "production_status", "in_production")

    def test_gate_through_panel(self):
        order = make_order()
        staff = User.objects.create_user("s", password="x", is_staff=True)
        self.client.force_login(staff)
        url = reverse("panel_order", args=[order.public_id])
        r = self.client.post(url, {"field": "production_status", "value": "in_production"})
        self.assertEqual(r.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.production_status, "not_started")

    def test_states_stay_independent(self):
        order = make_order()
        services.apply_transition(order, "payment_status", "paid", note="REF")
        order.refresh_from_db()
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.production_status, "not_started")
        self.assertEqual(order.shipping_status, "not_shipped")


class ManualReviewWordingTests(TestCase):
    def test_quote_and_order_mention_manual_review(self):
        order = make_order()
        quote_page = self.client.get(reverse("smart_quote", args=[order.quote.public_id]))
        self.assertContains(quote_page, "reviews every quote manually")
        order_page = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertContains(order_page, "review your quote manually")

    def test_checkout_states_payment_not_confirmed(self):
        dog = DogProfile.objects.create(
            name="Rex", breed="Dachshund", weight_kg=Decimal("7.5"),
            back_length_cm=Decimal("35"), chest_girth_cm=Decimal("42"),
        )
        quote = services.create_quote(dog, "dog-sweater")
        page = self.client.get(reverse("checkout", args=[quote.public_id]))
        self.assertContains(page, "does not confirm payment")
        self.assertContains(page, "production starts only after")
        self.assertContains(page, "15% discount")
        self.assertEqual(Quote.objects.count(), 1)
