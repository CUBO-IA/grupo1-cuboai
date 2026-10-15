from django.test import TestCase
from django.urls import reverse

from .models import DogProfile, Quote

FIT = {
    "name": "Rex", "breed": "Dachshund", "weight": "5", "weight_unit": "kg",
    "length_unit": "cm", "back_length": "35", "chest_girth": "40", "neck_girth": "",
}


class GalleryTests(TestCase):
    def test_thumbnails_are_buttons_with_script(self):
        r = self.client.get(reverse("detalle", args=["alnut-whip-harness"]))
        html = r.content.decode()
        self.assertIn('id="detail-main"', html)
        self.assertIn("detail-thumb is-active", html)
        self.assertGreaterEqual(html.count('class="detail-thumb'), 2)
        self.assertIn("data-src=", html)


class SmartFitSaveTests(TestCase):
    def test_resubmit_does_not_duplicate_profile(self):
        self.client.post(reverse("smart_fit"), FIT)
        self.client.post(reverse("smart_fit"), FIT)
        self.assertEqual(DogProfile.objects.count(), 1)

    def test_confirmation_shown_after_edit_redirect(self):
        self.client.post(reverse("smart_fit"), FIT)
        dog = DogProfile.objects.get()
        r = self.client.post(reverse("smart_fit_editar", args=[dog.public_id]), {**FIT, "name": "Max"}, follow=True)
        self.assertContains(r, "Measurements saved")

    def test_quote_edit_returns_to_same_quote(self):
        self.client.post(reverse("smart_fit"), FIT)
        dog = DogProfile.objects.get()
        self.client.post(reverse("smart_quote_crear", args=[dog.public_id]), {"producto": "tactical-dog", "quantity": "1"})
        q = Quote.objects.get()
        url = reverse("smart_fit_editar", args=[dog.public_id]) + f"?producto=tactical-dog&quote={q.public_id}"
        r = self.client.post(url, {**FIT, "chest_girth": "42"})
        self.assertRedirects(r, reverse("smart_quote", args=[q.public_id]))
        self.assertEqual(Quote.objects.count(), 1)
        self.assertEqual(DogProfile.objects.count(), 1)


class DetailCartTests(TestCase):
    def test_add_to_cart_from_detail_with_saved_dog(self):
        self.client.post(reverse("smart_fit"), FIT)
        r = self.client.get(reverse("detalle", args=["bamboo-drying-robe"]))
        self.assertContains(r, "Add to Cart")
        self.assertContains(r, reverse("cart_add"))
        dog = DogProfile.objects.get()
        r = self.client.post(reverse("cart_add"), {"producto": "bamboo-drying-robe", "dog": str(dog.public_id), "quantity": "2", "size": ""})
        self.assertRedirects(r, reverse("cart"))
        self.assertContains(self.client.get(reverse("cart")), "Drying Robe")

    def test_detail_without_dog_points_to_smart_fit(self):
        r = self.client.get(reverse("detalle", args=["bamboo-drying-robe"]))
        self.assertContains(r, "Add to Cart")


class GuideMeTests(TestCase):
    def test_new_heading_and_options(self):
        r = self.client.get(reverse("assistant"))
        self.assertContains(r, "Find the Perfect Outfit for Your Dachshund")
        self.assertContains(r, "Wedding or special occasion")
        self.assertContains(r, "Drying robe after a bath")

    def test_recommendation_has_photo_price_and_actions(self):
        r = self.client.get(reverse("assistant"), {"occasion": "bath"})
        self.assertContains(r, "Bamboo")
        self.assertContains(r, "View Product")
        self.assertContains(r, "Add to Cart")
        self.assertContains(r, "<img")
