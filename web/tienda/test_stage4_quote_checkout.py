"""Etapa 4: cantidad, resumen comercial, paso de revisión y checkout."""

import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from . import services
from .models import DogProfile, Order, Quote

CUSTOMER = {
    "customer_name": "Ana Perez", "customer_email": "ana@example.com",
    "customer_phone": "+503 7000 0000", "country": "El Salvador",
    "city": "San Salvador", "address": "Calle 1 #2", "payment_method": "unspecified",
}



class BtcTestCase(TestCase):
    """TestCase base: el descuento Bitcoin es opt-in por producto (pendiente de
    confirmar por el negocio); estas pruebas lo habilitan explícitamente."""

    @classmethod
    def setUpTestData(cls):
        from .models import ProductPaymentRule

        ProductPaymentRule.objects.update(bitcoin_discount_eligible=True)


def make_dog(**kw):
    values = dict(
        name="Rex", breed="Dachshund", weight_kg=Decimal("7.50"),
        back_length_cm=Decimal("35.0"), chest_girth_cm=Decimal("42.5"),
    )
    values.update(kw)
    return DogProfile.objects.create(**values)


def make_quote(slug="wedding-dog", quantity=1, **kw):
    return services.create_quote(make_dog(**kw), slug, quantity)


class QuantityTests(BtcTestCase):
    def test_default_and_explicit_quantity(self):
        dog = make_dog()
        self.assertEqual(services.create_quote(dog, "cable-knit-jumper").quantity, 1)
        q = services.create_quote(dog, "cable-knit-jumper", 3)
        self.assertEqual(q.quantity, 3)
        self.assertEqual(Quote.objects.count(), 1)  # el borrador se reutiliza

    def test_invalid_quantities_rejected(self):
        dog = make_dog()
        for bad in (0, -1, 11, 100, "abc", "", None, "1.5"):
            with self.assertRaises(services.QuantityError, msg=repr(bad)):
                services.create_quote(dog, "cable-knit-jumper", bad)
        self.assertEqual(Quote.objects.count(), 0)

    def test_totals_use_quantity(self):
        q = make_quote("tactical-dog", 3)
        t = services.compute_totals(q)
        self.assertEqual(t["unit_price"], Decimal("300.00"))
        self.assertEqual(t["subtotal"], Decimal("900.00"))
        self.assertIsNone(t["shipping"])
        self.assertEqual(t["amount_due"], Decimal("900.00"))

    def test_bitcoin_discount_on_subtotal_not_shipping(self):
        q = make_quote("cable-knit-jumper", 4)
        t = services.compute_totals(q, "bitcoin")
        self.assertEqual(t["subtotal"], Decimal("600.00"))
        self.assertEqual(t["discount_amount"], Decimal("90.00"))
        self.assertEqual(t["total_if_discount"], Decimal("510.00"))
        self.assertEqual(t["amount_due"], Decimal("600.00"))  # aún no aplicado
        self.assertIsNone(t["shipping"])

    def test_unit_price_cap_guard(self):
        changed = {**services.PRODUCTOS["wedding-dog"], "precio": "$900"}
        with mock.patch.dict(services.PRODUCTOS, {"wedding-dog": changed}):
            with self.assertRaises(services.InvalidCatalogPrice):
                services.get_base_price("wedding-dog")
        edge = {**services.PRODUCTOS["wedding-dog"], "precio": "$850"}
        with mock.patch.dict(services.PRODUCTOS, {"wedding-dog": edge}):
            self.assertEqual(services.get_base_price("wedding-dog"), Decimal("850.00"))


class QuoteViewTests(TestCase):
    def test_create_quote_with_quantity_from_form(self):
        dog = make_dog()
        r = self.client.post(
            reverse("smart_quote_crear", args=[dog.public_id]),
            {"producto": "christmas-dog", "quantity": "2", "base_price": "1", "quantity_price": "9"},
        )
        quote = Quote.objects.get()
        self.assertEqual((quote.quantity, quote.base_price), (2, Decimal("250.00")))
        page = self.client.get(r.url)
        self.assertContains(page, "$500.00")
        self.assertContains(page, "Christmas Dog")
        self.assertContains(page, "tienda/img/christmas-dog.jpg")
        self.assertContains(page, "42.5")  # medidas confirmadas
        self.assertContains(page, "Reference size")
        self.assertContains(page, "Size adjustment")
        self.assertContains(page, "Shipping")

    def test_invalid_quantity_on_create(self):
        dog = make_dog()
        for bad in ("0", "11", "x", ""):
            r = self.client.post(
                reverse("smart_quote_crear", args=[dog.public_id]),
                {"producto": "cable-knit-jumper", "quantity": bad},
            )
            self.assertEqual(r.status_code, 400, bad)
        self.assertEqual(Quote.objects.count(), 0)

    def test_update_quantity(self):
        quote = make_quote("cable-knit-jumper")
        url = reverse("smart_quote_cantidad", args=[quote.public_id])
        r = self.client.post(url, {"quantity": "5"})
        self.assertRedirects(r, reverse("smart_quote", args=[quote.public_id]))
        quote.refresh_from_db()
        self.assertEqual(quote.quantity, 5)
        self.assertContains(self.client.get(r.url), "$750.00")
        r = self.client.post(url, {"quantity": "99"})
        self.assertEqual(r.status_code, 400)
        quote.refresh_from_db()
        self.assertEqual(quote.quantity, 5)

    def test_quantity_locked_after_order(self):
        quote = make_quote("cable-knit-jumper", 2)
        services.create_order(quote, CUSTOMER)
        r = self.client.post(
            reverse("smart_quote_cantidad", args=[quote.public_id]), {"quantity": "5"}
        )
        self.assertEqual(r.status_code, 400)
        quote.refresh_from_db()
        self.assertEqual(quote.quantity, 2)

    def test_edit_measurements_returns_to_quote(self):
        quote = make_quote("cable-knit-jumper")
        dog = quote.dog
        url = (
            reverse("smart_fit_editar", args=[dog.public_id])
            + f"?producto=cable-knit-jumper&quote={quote.public_id}"
        )
        data = {"name": "Rex", "breed": "Dachshund", "weight": "7.5", "weight_unit": "kg",
                "length_unit": "cm", "back_length": "38", "chest_girth": "44", "neck_girth": ""}
        r = self.client.post(url, data)
        self.assertRedirects(r, reverse("smart_quote", args=[quote.public_id]))
        dog.refresh_from_db()
        self.assertEqual(dog.back_length_cm, Decimal("38.0"))

    def test_quote_param_of_other_dog_is_ignored(self):
        quote = make_quote("cable-knit-jumper")
        other = make_dog()
        url = (
            reverse("smart_fit_editar", args=[other.public_id])
            + f"?quote={quote.public_id}"
        )
        data = {"name": "Rex", "breed": "Dachshund", "weight": "7.5", "weight_unit": "kg",
                "length_unit": "cm", "back_length": "38", "chest_girth": "44", "neck_girth": ""}
        r = self.client.post(url, data)
        self.assertRedirects(
            r, reverse("smart_fit_resultado", args=[other.public_id]),
            fetch_redirect_response=False,
        )
        r = self.client.post(reverse("smart_fit_editar", args=[other.public_id]) + "?quote=zzz", data)
        self.assertEqual(r.status_code, 302)

    def test_unknown_quote_404(self):
        for name in ("smart_quote", "smart_quote_cantidad", "checkout"):
            r = self.client.get(reverse(name, args=[uuid.uuid4()]))
            self.assertEqual(r.status_code, 404, name)

    def test_csrf_on_quantity(self):
        quote = make_quote("cable-knit-jumper")
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("smart_quote_cantidad", args=[quote.public_id]), {"quantity": "3"})
        self.assertEqual(r.status_code, 403)


class ReviewStepTests(BtcTestCase):
    def setUp(self):
        self.quote = make_quote("wedding-dog", 2)
        self.url = reverse("checkout", args=[self.quote.public_id])

    def test_checkout_form_sends_review_step(self):
        page = self.client.get(self.url)
        self.assertContains(page, 'name="step" value="review"')
        self.assertContains(page, "Review order")
        self.assertContains(page, "Quantity: 2")
        self.assertContains(page, "tienda/img/wedding-dog.jpg")

    def test_review_does_not_create_order(self):
        r = self.client.post(self.url, {**CUSTOMER, "step": "review"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(r, "Review your order")
        self.assertContains(r, "$1300.00")
        self.assertContains(r, "Confirm order")
        self.assertContains(r, "To be confirmed")
        self.assertContains(r, "does not charge you")

    def test_review_shows_bitcoin_discount_separately(self):
        r = self.client.post(
            self.url, {**CUSTOMER, "payment_method": "bitcoin", "step": "review"}
        )
        self.assertContains(r, "Bitcoin discount (15%)")
        self.assertContains(r, "-$195.00")
        self.assertContains(r, "$1105.00")  # si se verifica el pago
        self.assertContains(r, "Not applied yet")
        self.assertEqual(Order.objects.count(), 0)

    def test_review_with_invalid_data_returns_form(self):
        r = self.client.post(
            self.url, {**CUSTOMER, "customer_email": "nope", "step": "review"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Enter a valid email")
        self.assertNotContains(r, "Confirm order")

    def test_confirm_creates_order_with_quantity(self):
        r = self.client.post(self.url, {**CUSTOMER, "step": "confirm"})
        order = Order.objects.get()
        self.assertRedirects(r, reverse("order_detail", args=[order.public_id]))
        self.assertEqual(order.quantity, 2)
        self.assertEqual(order.total, Decimal("1300.00"))
        self.assertEqual(order.payment_status, "unpaid")
        snap = order.snapshot
        self.assertEqual((snap["quantity"], snap["unit_price"], snap["subtotal"]),
                         (2, "650.00", "1300.00"))
        self.assertEqual(snap["shipping"]["status"], "pending")
        page = self.client.get(r.url)
        self.assertContains(page, "Quantity")
        self.assertContains(page, "$1300.00")

    def test_confirm_with_bitcoin_discount_on_subtotal(self):
        self.client.post(self.url, {**CUSTOMER, "payment_method": "bitcoin", "step": "confirm"})
        order = Order.objects.get()
        self.assertEqual(order.discount_amount, Decimal("195.00"))
        self.assertEqual(order.discount_status, "pending_verification")
        self.assertEqual(order.amount_due, Decimal("1300.00"))
        self.assertEqual(order.amount_if_discount, Decimal("1105.00"))

    def test_direct_post_still_works_and_is_idempotent(self):
        self.client.post(self.url, CUSTOMER)
        self.client.post(self.url, CUSTOMER)
        self.assertEqual(Order.objects.count(), 1)

    def test_client_cannot_inject_amounts(self):
        self.client.post(
            self.url,
            {**CUSTOMER, "step": "confirm", "total": "1", "quantity": "1",
             "unit_price": "1", "discount_amount": "999"},
        )
        order = Order.objects.get()
        self.assertEqual((order.quantity, order.total), (2, Decimal("1300.00")))
        self.assertEqual(order.discount_amount, Decimal("0.00"))

    def test_review_escapes_user_input(self):
        r = self.client.post(
            self.url,
            {**CUSTOMER, "address": '"><script>alert(1)</script>', "step": "review"},
        )
        self.assertNotContains(r, "<script>alert(1)</script>")

    def test_csrf_on_review(self):
        c = Client(enforce_csrf_checks=True)
        r = c.post(self.url, {**CUSTOMER, "step": "review"})
        self.assertEqual(r.status_code, 403)


class CostWithQuantityTests(TestCase):
    def test_cost_scales_with_quantity_and_stays_private(self):
        quote = make_quote("cable-knit-jumper", 3)
        order, _ = services.create_order(quote, CUSTOMER)
        s = services.cost_summary(order)
        self.assertEqual(s["cost"], Decimal("105.00"))  # 3 × 35.00 (materiales)
        self.assertEqual(s["revenue"], Decimal("450.00"))
        self.assertEqual(s["margin"], Decimal("345.00"))
        page = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertNotContains(page, "105.00")
        self.assertNotContains(page, "345.00")
        staff = User.objects.create_user("s", password="x", is_staff=True)
        self.client.force_login(staff)
        panel = self.client.get(reverse("panel_order", args=[order.public_id]))
        self.assertContains(panel, "× 3")
