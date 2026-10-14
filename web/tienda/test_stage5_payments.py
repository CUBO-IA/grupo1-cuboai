"""Etapa 5: pagos — Bitcoin, opciones demo y reglas por producto."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from . import services
from .models import DogProfile, Order, OrderEvent, ProductPaymentRule

CUSTOMER = {
    "customer_name": "Ana Perez", "customer_email": "ana@example.com",
    "customer_phone": "+503 7000 0000", "country": "El Salvador",
    "city": "San Salvador", "address": "Calle 1 #2", "payment_method": "unspecified",
}


def make_dog():
    return DogProfile.objects.create(
        name="Rex", breed="Dachshund", weight_kg=Decimal("7.50"),
        back_length_cm=Decimal("35.0"), chest_girth_cm=Decimal("42.5"),
    )


def make_order(slug="wedding-dog", method="unspecified", quantity=1):
    quote = services.create_quote(make_dog(), slug, quantity)
    order, _ = services.create_order(quote, {**CUSTOMER, "payment_method": method})
    return order


def staff():
    return User.objects.create_user("staff", password="x", is_staff=True)


class DemoMethodTests(TestCase):
    def test_options_present_and_marked_demo(self):
        quote = services.create_quote(make_dog(), "dog-sweater")
        page = self.client.get(reverse("checkout", args=[quote.public_id]))
        self.assertContains(page, "PayPal — DEMO, not available")
        self.assertContains(page, "Card — DEMO, not available")
        self.assertContains(page, "no payment is processed")

    def test_no_card_data_is_collected(self):
        quote = services.create_quote(make_dog(), "dog-sweater")
        page = self.client.get(reverse("checkout", args=[quote.public_id])).content.decode().lower()
        for word in ("card number", "cvv", "cvc", "expiry", "expiration", "cardnumber"):
            self.assertNotIn(word, page)
        # Tampering: campos de tarjeta enviados no se guardan en ningún lado.
        r = self.client.post(
            reverse("checkout", args=[quote.public_id]),
            {**CUSTOMER, "payment_method": "card_demo", "card_number": "4111111111111111",
             "cvv": "123", "step": "confirm"},
        )
        order = Order.objects.get()
        self.assertNotIn("4111", str(order.snapshot))
        self.assertNotIn("4111", order.customer_name + order.address + order.payment_reference)
        self.assertEqual(r.status_code, 302)

    def test_demo_order_is_unpaid_without_discount(self):
        for method in ("paypal_demo", "card_demo"):
            order = make_order("wedding-dog", method)
            self.assertEqual(order.payment_method, method)
            self.assertEqual(order.payment_status, "unpaid")
            self.assertEqual(order.discount_status, "none")
            self.assertEqual(order.discount_amount, Decimal("0.00"))
            self.assertEqual(order.amount_due, Decimal("650.00"))

    def test_review_page_flags_demo(self):
        quote = services.create_quote(make_dog(), "dog-sweater")
        r = self.client.post(
            reverse("checkout", args=[quote.public_id]),
            {**CUSTOMER, "payment_method": "paypal_demo", "step": "review"},
        )
        self.assertContains(r, "DEMO option")
        self.assertContains(r, "nothing is charged")
        self.assertEqual(Order.objects.count(), 0)

    def test_customer_page_explains_demo_and_never_shows_paid(self):
        order = make_order("dog-sweater", "card_demo")
        page = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertContains(page, "Card (demo - not available)")
        self.assertContains(page, "Demonstration option")
        self.assertContains(page, "no payment has been collected")
        self.assertNotContains(page, "Paid</dd>")

    def test_demo_cannot_be_recorded_as_paid(self):
        order = make_order("dog-sweater", "paypal_demo")
        with self.assertRaises(services.TransitionError) as ctx:
            services.apply_transition(order, "payment_status", "paid", note="REF")
        self.assertIn("Demo payment methods", str(ctx.exception))
        self.assertNotIn(
            "paid", services.allowed_transitions(order)["payment_status"]
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "unpaid")
        # ni producción
        with self.assertRaises(services.TransitionError):
            services.apply_transition(order, "production_status", "in_production")

    def test_demo_paid_blocked_through_panel(self):
        order = make_order("dog-sweater", "card_demo")
        self.client.force_login(staff())
        url = reverse("panel_order", args=[order.public_id])
        r = self.client.post(url, {"field": "payment_status", "value": "paid", "note": "x"})
        self.assertEqual(r.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "unpaid")

    def test_unknown_method_falls_back(self):
        order = make_order("dog-sweater", "wire_transfer")
        self.assertEqual(order.payment_method, "unspecified")


class EligibilityTests(TestCase):
    def test_all_products_eligible_by_default(self):
        self.assertEqual(
            set(ProductPaymentRule.objects.values_list("product_slug", "bitcoin_discount_eligible")),
            {(slug, True) for slug in services.PRODUCTOS},
        )

    def test_ineligible_product_gets_no_discount(self):
        ProductPaymentRule.objects.filter(product_slug="dog-sweater").update(
            bitcoin_discount_eligible=False
        )
        order = make_order("dog-sweater", "bitcoin", quantity=2)
        self.assertEqual(order.discount_status, "none")
        self.assertEqual(order.discount_amount, Decimal("0.00"))
        self.assertEqual(order.total, Decimal("250.00"))
        # otro producto sigue elegible
        other = make_order("tactical-dog", "bitcoin")
        self.assertEqual(other.discount_amount, Decimal("45.00"))

    def test_checkout_and_review_say_so(self):
        ProductPaymentRule.objects.filter(product_slug="dog-sweater").update(
            bitcoin_discount_eligible=False
        )
        quote = services.create_quote(make_dog(), "dog-sweater")
        url = reverse("checkout", args=[quote.public_id])
        self.assertContains(self.client.get(url), "does not apply to this product")
        r = self.client.post(url, {**CUSTOMER, "payment_method": "bitcoin", "step": "review"})
        self.assertContains(r, "does not apply to this product")
        self.assertNotContains(r, "Bitcoin discount (15%)")

    def test_panel_payments_page_and_update(self):
        url = reverse("panel_payments")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(staff())
        page = self.client.get(url)
        self.assertContains(page, "No payment provider is connected")
        self.assertContains(page, "Pending definition")
        r = self.client.post(url, {"btc_wedding-dog": "on", "btc_tactical-dog": "on"})
        self.assertRedirects(r, url)
        self.assertFalse(services.discount_eligible("dog-sweater"))
        self.assertFalse(services.discount_eligible("christmas-dog"))
        self.assertTrue(services.discount_eligible("wedding-dog"))

    def test_csrf_on_payments(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(staff())
        self.assertEqual(c.post(reverse("panel_payments"), {}).status_code, 403)


class ChangeMethodTests(TestCase):
    def test_switch_recalculates_discount(self):
        order = make_order("wedding-dog", "unspecified")
        s = staff()
        services.set_payment_method(order, "bitcoin", user=s)
        order.refresh_from_db()
        self.assertEqual(order.discount_amount, Decimal("97.50"))
        self.assertEqual(order.discount_status, "pending_verification")
        services.set_payment_method(order, "unspecified", user=s)
        order.refresh_from_db()
        self.assertEqual((order.discount_amount, order.discount_status), (Decimal("0.00"), "none"))
        self.assertEqual(
            OrderEvent.objects.filter(field="payment_method").count(), 2
        )

    def test_demo_to_bitcoin_then_verified_payment_applies_discount(self):
        order = make_order("wedding-dog", "paypal_demo")
        s = staff()
        services.set_payment_method(order, "bitcoin", user=s)
        order.refresh_from_db()
        services.apply_transition(order, "payment_status", "paid", user=s, note="BTC-TX-9")
        order.refresh_from_db()
        self.assertEqual(order.discount_status, "applied")
        self.assertEqual(order.amount_due, Decimal("552.50"))

    def test_cannot_set_demo_or_unknown(self):
        order = make_order("wedding-dog", "unspecified")
        for method in ("paypal_demo", "card_demo", "cash", ""):
            with self.assertRaises(services.TransitionError):
                services.set_payment_method(order, method)

    def test_blocked_after_payment_and_when_cancelled(self):
        order = make_order("wedding-dog", "bitcoin")
        services.apply_transition(order, "payment_status", "paid", note="REF")
        order.refresh_from_db()
        with self.assertRaises(services.TransitionError):
            services.set_payment_method(order, "unspecified")
        other = make_order("dog-sweater", "unspecified")
        services.apply_transition(other, "status", "cancelled")
        other.refresh_from_db()
        with self.assertRaises(services.TransitionError):
            services.set_payment_method(other, "bitcoin")

    def test_panel_form_permissions_and_effect(self):
        order = make_order("tactical-dog", "unspecified")
        url = reverse("panel_order", args=[order.public_id])
        r = self.client.post(url, {"form": "payment_method", "payment_method": "bitcoin"})
        self.assertEqual(r.status_code, 302)  # anónimo → login
        self.client.force_login(User.objects.create_user("u", password="x"))
        r = self.client.post(url, {"form": "payment_method", "payment_method": "bitcoin"})
        self.assertEqual(r.status_code, 403)
        self.client.force_login(staff())
        page = self.client.get(url)
        self.assertContains(page, "Set payment method")
        r = self.client.post(url, {"form": "payment_method", "payment_method": "bitcoin"})
        self.assertRedirects(r, url)
        order.refresh_from_db()
        self.assertEqual(order.discount_amount, Decimal("45.00"))
        r = self.client.post(url, {"form": "payment_method", "payment_method": "card_demo"})
        self.assertEqual(r.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.payment_method, "bitcoin")

    def test_csrf_on_method_change(self):
        order = make_order("tactical-dog")
        c = Client(enforce_csrf_checks=True)
        c.force_login(staff())
        r = c.post(
            reverse("panel_order", args=[order.public_id]),
            {"form": "payment_method", "payment_method": "bitcoin"},
        )
        self.assertEqual(r.status_code, 403)
