"""Task 7: flujo completo Catálogo → Smart Fit → cotización → checkout →
pedido → panel privado, usando solo las URLs públicas."""

import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from .models import DogProfile, Order, OrderEvent, Quote
from .views import PRODUCTOS

FIT = {
    "name": "Luna", "breed": "Dachshund", "weight": "6", "weight_unit": "kg",
    "length_unit": "cm", "back_length": "33", "chest_girth": "40", "neck_girth": "",
}
CUSTOMER = {
    "customer_name": "Ana Perez", "customer_email": "ana@example.com",
    "customer_phone": "+503 7000 0000", "country": "El Salvador",
    "city": "San Salvador", "address": "Calle 1 #2",
}


def uuid_in(url):
    return re.search(r"[0-9a-f-]{36}", url).group(0)


class StaticAndPagesTests(TestCase):
    def test_static_assets_exist(self):
        for path in ("tienda/css/style.css", "tienda/js/script.js", "tienda/img/hero.JPG"):
            self.assertIsNotNone(finders.find(path), path)

    def test_public_pages_reference_working_static(self):
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "tienda/css/style.css")
        for slug, item in PRODUCTOS.items():
            self.assertIsNotNone(finders.find(item["imagen"]))
            self.assertEqual(self.client.get(reverse("detalle", args=[slug])).status_code, 200)
        for name in ("inicio", "productos", "smart_fit"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_unknown_product_404(self):
        self.assertEqual(self.client.get(reverse("detalle", args=["nope"])).status_code, 404)


class EndToEndTests(TestCase):
    def test_full_flow_through_panel(self):
        # 1. Smart Fit
        r = self.client.post(reverse("smart_fit"), FIT)
        self.assertEqual(r.status_code, 302)
        dog_id = uuid_in(r.url)
        self.assertContains(self.client.get(r.url), "Luna")

        # 2. Cotización
        r = self.client.post(
            reverse("smart_quote_crear", args=[dog_id]), {"producto": "christmas-dog"}
        )
        self.assertContains(self.client.get(r.url), "$250.00")
        quote_id = uuid_in(r.url)

        # 3. Checkout (con doble envío accidental)
        checkout = reverse("checkout", args=[quote_id])
        self.assertContains(self.client.get(checkout), "Provisional price")
        r1 = self.client.post(checkout, CUSTOMER)
        r2 = self.client.post(checkout, CUSTOMER)
        self.assertEqual(r1.url, r2.url)
        self.assertEqual(Order.objects.count(), 1)

        # 4. Confirmación: no pagado
        page = self.client.get(r1.url)
        self.assertContains(page, "WK-000001")
        self.assertContains(page, "no payment has been collected")
        self.assertNotContains(page, "Payment</dt><dd>Paid")

        # 5. Panel
        staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("panel_orders")).status_code, 302)
        self.client.force_login(staff)
        listing = self.client.get(reverse("panel_orders"), {"q": "Ana"})
        self.assertContains(listing, "WK-000001")
        detail_url = reverse("panel_order", args=[uuid_in(r1.url)])
        self.assertContains(self.client.get(detail_url), "Christmas Dog")

        # 6. Ciclo de estados
        for field, value, note in (
            ("status", "confirmed", ""),
            ("payment_status", "paid", "BANK-1"),
            ("production_status", "in_production", ""),
            ("production_status", "completed", ""),
            ("shipping_status", "shipped", ""),
            ("shipping_status", "delivered", ""),
        ):
            r = self.client.post(detail_url, {"field": field, "value": value, "note": note})
            self.assertRedirects(r, detail_url)
        order = Order.objects.get()
        self.assertEqual(
            (order.status, order.payment_status, order.production_status, order.shipping_status),
            ("confirmed", "paid", "completed", "delivered"),
        )
        self.assertEqual(OrderEvent.objects.count(), 6)

        # El cliente ve los estados reales
        public = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertContains(public, "Delivered")

    def test_amounts_are_decimal_everywhere(self):
        self.client.post(reverse("smart_fit"), FIT)
        dog = DogProfile.objects.get()
        self.client.post(
            reverse("smart_quote_crear", args=[dog.public_id]), {"producto": "wedding-dog"}
        )
        quote = Quote.objects.get()
        self.client.post(reverse("checkout", args=[quote.public_id]), CUSTOMER)
        order = Order.objects.get()
        for value in (quote.base_price, order.total):
            self.assertIsInstance(value, Decimal)
        self.assertEqual(order.total, Decimal("650.00"))

    def test_persistence_survives_new_session(self):
        self.client.post(reverse("smart_fit"), FIT)
        dog = DogProfile.objects.get()
        fresh = self.client_class()
        r = fresh.get(reverse("smart_fit_resultado", args=[dog.public_id]))
        self.assertContains(r, "Luna")
        self.assertContains(r, "33.0 cm")


class PaidWordingTests(TestCase):
    def test_paid_order_does_not_say_no_payment_collected(self):
        from . import services as svc
        from .test_panel import make_order

        order = make_order()
        page = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertContains(page, "no payment has been collected")
        svc.apply_transition(order, "payment_status", "paid", note="BANK-1")
        page = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertNotContains(page, "no payment has been collected")
        self.assertContains(page, "recorded by Weiner Kingdom")
        self.assertNotContains(page, "BANK-1")


class DatabaseConcurrencyConfigTests(TestCase):
    def test_sqlite_writes_wait_instead_of_failing(self):
        from django.conf import settings

        options = settings.DATABASES["default"]["OPTIONS"]
        self.assertEqual(options["transaction_mode"], "IMMEDIATE")
        self.assertGreaterEqual(options["timeout"], 5)
