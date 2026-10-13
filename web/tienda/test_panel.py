from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from . import services
from .models import DogProfile, Order, OrderEvent


def make_order(name="Ana Perez", slug="tactical-dog"):
    dog = DogProfile.objects.create(
        name="Rex", breed="Dachshund", weight_kg=Decimal("7.50"),
        back_length_cm=Decimal("35.0"), chest_girth_cm=Decimal("42.5"),
    )
    quote = services.create_quote(dog, slug)
    order, _ = services.create_order(
        quote,
        {
            "customer_name": name,
            "customer_email": "ana@example.com",
            "customer_phone": "+503 7000 0000",
            "country": "El Salvador",
            "city": "San Salvador",
            "address": "Calle 1",
        },
    )
    return order


class PanelAccessTests(TestCase):
    def setUp(self):
        self.order = make_order()
        self.staff = User.objects.create_user("staff", password="x-test-pw", is_staff=True)
        self.user = User.objects.create_user("user", password="x-test-pw")
        self.urls = [
            reverse("panel_orders"),
            reverse("panel_order", args=[self.order.public_id]),
        ]

    def test_anonymous_redirected_to_login(self):
        for url in self.urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse("panel_login"), r.url)

    def test_anonymous_cannot_post_transition(self):
        r = self.client.post(
            self.urls[1], {"field": "status", "value": "confirmed"}
        )
        self.assertEqual(r.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_non_staff_forbidden(self):
        self.client.force_login(self.user)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        r = self.client.post(self.urls[1], {"field": "status", "value": "confirmed"})
        self.assertEqual(r.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_staff_allowed(self):
        self.client.force_login(self.staff)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_login_flow(self):
        r = self.client.post(
            reverse("panel_login"), {"username": "staff", "password": "x-test-pw"}
        )
        self.assertRedirects(r, reverse("panel_orders"))
        r = self.client.post(
            reverse("panel_login"), {"username": "staff", "password": "wrong"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Incorrect username or password")

    def test_public_pages_do_not_expose_panel_data(self):
        r = self.client.get(reverse("order_detail", args=[self.order.public_id]))
        self.assertNotContains(r, "Internal cost estimate")
        self.assertNotContains(r, "ESTIMATE")

    def test_csrf_on_transition(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.staff)
        r = c.post(self.urls[1], {"field": "status", "value": "confirmed"})
        self.assertEqual(r.status_code, 403)

    def test_inactive_staff_forbidden(self):
        self.staff.is_active = False
        self.staff.save()
        self.client.force_login(self.staff)
        self.assertNotEqual(self.client.get(self.urls[0]).status_code, 200)


class PanelListTests(TestCase):
    def setUp(self):
        self.client.force_login(
            User.objects.create_user("staff", password="x", is_staff=True)
        )
        self.a = make_order("Ana Perez", "wedding-dog")
        self.b = make_order("Bruno Diaz", "dog-sweater")
        services.apply_transition(self.b, "status", "confirmed")

    def get(self, **params):
        return self.client.get(reverse("panel_orders"), params)

    def test_lists_all(self):
        r = self.get()
        self.assertEqual(len(r.context["orders"]), 2)

    def test_search_by_name_email_number_product(self):
        self.assertEqual([o.pk for o in self.get(q="bruno").context["orders"]], [self.b.pk])
        self.assertEqual(len(self.get(q="ana@example").context["orders"]), 2)
        self.assertEqual([o.pk for o in self.get(q=self.a.number).context["orders"]], [self.a.pk])
        self.assertEqual([o.pk for o in self.get(q="wedding").context["orders"]], [self.a.pk])
        self.assertEqual(len(self.get(q="zzz").context["orders"]), 0)

    def test_filters(self):
        r = self.get(status="confirmed")
        self.assertEqual([o.pk for o in r.context["orders"]], [self.b.pk])
        self.assertEqual(len(self.get(payment_status="paid").context["orders"]), 0)
        # valor inválido se ignora
        self.assertEqual(len(self.get(status="bogus").context["orders"]), 2)


class TransitionTests(TestCase):
    def setUp(self):
        self.order = make_order()
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)

    def test_initial_states_independent(self):
        o = self.order
        self.assertEqual(o.payment_status, "unpaid")
        self.assertEqual(o.production_status, "not_started")
        self.assertEqual(o.shipping_status, "not_shipped")

    def test_payment_requires_reference(self):
        with self.assertRaises(services.TransitionError):
            services.apply_transition(self.order, "payment_status", "paid", note="")
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "unpaid")
        services.apply_transition(
            self.order, "payment_status", "paid", user=self.staff, note="BANK-123"
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")
        self.assertEqual(self.order.payment_reference, "BANK-123")
        ev = OrderEvent.objects.get()
        self.assertEqual((ev.field, ev.from_value, ev.to_value, ev.by), ("payment_status", "unpaid", "paid", self.staff))

    def test_paying_does_not_change_production_or_shipping(self):
        services.apply_transition(self.order, "payment_status", "paid", note="R1")
        self.order.refresh_from_db()
        self.assertEqual(self.order.production_status, "not_started")
        self.assertEqual(self.order.shipping_status, "not_shipped")

    def test_invalid_transitions(self):
        bad = [
            ("payment_status", "unpaid"),
            ("production_status", "completed"),
            ("shipping_status", "delivered"),
            ("shipping_status", "shipped"),
            ("status", "pending"),
            ("nonsense", "x"),
            ("status", "bogus"),
        ]
        for field, value in bad:
            with self.assertRaises(services.TransitionError, msg=(field, value)):
                services.apply_transition(self.order, field, value, note="n")
        self.assertEqual(OrderEvent.objects.count(), 0)

    def test_no_shipping_before_production_completed(self):
        services.apply_transition(self.order, "payment_status", "paid", note="R1")
        services.apply_transition(self.order, "production_status", "in_production")
        with self.assertRaises(services.TransitionError):
            services.apply_transition(self.order, "shipping_status", "shipped")
        services.apply_transition(self.order, "production_status", "completed")
        services.apply_transition(self.order, "shipping_status", "shipped")
        services.apply_transition(self.order, "shipping_status", "delivered")
        self.order.refresh_from_db()
        self.assertEqual(self.order.shipping_status, "delivered")

    def test_cancelled_is_final_and_blocked_after_shipping(self):
        services.apply_transition(self.order, "status", "cancelled")
        with self.assertRaises(services.TransitionError):
            services.apply_transition(self.order, "production_status", "in_production")
        other = make_order("Otro")
        services.apply_transition(other, "payment_status", "paid", note="R2")
        services.apply_transition(other, "production_status", "in_production")
        services.apply_transition(other, "production_status", "completed")
        services.apply_transition(other, "shipping_status", "shipped")
        with self.assertRaises(services.TransitionError):
            services.apply_transition(other, "status", "cancelled")

    def test_allowed_transitions_listing(self):
        allowed = services.allowed_transitions(self.order)
        self.assertEqual(allowed["payment_status"], ["paid"])
        self.assertEqual(allowed["shipping_status"], [])

    def test_transition_via_panel(self):
        self.client.force_login(self.staff)
        url = reverse("panel_order", args=[self.order.public_id])
        r = self.client.post(url, {"field": "status", "value": "confirmed"})
        self.assertRedirects(r, url)
        r = self.client.post(url, {"field": "payment_status", "value": "paid", "note": ""})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "payment reference is required", status_code=400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "confirmed")
        self.assertEqual(self.order.payment_status, "unpaid")

    def test_cost_estimate_labelled_and_decimal(self):
        est = services.cost_summary(self.order)
        self.assertEqual(est["cost_source"], "target")
        self.assertEqual(est["cost"], Decimal("175.00"))
        self.assertEqual(est["margin"], Decimal("125.00"))
        self.assertEqual(est["margin_pct"], Decimal("41.7"))
        self.client.force_login(self.staff)
        r = self.client.get(reverse("panel_order", args=[self.order.public_id]))
        self.assertContains(r, "ESTIMATE")
        self.assertContains(r, "target, not a proven cost")
        self.assertContains(r, "(provisional)")
