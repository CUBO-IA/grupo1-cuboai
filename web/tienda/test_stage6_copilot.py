"""Etapa 6: Order Copilot — preparación para fabricar, etapas, progreso,
talla confirmada, seguimiento y ficha de taller."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from . import services
from .models import DogProfile, Order, OrderEvent

CUSTOMER = {
    "customer_name": "Ana Perez", "customer_email": "ana@example.com",
    "customer_phone": "+503 7000 0000", "country": "El Salvador",
    "city": "San Salvador", "address": "Calle 1 #2", "payment_method": "unspecified",
}


def make_order(slug="wedding-dog", chest="42.5", back="35.0", method="unspecified", quantity=1):
    dog = DogProfile.objects.create(
        name="Rex", breed="Dachshund", weight_kg=Decimal("7.50"),
        back_length_cm=Decimal(back), chest_girth_cm=Decimal(chest),
    )
    quote = services.create_quote(dog, slug, quantity)
    order, _ = services.create_order(quote, {**CUSTOMER, "payment_method": method})
    return order


def ambiguous_order(**kw):
    return make_order(chest="46", back="36", **kw)


def staff():
    return User.objects.create_user("staff", password="x", is_staff=True)


def pay(order, ref="REF-1"):
    services.apply_transition(order, "payment_status", "paid", note=ref)
    order.refresh_from_db()
    return order


class ReadinessTests(TestCase):
    def check(self, order, key):
        return next(c for c in services.order_readiness(order)["checks"] if c["key"] == key)

    def test_unpaid_complete_order_not_ready(self):
        order = make_order()
        r = services.order_readiness(order)
        self.assertTrue(r["saved"])
        self.assertFalse(r["payment_confirmed"])
        self.assertTrue(r["info_validated"])
        self.assertFalse(r["ready"])
        self.assertTrue(any("payment" in b for b in r["blockers"]))

    def test_paid_complete_order_ready(self):
        order = pay(make_order())
        r = services.order_readiness(order)
        self.assertTrue(r["payment_confirmed"] and r["info_validated"] and r["ready"])
        self.assertEqual(r["blockers"], [])

    def test_indicators_are_independent(self):
        order = pay(ambiguous_order())
        r = services.order_readiness(order)
        self.assertTrue(r["payment_confirmed"])
        self.assertFalse(r["info_validated"])
        self.assertFalse(r["ready"])

    def test_missing_delivery_data_blocks(self):
        order = pay(make_order())
        order.address = "  "
        order.save()
        r = services.order_readiness(order)
        self.assertFalse(r["info_validated"])
        self.assertIn("address", self.check(order, "delivery")["detail"])

    def test_missing_measurements_block(self):
        order = pay(make_order())
        line = order.lines.get()
        line.dog_snapshot["chest_girth_cm"] = None
        line.save()
        self.assertIn("chest girth", self.check(order, "measurements")["detail"])
        self.assertFalse(services.order_readiness(order)["ready"])

    def test_required_neck_missing_blocks(self):
        order = pay(make_order())
        line = order.lines.get()
        line.required_measurements = {"neck_girth": True, "validated": False}
        line.save()
        self.assertIn("neck girth", self.check(order, "measurements")["detail"])
        line.dog_snapshot["neck_girth_cm"] = "25.0"
        line.save()
        self.assertTrue(self.check(order, "measurements")["ok"])

    def test_ambiguous_or_outside_size_needs_staff_confirmation(self):
        order = pay(ambiguous_order())
        self.assertFalse(self.check(order, "size")["ok"])
        self.assertIn("ambiguous", self.check(order, "size")["detail"])
        services.confirm_size(order, "M (medium dogs)", user=staff())
        order.refresh_from_db()
        self.assertTrue(self.check(order, "size")["ok"])
        self.assertTrue(services.order_readiness(order)["ready"])

    def test_cancelled_never_ready(self):
        order = pay(make_order())
        services.apply_transition(order, "status", "cancelled")
        order.refresh_from_db()
        r = services.order_readiness(order)
        self.assertFalse(r["ready"])
        self.assertIn("order is cancelled", r["blockers"])

    def test_demo_method_never_counts_as_paid(self):
        order = make_order(method="paypal_demo")
        self.assertFalse(services.order_readiness(order)["payment_confirmed"])


class ProductionGateTests(TestCase):
    def test_blocked_without_data_with_reason(self):
        order = pay(ambiguous_order())
        with self.assertRaises(services.TransitionError) as ctx:
            services.apply_transition(order, "production_status", "in_production")
        self.assertIn("Cannot start production", str(ctx.exception))
        self.assertIn("size", str(ctx.exception))
        order.refresh_from_db()
        self.assertEqual(order.production_status, "not_started")
        self.assertEqual(services.allowed_transitions(order)["production_status"], [])

    def test_payment_message_still_first(self):
        order = make_order()
        with self.assertRaises(services.TransitionError) as ctx:
            services.apply_transition(order, "production_status", "in_production")
        self.assertIn("Payment must be verified", str(ctx.exception))

    def test_blocked_through_panel_then_allowed_after_size_confirmation(self):
        order = pay(ambiguous_order())
        self.client.force_login(staff())
        url = reverse("panel_order", args=[order.public_id])
        r = self.client.post(url, {"field": "production_status", "value": "in_production"})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "Cannot start production", status_code=400)
        r = self.client.post(url, {"form": "size", "size_confirmed": "M"})
        self.assertRedirects(r, url)
        r = self.client.post(url, {"field": "production_status", "value": "in_production"})
        self.assertRedirects(r, url)
        order.refresh_from_db()
        self.assertEqual(order.production_status, "in_production")

    def test_complete_paid_order_can_start(self):
        order = pay(make_order())
        services.apply_transition(order, "production_status", "in_production")
        order.refresh_from_db()
        self.assertEqual(order.production_status, "in_production")


class SizeAndTrackingTests(TestCase):
    def test_confirm_size_validation_and_event(self):
        order = ambiguous_order()
        for bad in ("", "   ", "x" * 41):
            with self.assertRaises(services.TransitionError):
                services.confirm_size(order, bad)
        services.confirm_size(order, "L", user=staff())
        order.refresh_from_db()
        self.assertEqual(order.size_confirmed, "L")
        self.assertTrue(OrderEvent.objects.filter(field="size_confirmed").exists())

    def test_size_locked_after_production_started_or_cancelled(self):
        order = pay(make_order())
        services.apply_transition(order, "production_status", "in_production")
        order.refresh_from_db()
        with self.assertRaises(services.TransitionError):
            services.confirm_size(order, "S")
        other = make_order()
        services.apply_transition(other, "status", "cancelled")
        other.refresh_from_db()
        with self.assertRaises(services.TransitionError):
            services.confirm_size(other, "S")

    def test_tracking_optional_and_logged(self):
        order = pay(make_order())
        for step in ("in_production", "completed"):
            services.apply_transition(order, "production_status", step)
            order.refresh_from_db()
        # Enviar sin número de seguimiento está permitido (es opcional).
        services.apply_transition(order, "shipping_status", "shipped")
        order.refresh_from_db()
        self.assertEqual(order.shipping_status, "shipped")
        self.assertEqual(order.tracking_number, "")
        services.set_tracking(order, "TRK-123", "DHL", user=staff())
        order.refresh_from_db()
        self.assertEqual((order.tracking_number, order.tracking_carrier), ("TRK-123", "DHL"))
        self.assertTrue(OrderEvent.objects.filter(field="tracking_number").exists())

    def test_tracking_validation(self):
        order = make_order()
        with self.assertRaises(services.TransitionError):
            services.set_tracking(order, "x" * 61)
        with self.assertRaises(services.TransitionError):
            services.set_tracking(order, "<script>")

    def test_customer_sees_tracking_only_when_set(self):
        order = make_order()
        url = reverse("order_detail", args=[order.public_id])
        self.assertNotContains(self.client.get(url), "Tracking number")
        services.set_tracking(order, "TRK-777", "Correos")
        page = self.client.get(url)
        self.assertContains(page, "TRK-777")
        self.assertContains(page, "Correos")
        # los eventos de seguimiento/talla no aparecen en "Updates"
        self.assertNotContains(page, "tracking_number")
        self.assertNotContains(page, "size_confirmed")


class ProgressAndStagesTests(TestCase):
    def test_progress_steps(self):
        order = make_order()
        steps = services.progress_steps(order)
        self.assertEqual([s["done"] for s in steps], [True, False, False, False, False, False])
        self.assertTrue(steps[1]["current"])
        pay(order)
        for step in ("in_production", "completed"):
            services.apply_transition(order, "production_status", step)
        order.refresh_from_db()
        done = [s["done"] for s in services.progress_steps(order)]
        self.assertEqual(done, [True, True, True, True, False, False])

    def test_stage_counts_and_filters(self):
        unpaid = make_order()
        ready = pay(make_order())
        inprod = pay(make_order())
        services.apply_transition(inprod, "production_status", "in_production")
        finished = pay(make_order())
        for s in ("in_production", "completed"):
            services.apply_transition(finished, "production_status", s)
        shipped = pay(make_order())
        for s in ("in_production", "completed"):
            services.apply_transition(shipped, "production_status", s)
        shipped.refresh_from_db()
        services.apply_transition(shipped, "shipping_status", "shipped")
        cancelled = make_order()
        services.apply_transition(cancelled, "status", "cancelled")

        counts = {c["key"]: c["count"] for c in services.stage_counts()}
        self.assertEqual(
            counts, {"review": 1, "ready": 1, "production": 1, "finished": 1, "shipped": 1}
        )
        self.client.force_login(staff())
        url = reverse("panel_orders")

        def numbers(stage):
            r = self.client.get(url, {"stage": stage})
            return {o.number for o in r.context["orders"]}

        self.assertEqual(numbers("review"), {unpaid.number})
        self.assertEqual(numbers("ready"), {ready.number})
        self.assertEqual(numbers("production"), {inprod.number})
        self.assertEqual(numbers("finished"), {finished.number})
        self.assertEqual(numbers("shipped"), {shipped.number})
        self.assertEqual(
            numbers("attention"), {unpaid.number, ready.number, finished.number}
        )
        self.assertEqual(len(self.client.get(url, {"stage": "bogus"}).context["orders"]), 6)

    def test_list_shows_stage_cards_and_ready_column(self):
        pay(make_order())
        self.client.force_login(staff())
        page = self.client.get(reverse("panel_orders"))
        self.assertContains(page, "Paid / ready to make")
        self.assertContains(page, "Needs attention")
        self.assertContains(page, "Ready to make")


class SheetAndPermissionsTests(TestCase):
    def test_sheet_content_for_staff(self):
        order = pay(make_order("cable-knit-jumper", quantity=2))
        self.client.force_login(staff())
        page = self.client.get(reverse("panel_order_sheet", args=[order.public_id]))
        self.assertEqual(page.status_code, 200)
        for text in (order.number, "Luxury Cable Knit Dachshund Jumper", "Quantity", "Personalization",
                     "None recorded", "42.5", "35.0", "Calle 1", "Hilo premium de lana merino",
                     "ESTIMATE", "no construction instructions", "Yes"):
            self.assertContains(page, text)

    def test_sheet_requires_staff(self):
        order = make_order()
        url = reverse("panel_order_sheet", args=[order.public_id])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.assertEqual(self.client.get(url).status_code, 403)
        import uuid

        self.client.force_login(staff())
        self.assertEqual(
            self.client.get(reverse("panel_order_sheet", args=[uuid.uuid4()])).status_code, 404
        )

    def test_internal_data_not_on_public_pages(self):
        order = pay(make_order("cable-knit-jumper"))
        page = self.client.get(reverse("order_detail", args=[order.public_id])).content.decode()
        for text in ("Workshop", "Hilo premium", "Readiness", "ESTIMATE", "REF-1", "35.00"):
            self.assertNotIn(text, page)

    def test_new_forms_require_staff_and_csrf(self):
        order = make_order()
        url = reverse("panel_order", args=[order.public_id])
        for data in ({"form": "size", "size_confirmed": "M"},
                     {"form": "tracking", "tracking_number": "T"}):
            self.assertEqual(self.client.post(url, data).status_code, 302)
        self.client.force_login(User.objects.create_user("u", password="x"))
        for data in ({"form": "size", "size_confirmed": "M"},
                     {"form": "tracking", "tracking_number": "T"}):
            self.assertEqual(self.client.post(url, data).status_code, 403)
        c = Client(enforce_csrf_checks=True)
        c.force_login(staff())
        self.assertEqual(c.post(url, {"form": "size", "size_confirmed": "M"}).status_code, 403)
        order.refresh_from_db()
        self.assertEqual((order.size_confirmed, order.tracking_number), ("", ""))

    def test_detail_shows_readiness_progress_and_forms(self):
        order = make_order()
        self.client.force_login(staff())
        page = self.client.get(reverse("panel_order", args=[order.public_id]))
        for text in ("Readiness", "Payment confirmed", "Order saved", "Workshop sheet",
                     "Save tracking", "Not ready to make"):
            self.assertContains(page, text)
        # La talla solo se pide confirmar cuando la referencia no es concluyente.
        self.assertNotContains(page, "Confirm size")
        ambiguous = ambiguous_order()
        page = self.client.get(reverse("panel_order", args=[ambiguous.public_id]))
        self.assertContains(page, "Confirm size")

    def test_tracking_is_escaped_in_panel(self):
        order = make_order()
        order.tracking_number = 'A"><b>x</b>'
        order.save()
        self.client.force_login(staff())
        page = self.client.get(reverse("panel_order", args=[order.public_id]))
        self.assertNotContains(page, "<b>x</b>")
