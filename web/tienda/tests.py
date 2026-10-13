import uuid
from decimal import Decimal

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from .models import DogProfile, Order, Quote
from .views import PRODUCTOS

EXPECTED = {
    "wedding-dog": ("Wedding Dog", "$650"),
    "tactical-dog": ("Tactical Dog", "$300"),
    "christmas-dog": ("Christmas Dog", "$250"),
    "dog-sweater": ("Dog Sweater", "$125"),
}


class CatalogTests(TestCase):
    def test_catalog_names_and_prices(self):
        self.assertEqual(set(PRODUCTOS), set(EXPECTED))
        for slug, (name, price) in EXPECTED.items():
            self.assertEqual(PRODUCTOS[slug]["nombre"], name)
            self.assertEqual(PRODUCTOS[slug]["precio"], price)

    def test_catalog_images_exist(self):
        for item in PRODUCTOS.values():
            self.assertIsNotNone(finders.find(item["imagen"]), item["imagen"])

    def test_pages_render(self):
        for name in ("inicio", "productos"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for slug in EXPECTED:
            url = reverse("detalle", args=[slug])
            self.assertEqual(self.client.get(url).status_code, 200)


class ModelTests(TestCase):
    def test_dog_quote_order_chain(self):
        dog = DogProfile.objects.create(
            name="Rex",
            breed="Dachshund",
            weight_kg=Decimal("7.50"),
            back_length_cm=Decimal("35.0"),
            chest_girth_cm=Decimal("42.5"),
        )
        quote = Quote.objects.create(
            dog=dog, product_slug="dog-sweater", base_price=Decimal("125.00")
        )
        order = Order.objects.create(quote=quote, total=Decimal("125.00"))
        self.assertEqual(quote.status, Quote.Status.DRAFT)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertIsNone(quote.total_price)
        self.assertEqual(dog.quotes.get(), quote)
        self.assertEqual(quote.order, order)


from django.urls import reverse as _reverse  # noqa: E402


def _valid_post(**overrides):
    data = {
        "name": "Rex",
        "breed": "Dachshund",
        "weight": "7.5",
        "weight_unit": "kg",
        "length_unit": "cm",
        "back_length": "35",
        "chest_girth": "42.5",
        "neck_girth": "",
    }
    data.update(overrides)
    return data


class SmartFitTests(TestCase):
    url = _reverse("smart_fit")

    def test_get_renders_form(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "csrfmiddlewaretoken")

    def test_valid_submission_persists_and_reloads(self):
        r = self.client.post(self.url, _valid_post())
        dog = DogProfile.objects.get()
        self.assertRedirects(r, _reverse("smart_fit_resultado", args=[dog.public_id]))
        self.assertEqual(dog.weight_kg, Decimal("7.50"))
        self.assertEqual(dog.back_length_cm, Decimal("35.0"))
        self.assertEqual(dog.chest_girth_cm, Decimal("42.5"))
        self.assertIsNone(dog.neck_girth_cm)
        page = self.client.get(r.url)
        self.assertContains(page, "Rex")
        self.assertContains(page, "7.50 kg")
        self.assertContains(page, "Not provided")

    def test_units_are_converted(self):
        self.client.post(
            self.url,
            _valid_post(
                weight="10", weight_unit="lb", length_unit="in",
                back_length="14", chest_girth="17", neck_girth="10",
            ),
        )
        dog = DogProfile.objects.get()
        self.assertEqual(dog.weight_kg, Decimal("4.54"))
        self.assertEqual(dog.back_length_cm, Decimal("35.6"))
        self.assertEqual(dog.chest_girth_cm, Decimal("43.2"))
        self.assertEqual(dog.neck_girth_cm, Decimal("25.4"))

    def test_empty_required_fields(self):
        r = self.client.post(self.url, {})
        self.assertEqual(r.status_code, 200)
        for field in ("name", "breed", "weight", "back_length", "chest_girth"):
            self.assertIn(field, r.context["form"].errors)
        self.assertNotIn("neck_girth", r.context["form"].errors)
        self.assertEqual(DogProfile.objects.count(), 0)

    def test_invalid_values_rejected_and_input_kept(self):
        for override in (
            {"weight": "abc"},
            {"weight": "-3"},
            {"weight": "0"},
            {"weight": "500"},
            {"weight": "7.555"},
            {"back_length": "1000"},
            {"chest_girth": "2"},
            {"neck_girth": "999"},
            {"weight_unit": "stone"},
            {"length_unit": "ft"},
            {"name": "   "},
        ):
            r = self.client.post(self.url, _valid_post(**{"name": "Kept", **override}))
            self.assertEqual(r.status_code, 200, override)
            self.assertTrue(r.context["form"].errors, override)
            self.assertEqual(DogProfile.objects.count(), 0, override)
            if "name" not in override:
                self.assertContains(r, 'value="Kept"')

    def test_unit_aware_range(self):
        # 100 in = 254 cm: fuera de rango aunque 100 sea válido en cm.
        r = self.client.post(self.url, _valid_post(length_unit="in", back_length="100"))
        self.assertIn("back_length", r.context["form"].errors)

    def test_csrf_enforced(self):
        from django.test import Client

        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(self.url, _valid_post()).status_code, 403)
        self.assertEqual(DogProfile.objects.count(), 0)

    def test_result_404_for_unknown_profile(self):
        self.assertEqual(
            self.client.get(_reverse("smart_fit_resultado", args=[uuid.uuid4()])).status_code, 404
        )


from . import services  # noqa: E402


def _make_dog():
    return DogProfile.objects.create(
        name="Rex", breed="Dachshund", weight_kg=Decimal("7.50"),
        back_length_cm=Decimal("35.0"), chest_girth_cm=Decimal("42.5"),
    )


class QuoteServiceTests(TestCase):
    def test_base_prices_are_decimal(self):
        self.assertEqual(services.get_base_price("wedding-dog"), Decimal("650.00"))
        self.assertEqual(services.get_base_price("tactical-dog"), Decimal("300.00"))
        self.assertEqual(services.get_base_price("christmas-dog"), Decimal("250.00"))
        self.assertEqual(services.get_base_price("dog-sweater"), Decimal("125.00"))

    def test_unknown_product(self):
        for slug in ("", "nope", "../etc"):
            with self.assertRaises(services.UnknownProduct):
                services.get_base_price(slug)

    def test_invalid_catalog_price(self):
        from unittest import mock

        for bad in ("abc", "$0", "-$5"):
            patched = {"x": {"nombre": "X", "precio": bad}}
            with mock.patch.dict(services.PRODUCTOS, patched, clear=True):
                with self.assertRaises(services.InvalidCatalogPrice):
                    services.get_base_price("x")

    def test_create_quote_is_provisional_and_reused(self):
        dog = _make_dog()
        q = services.create_quote(dog, "dog-sweater")
        self.assertEqual(q.base_price, Decimal("125.00"))
        self.assertIsNone(q.total_price)
        self.assertEqual(q.pricing, Quote.Pricing.PROVISIONAL)
        self.assertEqual(q.status, Quote.Status.DRAFT)
        self.assertEqual(services.create_quote(dog, "dog-sweater").pk, q.pk)
        self.assertEqual(Quote.objects.count(), 1)

    def test_breakdown_provisional(self):
        q = services.create_quote(_make_dog(), "wedding-dog")
        b = services.build_breakdown(q)
        self.assertFalse(b["is_final"])
        self.assertEqual(b["total"], Decimal("650.00"))
        self.assertIsNone(b["lines"][1]["amount"])


class QuoteViewTests(TestCase):
    def test_quote_flow(self):
        dog = _make_dog()
        url = _reverse("smart_quote_crear", args=[dog.public_id])
        r = self.client.post(url, {"producto": "tactical-dog"})
        quote = Quote.objects.get()
        self.assertRedirects(r, _reverse("smart_quote", args=[quote.public_id]))
        page = self.client.get(r.url)
        self.assertContains(page, "Provisional quote")
        self.assertContains(page, "$300.00")
        self.assertContains(page, "Tactical Dog")

    def test_client_cannot_set_price(self):
        dog = _make_dog()
        self.client.post(
            _reverse("smart_quote_crear", args=[dog.public_id]),
            {"producto": "dog-sweater", "base_price": "1", "total_price": "1",
             "pricing": "final", "status": "accepted"},
        )
        q = Quote.objects.get()
        self.assertEqual(q.base_price, Decimal("125.00"))
        self.assertIsNone(q.total_price)
        self.assertEqual(q.pricing, Quote.Pricing.PROVISIONAL)
        self.assertEqual(q.status, Quote.Status.DRAFT)

    def test_unknown_product_and_missing_dog(self):
        dog = _make_dog()
        r = self.client.post(_reverse("smart_quote_crear", args=[dog.public_id]), {"producto": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Quote.objects.count(), 0)
        r = self.client.post(_reverse("smart_quote_crear", args=[uuid.uuid4()]), {"producto": "dog-sweater"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.get(_reverse("smart_quote", args=[uuid.uuid4()])).status_code, 404)

    def test_get_on_create_redirects_without_creating(self):
        dog = _make_dog()
        r = self.client.get(_reverse("smart_quote_crear", args=[dog.public_id]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Quote.objects.count(), 0)

    def test_csrf_enforced(self):
        from django.test import Client

        dog = _make_dog()
        c = Client(enforce_csrf_checks=True)
        r = c.post(_reverse("smart_quote_crear", args=[dog.public_id]), {"producto": "dog-sweater"})
        self.assertEqual(r.status_code, 403)


def _customer(**overrides):
    data = {
        "customer_name": "Ana Perez",
        "customer_email": "ana@example.com",
        "customer_phone": "+503 7000 0000",
        "country": "El Salvador",
        "city": "San Salvador",
        "address": "Calle 1 #2",
    }
    data.update(overrides)
    return data


class CheckoutTests(TestCase):
    def setUp(self):
        self.dog = _make_dog()
        self.quote = services.create_quote(self.dog, "tactical-dog")
        self.url = _reverse("checkout", args=[self.quote.public_id])

    def test_get_shows_review(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Tactical Dog")
        self.assertContains(r, "$300.00")
        self.assertContains(r, "Provisional price")
        self.assertContains(r, "csrfmiddlewaretoken")

    def test_valid_order_created(self):
        r = self.client.post(self.url, _customer())
        order = Order.objects.get()
        self.assertRedirects(r, _reverse("order_detail", args=[order.public_id]))
        self.assertEqual(order.quote, self.quote)
        self.assertEqual(order.total, Decimal("300.00"))
        self.assertTrue(order.price_is_provisional)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment_status, Order.PaymentStatus.UNPAID)
        self.assertEqual(order.production_status, Order.ProductionStatus.NOT_STARTED)
        self.assertEqual(order.shipping_status, Order.ShippingStatus.NOT_SHIPPED)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.status, Quote.Status.ACCEPTED)
        page = self.client.get(r.url)
        self.assertContains(page, order.number)
        self.assertContains(page, "no payment has been collected")
        self.assertContains(page, "Unpaid")

    def test_resubmission_does_not_duplicate(self):
        self.client.post(self.url, _customer())
        r = self.client.post(self.url, _customer(customer_name="Other"))
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.get().customer_name, "Ana Perez")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_service_idempotent(self):
        o1, created1 = services.create_order(self.quote, _customer())
        o2, created2 = services.create_order(self.quote, _customer())
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(o1.pk, o2.pk)

    def test_invalid_fields(self):
        for override in (
            {"customer_name": ""},
            {"customer_email": "nope"},
            {"customer_phone": "abc"},
            {"customer_phone": "123"},
            {"country": ""},
            {"city": ""},
            {"address": ""},
            {"address": "x" * 301},
        ):
            r = self.client.post(self.url, _customer(**override))
            self.assertEqual(r.status_code, 200, override)
            self.assertTrue(r.context["form"].errors, override)
        self.assertEqual(Order.objects.count(), 0)

    def test_input_kept_on_error(self):
        r = self.client.post(self.url, _customer(customer_email="bad", city="Santa Ana"))
        self.assertContains(r, "Santa Ana")

    def test_client_cannot_set_total(self):
        self.client.post(
            self.url, _customer(total="1", price_is_provisional="", payment_status="paid")
        )
        order = Order.objects.get()
        self.assertEqual(order.total, Decimal("300.00"))
        self.assertEqual(order.payment_status, Order.PaymentStatus.UNPAID)

    def test_total_recalculated_from_catalog(self):
        from unittest import mock

        changed = {**services.PRODUCTOS["tactical-dog"], "precio": "$310"}
        with mock.patch.dict(services.PRODUCTOS, {"tactical-dog": changed}):
            self.client.post(self.url, _customer())
        order = Order.objects.get()
        self.assertEqual(order.total, Decimal("310.00"))
        self.assertEqual(order.snapshot["base_price"], "310.00")

    def test_snapshot_survives_catalog_and_dog_changes(self):
        self.client.post(self.url, _customer())
        order = Order.objects.get()
        self.dog.weight_kg = Decimal("20.00")
        self.dog.name = "Changed"
        self.dog.save()
        order.refresh_from_db()
        self.assertEqual(order.snapshot["dog"]["name"], "Rex")
        self.assertEqual(order.snapshot["dog"]["weight_kg"], "7.50")
        self.assertEqual(order.snapshot["product"]["name"], "Tactical Dog")
        self.assertEqual(order.snapshot["pricing"], "provisional")

    def test_unknown_ids_404_and_int_ids_do_not_route(self):
        for name in ("checkout", "order_detail", "smart_quote", "smart_fit_resultado"):
            r = self.client.get(_reverse(name, args=[uuid.uuid4()]))
            self.assertEqual(r.status_code, 404, name)
        self.assertEqual(self.client.get("/quote/1/").status_code, 404)
        self.assertEqual(self.client.get("/order/1/").status_code, 404)
        self.assertEqual(self.client.get("/smart-fit/1/").status_code, 404)

    def test_cancelled_quote_blocked(self):
        self.quote.status = Quote.Status.CANCELLED
        self.quote.save()
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.post(self.url, _customer()).status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_csrf_enforced(self):
        from django.test import Client

        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(self.url, _customer()).status_code, 403)
        self.assertEqual(Order.objects.count(), 0)

    def test_full_flow(self):
        r = self.client.post(
            _reverse("smart_fit"),
            {"name": "Luna", "breed": "Dachshund", "weight": "6", "weight_unit": "kg",
             "length_unit": "cm", "back_length": "33", "chest_girth": "40", "neck_girth": ""},
        )
        r = self.client.post(
            _reverse("smart_quote_crear", args=[DogProfile.objects.get(name="Luna").public_id]),
            {"producto": "wedding-dog"},
        )
        r = self.client.get(r.url)
        self.assertContains(r, "$650.00")
        quote = Quote.objects.get(product_slug="wedding-dog")
        r = self.client.post(_reverse("checkout", args=[quote.public_id]), _customer())
        self.assertContains(self.client.get(r.url), "Luna")
        self.assertEqual(Order.objects.get().total, Decimal("650.00"))
