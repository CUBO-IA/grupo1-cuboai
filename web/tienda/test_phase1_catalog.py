"""Fase 1 del catálogo v2: 8 productos, ficha pública de materiales, HOME,
producto retirado y flujo básico por producto."""

import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from . import services
from .catalog import PRODUCTOS, RETIRED_SLUGS
from .models import DogProfile, ProductPaymentRule, Quote

EXPECTED = [
    ("wedding-dog", "Waterproof Linen Dachshund Wedding Dog Suit Pair for Two", "650"),
    ("tactical-dog", "Tactical Dog", "300"),
    ("christmas-dog", "Christmas Dog", "250"),
    ("alnut-whip-harness", "Walnut Whip Dachshund Harness Fleece", "250.00"),
    ("beige-anti-rub-harness", "Beige Sophisticated Sausage Dachshund Anti-Rub Dog Harness", "63.00"),
    ("tutti-frutti-harness", "Tutti Frutti Houndstooth Anti-Rub Harness – Ribbon", "63.00"),
    ("cable-knit-jumper", "Luxury Cable Knit Dachshund Jumper", "150.00"),
    ("bamboo-drying-robe", "Showercover Bamboo Dachshund Drying Robe", "88.00"),
]


def make_dog():
    return DogProfile.objects.create(
        name="Rex", breed="Dachshund", weight_kg=Decimal("7.50"),
        back_length_cm=Decimal("35.0"), chest_girth_cm=Decimal("42.5"),
    )


class CatalogTests(TestCase):
    def test_exactly_the_eight_documented_products_in_order(self):
        self.assertEqual(list(PRODUCTOS), [e[0] for e in EXPECTED])
        for slug, name, price in EXPECTED:
            self.assertEqual(PRODUCTOS[slug]["nombre"], name)
            self.assertEqual(
                services.get_base_price(slug), Decimal(price).quantize(Decimal("0.01")), slug
            )

    def test_every_image_exists(self):
        for slug, item in PRODUCTOS.items():
            self.assertIn(item["imagen"], item["imagenes"])
            for path in item["imagenes"]:
                self.assertIsNotNone(finders.find(path), f"{slug}: {path}")

    def test_dog_sweater_is_retired(self):
        self.assertEqual(RETIRED_SLUGS, ("dog-sweater",))
        self.assertNotIn("dog-sweater", PRODUCTOS)
        self.assertEqual(self.client.get(reverse("detalle", args=["dog-sweater"])).status_code, 404)
        listing = self.client.get(reverse("productos")).content.decode()
        self.assertNotIn("Dog Sweater", listing)

    def test_listing_shows_all_products_with_prices_and_images(self):
        page = self.client.get(reverse("productos"))
        for slug, name, price in EXPECTED:
            self.assertContains(page, name)
            self.assertContains(page, PRODUCTOS[slug]["precio"])
            self.assertContains(page, PRODUCTOS[slug]["imagen"])
            self.assertContains(page, reverse("detalle", args=[slug]))

    def test_each_detail_page_has_description_and_cta(self):
        for slug, name, _ in EXPECTED:
            page = self.client.get(reverse("detalle", args=[slug]))
            self.assertEqual(page.status_code, 200, slug)
            self.assertContains(page, name)
            self.assertContains(page, PRODUCTOS[slug]["descripcion"])
            self.assertContains(page, reverse("smart_fit") + f"?producto={slug}")


class PublicMaterialsCardTests(TestCase):
    def test_materials_card_on_every_product(self):
        for slug in PRODUCTOS:
            page = self.client.get(reverse("detalle", args=[slug]))
            self.assertContains(page, "Materiales del traje")
            for m in PRODUCTOS[slug]["materiales"]:
                self.assertContains(page, m["nombre"])
                self.assertContains(page, m["funcion"])

    def test_materials_match_document_lists(self):
        names = lambda slug: [m["nombre"] for m in PRODUCTOS[slug]["materiales"]]
        self.assertIn("Polar fleece premium antipilling", names("alnut-whip-harness"))
        self.assertIn("Tela de rizo con fibra de bambú", names("bamboo-drying-robe"))
        self.assertIn("Nylon Cordura 1000D", names("tactical-dog"))
        self.assertEqual(len(names("alnut-whip-harness")), 9)
        self.assertEqual(len(names("cable-knit-jumper")), 7)
        self.assertEqual(len(names("bamboo-drying-robe")), 8)

    def test_public_card_has_no_prices_quantities_or_costs(self):
        for slug in PRODUCTOS:
            page = self.client.get(reverse("detalle", args=[slug])).content.decode()
            card = re.search(
                r'<section class="wk-materials".*?</section>', page, flags=re.S
            ).group(0)
            self.assertNotRegex(card, r"\$\s*\d")
            self.assertNotRegex(card, r"\d+(\.\d+)?\s*(m|kg|cono|unidad|lote)\b")
            for word in ("Consumption", "Unit price", "Subtotal", "Labor", "Margin", "margin"):
                self.assertNotIn(word, card, f"{slug}: {word}")
            self.assertNotRegex(card, r"\bcosts?\b|\bcosto")

    def test_internal_costs_are_not_in_catalog_data(self):
        text = repr(PRODUCTOS)
        for word in ("unit_price", "labor", "costo", "cost_", "margen"):
            self.assertNotIn(word, text)


class HomeTests(TestCase):
    def test_render_is_the_main_image_and_nothing_covers_it(self):
        page = self.client.get(reverse("inicio"))
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("tienda/img/home-render.jpg", html)
        self.assertIsNotNone(finders.find("tienda/img/home-render.jpg"))
        section = re.search(r'<section class="home-render".*?</section>', html, flags=re.S).group(0)
        # Dentro del render solo hay la imagen y la cinta de navegación.
        self.assertEqual(section.count("<img"), 1)
        self.assertEqual(section.count("<nav"), 1)
        for tag in ("<h1", "<h2", "<p", "<button", "class=\"card\"", "class=\"button\""):
            self.assertNotIn(tag, section)
        self.assertIn(reverse("productos"), section)
        self.assertIn(reverse("smart_fit"), section)

    def test_home_links_to_products_and_smart_fit(self):
        page = self.client.get(reverse("inicio"))
        self.assertContains(page, "View Products")
        self.assertContains(page, "Start Smart Fit")

    def test_render_file_matches_source_dimensions(self):
        # Lee el encabezado JPEG (SOF) sin depender de Pillow.
        import struct

        path = finders.find("tienda/img/home-render.jpg")
        with open(path, "rb") as f:
            data = f.read()
        self.assertEqual(data[:2], b"\xff\xd8")
        i, size = 2, None
        while i < len(data):
            marker = data[i + 1]
            length = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                size = (width, height)
                break
            i += 2 + length
        self.assertEqual(size, (1671, 941))


class RetiredProductTests(TestCase):
    def test_existing_quote_of_retired_product_is_unavailable(self):
        quote = Quote.objects.create(
            dog=make_dog(), product_slug="dog-sweater", base_price=Decimal("125.00")
        )
        for name in ("smart_quote", "checkout"):
            r = self.client.get(reverse(name, args=[quote.public_id]))
            self.assertEqual(r.status_code, 410, name)
            self.assertContains(r, "no longer available", status_code=410)

    def test_retired_product_cannot_be_quoted(self):
        dog = make_dog()
        with self.assertRaises(services.UnknownProduct):
            services.create_quote(dog, "dog-sweater")
        r = self.client.post(
            reverse("smart_quote_crear", args=[dog.public_id]), {"producto": "dog-sweater"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Quote.objects.count(), 0)


class FlowForEachProductTests(TestCase):
    CUSTOMER = {
        "customer_name": "Ana Perez", "customer_email": "ana@example.com",
        "customer_phone": "+503 7000 0000", "country": "El Salvador",
        "city": "San Salvador", "address": "Calle 1", "payment_method": "unspecified",
    }

    def test_quote_and_order_for_every_product(self):
        for slug, name, price in EXPECTED:
            dog = make_dog()
            r = self.client.post(
                reverse("smart_quote_crear", args=[dog.public_id]), {"producto": slug}
            )
            quote = Quote.objects.get(dog=dog)
            self.assertRedirects(r, reverse("smart_quote", args=[quote.public_id]))
            page = self.client.get(r.url)
            self.assertContains(page, name)
            self.assertContains(page, PRODUCTOS[slug]["imagen"])
            self.assertContains(page, "Provisional quote")
            order, _ = services.create_order(quote, self.CUSTOMER)
            self.assertEqual(order.total, Decimal(price).quantize(Decimal("0.01")))
            self.assertEqual(order.snapshot["product"]["name"], name)
            self.assertEqual(order.payment_status, "unpaid")

    def test_price_stays_below_cap(self):
        for slug in PRODUCTOS:
            self.assertLessEqual(services.get_base_price(slug), services.UNIT_PRICE_CAP)


class CostWarningsTests(TestCase):
    def test_new_products_show_incomplete_cost_warning_to_staff_only(self):
        staff = User.objects.create_user("s", password="x", is_staff=True)
        url = reverse("panel_product_cost", args=["bamboo-drying-robe"])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(staff)
        page = self.client.get(url)
        self.assertContains(page, "Labor and other production costs have not been entered")
        index = self.client.get(reverse("panel_costs"))
        self.assertEqual(index.content.decode().count("View / edit"), 8)
        self.assertContains(index, "labor/other not set")


class AssistantCatalogTests(TestCase):
    def test_assistant_knows_new_products_and_asks_about_harnesses(self):
        page = self.client.get(reverse("assistant"), {"q": "price of the bamboo robe"})
        self.assertContains(page, "$88.00")
        page = self.client.get(reverse("assistant"), {"q": "price of the harness"})
        self.assertContains(page, "more than one product")
        for key in ("walks", "warmth", "bath"):
            self.assertEqual(
                self.client.get(reverse("assistant"), {"occasion": key}).status_code, 200
            )

    def test_discount_eligibility_follows_commercial_listing(self):
        eligible = set(
            ProductPaymentRule.objects.filter(
                product_slug__in=list(PRODUCTOS), bitcoin_discount_eligible=True
            ).values_list("product_slug", flat=True)
        )
        self.assertEqual(eligible, {"cable-knit-jumper", "bamboo-drying-robe"})
