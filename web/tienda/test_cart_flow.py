from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import DogProfile, Order, Quote

FIT = {
    "name": "Rex", "breed": "Dachshund", "weight": "5", "weight_unit": "kg",
    "length_unit": "cm", "back_length": "35", "chest_girth": "40", "neck_girth": "",
}


class AddToCartWithoutMeasurementsTests(TestCase):
    def add(self, slug, **extra):
        data = {"producto": slug, "quantity": "1"}
        data.update(extra)
        return self.client.post(reverse("cart_add"), data)

    def test_add_goes_to_cart_not_smart_fit(self):
        r = self.add("tactical-dog")
        self.assertRedirects(r, reverse("cart"))
        q = Quote.objects.get()
        self.assertIsNone(q.dog)
        self.assertEqual(q.base_price, Decimal("300.00"))
        page = self.client.get(reverse("cart"))
        self.assertContains(page, "Tactical Dog")
        self.assertContains(page, "Measurements pending")
        self.assertContains(page, "tactical-dog")
        self.assertEqual(Order.objects.count(), 0)

    def test_add_several_and_totals_from_catalog(self):
        self.add("tactical-dog")
        self.add("bamboo-drying-robe", quantity="2")
        page = self.client.get(reverse("cart"))
        self.assertContains(page, "$476.00")
        self.assertEqual(Quote.objects.count(), 2)

    def test_same_product_merges_and_header_counts_units(self):
        self.add("tactical-dog")
        self.add("tactical-dog", quantity="2")
        self.assertEqual(Quote.objects.get().quantity, 3)
        self.assertContains(self.client.get(reverse("productos")), "Cart, 3 items")

    def test_cart_persists_across_navigation(self):
        self.add("tactical-dog")
        for name in ("productos", "inicio", "assistant"):
            self.client.get(reverse(name))
        self.client.get(reverse("detalle", args=["tactical-dog"]))
        self.assertContains(self.client.get(reverse("cart")), "Tactical Dog")
        self.assertEqual(Quote.objects.count(), 1)

    def test_update_and_remove_and_empty_state(self):
        self.add("tactical-dog")
        q = Quote.objects.get()
        self.client.post(reverse("cart_line_update", args=[q.public_id]), {"quantity": "4", "size": ""})
        q.refresh_from_db()
        self.assertEqual(q.quantity, 4)
        self.assertContains(self.client.get(reverse("cart")), "$1200.00")
        self.client.post(reverse("cart_line_remove", args=[q.public_id]))
        self.assertContains(self.client.get(reverse("cart")), "Your cart is empty")

    def test_checkout_blocked_until_measurements(self):
        self.add("tactical-dog")
        r = self.client.get(reverse("cart_checkout"))
        self.assertRedirects(r, reverse("cart"))

    def test_catalog_card_and_detail_use_same_flow(self):
        self.assertContains(self.client.get(reverse("productos")), reverse("cart_add"))
        self.assertContains(self.client.get(reverse("detalle", args=["tactical-dog"])), reverse("cart_add"))

    def test_smart_fit_from_cart_attaches_and_returns(self):
        self.add("tactical-dog")
        q = Quote.objects.get()
        url = reverse("smart_fit") + f"?producto=tactical-dog&line={q.public_id}"
        r = self.client.post(url, FIT)
        self.assertRedirects(r, reverse("cart"))
        q.refresh_from_db()
        self.assertIsNotNone(q.dog)
        self.assertEqual(Quote.objects.count(), 1)
        self.assertEqual(DogProfile.objects.count(), 1)
        self.assertContains(self.client.get(reverse("cart")), "Checkout (1 item)")

    def test_use_saved_dog_for_pending_line(self):
        self.client.post(reverse("smart_fit"), FIT)
        dog = DogProfile.objects.get()
        self.add("tactical-dog")
        q = Quote.objects.get()
        self.client.post(reverse("cart_line_update", args=[q.public_id]),
                         {"quantity": "1", "size": "", "dog": str(dog.public_id)})
        q.refresh_from_db()
        self.assertEqual(q.dog_id, dog.pk)

    def test_pending_quote_pages_redirect_to_cart(self):
        self.add("tactical-dog")
        q = Quote.objects.get()
        for name in ("smart_quote", "checkout"):
            r = self.client.get(reverse(name, args=[q.public_id]))
            self.assertRedirects(r, reverse("cart"))

    def test_complete_checkout_creates_one_order(self):
        self.add("tactical-dog")
        q = Quote.objects.get()
        self.client.post(reverse("smart_fit") + f"?line={q.public_id}", FIT)
        data = {
            "customer_name": "Ana Perez", "customer_email": "ana@example.com", "customer_phone": "+503 7000 0000",
            "country": "El Salvador", "city": "San Salvador", "address": "Calle 1 #2",
            "payment_method": "unspecified", "step": "confirm",
        }
        r = self.client.post(reverse("cart_checkout"), data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.get().lines.count(), 1)
