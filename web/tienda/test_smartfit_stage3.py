"""Etapa 3: Smart Fit — nombre opcional, perfil reutilizable/editable,
requisitos por prenda y talla de referencia."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from . import services
from .models import DogProfile, Order, ProductMeasurement, Quote, SizeRange
from .test_panel import make_order

FIT = {
    "name": "Luna", "breed": "Dachshund", "weight": "6", "weight_unit": "kg",
    "length_unit": "cm", "back_length": "33", "chest_girth": "40", "neck_girth": "",
}


def make_dog(**kw):
    values = dict(
        name="Rex", breed="Dachshund", weight_kg=Decimal("7.50"),
        back_length_cm=Decimal("35.0"), chest_girth_cm=Decimal("42.5"),
    )
    values.update(kw)
    return DogProfile.objects.create(**values)


class OptionalNameTests(TestCase):
    def test_name_optional(self):
        r = self.client.post(reverse("smart_fit"), {**FIT, "name": ""})
        dog = DogProfile.objects.get()
        self.assertEqual(dog.name, "")
        self.assertEqual(dog.display_name, "Unnamed dog")
        self.assertRedirects(r, reverse("smart_fit_resultado", args=[dog.public_id]))
        self.assertContains(self.client.get(r.url), "Unnamed dog")

    def test_unnamed_dog_through_quote_checkout_and_order(self):
        dog = make_dog(name="")
        quote = services.create_quote(dog, "cable-knit-jumper")
        self.assertContains(
            self.client.get(reverse("smart_quote", args=[quote.public_id])), "for Unnamed dog"
        )
        order, _ = services.create_order(quote, {
            "customer_name": "Ana", "customer_email": "a@example.com",
            "customer_phone": "+503 7000 0000", "country": "SV", "city": "SS",
            "address": "Calle 1", "payment_method": "unspecified",
        })
        self.assertContains(
            self.client.get(reverse("order_detail", args=[order.public_id])), "Unnamed dog"
        )

    def test_breed_and_measurements_still_required(self):
        r = self.client.post(reverse("smart_fit"), {})
        for field in ("breed", "weight", "back_length", "chest_girth"):
            self.assertIn(field, r.context["form"].errors)
        self.assertNotIn("name", r.context["form"].errors)


class EditAndReuseTests(TestCase):
    def test_edit_form_is_prefilled(self):
        dog = make_dog(neck_girth_cm=Decimal("25.0"))
        r = self.client.get(reverse("smart_fit_editar", args=[dog.public_id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Edit measurements")
        self.assertContains(r, 'value="Rex"')
        self.assertContains(r, 'value="35.0"')

    def test_edit_updates_same_profile(self):
        dog = make_dog()
        url = reverse("smart_fit_editar", args=[dog.public_id])
        r = self.client.post(url, {**FIT, "name": "Rex II", "back_length": "36"})
        self.assertRedirects(r, reverse("smart_fit_resultado", args=[dog.public_id]))
        dog.refresh_from_db()
        self.assertEqual(DogProfile.objects.count(), 1)
        self.assertEqual((dog.name, dog.back_length_cm), ("Rex II", Decimal("36.0")))

    def test_invalid_edit_changes_nothing_and_keeps_input(self):
        dog = make_dog()
        r = self.client.post(
            reverse("smart_fit_editar", args=[dog.public_id]), {**FIT, "weight": "900"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)
        dog.refresh_from_db()
        self.assertEqual(dog.weight_kg, Decimal("7.50"))

    def test_edit_in_other_units(self):
        dog = make_dog()
        self.client.post(
            reverse("smart_fit_editar", args=[dog.public_id]),
            {**FIT, "length_unit": "in", "back_length": "14", "chest_girth": "17",
             "weight_unit": "lb", "weight": "10"},
        )
        dog.refresh_from_db()
        self.assertEqual(dog.back_length_cm, Decimal("35.6"))
        self.assertEqual(dog.weight_kg, Decimal("4.54"))

    def test_order_keeps_original_measurements_after_edit(self):
        order = make_order(slug="cable-knit-jumper")
        dog = order.quote.dog
        self.client.post(
            reverse("smart_fit_editar", args=[dog.public_id]),
            {**FIT, "back_length": "50", "chest_girth": "60"},
        )
        dog.refresh_from_db()
        self.assertEqual(dog.back_length_cm, Decimal("50.0"))
        order.refresh_from_db()
        self.assertEqual(order.snapshot["dog"]["back_length_cm"], "35.0")
        page = self.client.get(reverse("order_detail", args=[order.public_id]))
        self.assertContains(page, "35.0 cm")
        self.assertNotContains(page, "50.0 cm")

    def test_unknown_profile_404_and_csrf(self):
        import uuid

        self.assertEqual(
            self.client.get(reverse("smart_fit_editar", args=[uuid.uuid4()])).status_code, 404
        )
        dog = make_dog()
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("smart_fit_editar", args=[dog.public_id]), FIT)
        self.assertEqual(r.status_code, 403)

    def test_saved_dogs_listed_for_same_session_only(self):
        self.client.post(reverse("smart_fit"), FIT)
        page = self.client.get(reverse("smart_fit"))
        self.assertContains(page, "Saved dogs")
        self.assertContains(page, "Luna")
        other = Client()
        self.assertNotContains(other.get(reverse("smart_fit")), "Saved dogs")

    def test_saved_dogs_limited_to_five(self):
        for i in range(7):
            self.client.post(reverse("smart_fit"), {**FIT, "name": f"Dog{i}"})
        self.assertEqual(len(self.client.session["dogs"]), 5)
        page = self.client.get(reverse("smart_fit"))
        self.assertContains(page, "Dog6")
        self.assertNotContains(page, "Dog0")


class RequirementTests(TestCase):
    def test_default_no_garment_requires_neck(self):
        self.assertEqual(
            set(
                ProductMeasurement.objects.filter(product_slug__in=list(services.PRODUCTOS))
                .values_list("product_slug", "requires_neck")
            ),
            {(slug, False) for slug in services.PRODUCTOS},
        )
        dog = make_dog()
        for slug in services.PRODUCTOS:
            self.assertEqual(services.missing_measurements(dog, slug), [])

    def _require_neck(self, slug):
        ProductMeasurement.objects.filter(product_slug=slug).update(requires_neck=True)

    def test_quote_blocked_until_neck_provided(self):
        self._require_neck("wedding-dog")
        dog = make_dog()  # sin cuello
        r = self.client.post(
            reverse("smart_quote_crear", args=[dog.public_id]), {"producto": "wedding-dog"}
        )
        edit = reverse("smart_fit_editar", args=[dog.public_id]) + "?producto=wedding-dog"
        self.assertRedirects(r, edit, fetch_redirect_response=False)
        self.assertEqual(Quote.objects.count(), 0)
        page = self.client.get(edit)
        self.assertContains(page, "required for this garment")

    def test_other_products_not_blocked(self):
        self._require_neck("wedding-dog")
        dog = make_dog()
        r = self.client.post(
            reverse("smart_quote_crear", args=[dog.public_id]), {"producto": "cable-knit-jumper"}
        )
        self.assertEqual(Quote.objects.count(), 1)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/quote/", r.url)

    def test_required_neck_enforced_on_form_and_flow_completes(self):
        self._require_neck("wedding-dog")
        dog = make_dog()
        url = reverse("smart_fit_editar", args=[dog.public_id]) + "?producto=wedding-dog"
        r = self.client.post(url, {**FIT, "neck_girth": ""})
        self.assertEqual(r.status_code, 200)
        self.assertIn("neck_girth", r.context["form"].errors)
        r = self.client.post(url, {**FIT, "neck_girth": "25"})
        self.assertRedirects(
            r,
            reverse("smart_fit_resultado", args=[dog.public_id]) + "?producto=wedding-dog",
            fetch_redirect_response=False,
        )
        r = self.client.post(
            reverse("smart_quote_crear", args=[dog.public_id]), {"producto": "wedding-dog"}
        )
        self.assertEqual(Quote.objects.count(), 1)

    def test_product_param_is_validated(self):
        r = self.client.get(reverse("smart_fit") + "?producto=<script>")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "<script>")
        r = self.client.get(reverse("smart_fit") + "?producto=nope")
        self.assertNotIn("required for this garment", r.content.decode())


class SizeReferenceTests(TestCase):
    def test_seeded_table(self):
        self.assertEqual(SizeRange.objects.count(), 9)
        self.assertFalse(SizeRange.objects.filter(is_validated=True).exists())
        self.assertEqual(
            list(SizeRange.objects.values_list("label", flat=True)),
            ["XS", "S", "M", "M", "L", "XL", "XL", "XXL", "XXXL"],
        )

    def test_matched_size_from_measurements(self):
        dog = make_dog(
            chest_girth_cm=Decimal("36"), back_length_cm=Decimal("28"),
            neck_girth_cm=Decimal("24"),
        )
        result = services.classify_size(dog)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["candidates"][0]["label"], "S")
        self.assertFalse(result["validated"])

    def test_breed_does_not_affect_size(self):
        a = make_dog(breed="Dachshund", chest_girth_cm=Decimal("36"), back_length_cm=Decimal("28"))
        b = make_dog(breed="Great Dane", chest_girth_cm=Decimal("36"), back_length_cm=Decimal("28"))
        self.assertEqual(services.classify_size(a), services.classify_size(b))
        c = make_dog(breed="Dachshund", chest_girth_cm=Decimal("80"), back_length_cm=Decimal("65"))
        self.assertNotEqual(
            services.classify_size(a)["candidates"], services.classify_size(c)["candidates"]
        )

    def test_ambiguous_and_outside(self):
        amb = services.classify_size(
            make_dog(chest_girth_cm=Decimal("46"), back_length_cm=Decimal("36"))
        )
        self.assertEqual(amb["status"], "ambiguous")
        self.assertGreater(len(amb["candidates"]), 1)
        out = services.classify_size(
            make_dog(chest_girth_cm=Decimal("20"), back_length_cm=Decimal("15"))
        )
        self.assertEqual(out["status"], "outside")
        self.assertEqual(out["candidates"], [])

    def test_neck_narrows_when_provided(self):
        base = make_dog(chest_girth_cm=Decimal("46"), back_length_cm=Decimal("36"))
        with_neck = make_dog(
            chest_girth_cm=Decimal("46"), back_length_cm=Decimal("36"), neck_girth_cm=Decimal("28")
        )
        self.assertEqual(services.classify_size(base)["status"], "ambiguous")
        r = services.classify_size(with_neck)
        self.assertEqual((r["status"], r["candidates"][0]["group"]), ("matched", "small"))
        self.assertTrue(r["used_neck"])

    def test_calculator_button_shows_reference_and_no_price(self):
        dog = make_dog(chest_girth_cm=Decimal("36"), back_length_cm=Decimal("28"))
        url = reverse("smart_fit_resultado", args=[dog.public_id])
        before = self.client.get(url)
        self.assertContains(before, "Calculate reference size")
        after = self.client.get(url + "?calcular=1")
        self.assertContains(after, "Reference only")
        self.assertContains(after, "not validated")
        self.assertNotContains(after, "$")

    def test_size_does_not_change_prices(self):
        small = make_dog(chest_girth_cm=Decimal("36"), back_length_cm=Decimal("28"))
        large = make_dog(chest_girth_cm=Decimal("80"), back_length_cm=Decimal("65"))
        for dog in (small, large):
            q = services.create_quote(dog, "wedding-dog")
            self.assertEqual(q.base_price, Decimal("650.00"))

    def test_order_snapshot_has_size_reference(self):
        order = make_order(slug="cable-knit-jumper")
        ref = order.snapshot["size_reference"]
        self.assertIn(ref["status"], {"matched", "ambiguous", "outside"})
        self.assertFalse(ref["validated"])
        self.assertIn("required_measurements", order.snapshot)


class PanelMeasurementsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.url = reverse("panel_measurements")

    def _post(self, **overrides):
        data = {}
        for row in SizeRange.objects.all():
            for f in ("neck_min", "neck_max", "chest_min", "chest_max", "back_min", "back_max"):
                data[f"{f}_{row.pk}"] = str(getattr(row, f))
        data.update(overrides)
        return data

    def test_permissions(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self._post()).status_code, 403)
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.staff)
        self.assertEqual(c.post(self.url, self._post()).status_code, 403)

    def test_page_and_update(self):
        self.client.force_login(self.staff)
        page = self.client.get(self.url)
        self.assertContains(page, "Not validated with tailoring")
        self.assertContains(page, "Requires neck girth")
        row = SizeRange.objects.first()
        r = self.client.post(
            self.url,
            self._post(**{
                f"chest_max_{row.pk}": "36.5",
                "neck_cable-knit-jumper": "on", "valid_cable-knit-jumper": "on",
                f"svalid_{row.pk}": "on",
            }),
        )
        self.assertRedirects(r, self.url)
        row.refresh_from_db()
        self.assertEqual(row.chest_max, Decimal("36.5"))
        self.assertTrue(row.is_validated)
        pm = ProductMeasurement.objects.get(product_slug="cable-knit-jumper")
        self.assertTrue(pm.requires_neck and pm.is_validated)
        self.assertFalse(ProductMeasurement.objects.get(product_slug="wedding-dog").requires_neck)

    def test_invalid_values_change_nothing(self):
        self.client.force_login(self.staff)
        row = SizeRange.objects.first()
        before = row.chest_max
        for bad in ({f"chest_max_{row.pk}": "abc"},
                    {f"chest_min_{row.pk}": "99", f"chest_max_{row.pk}": "10"},
                    {f"back_min_{row.pk}": "-1"}):
            r = self.client.post(self.url, self._post(**bad))
            self.assertEqual(r.status_code, 400)
            self.assertContains(r, "Nothing was saved", status_code=400)
        row.refresh_from_db()
        self.assertEqual(row.chest_max, before)
