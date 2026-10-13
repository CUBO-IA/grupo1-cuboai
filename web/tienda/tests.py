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
        self.assertRedirects(r, _reverse("smart_fit_resultado", args=[dog.pk]))
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
            self.client.get(_reverse("smart_fit_resultado", args=[999])).status_code, 404
        )
