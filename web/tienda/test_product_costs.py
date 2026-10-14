"""Etapa 2: tablas de materiales, costo por producto, margen y privacidad."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from . import services
from .models import MaterialLine, ProductCost
from .test_panel import make_order


def post_data(slug, **overrides):
    """Datos de formulario que reproducen los valores actuales."""
    summary = services.product_cost_summary(slug)
    data = {
        "labor_cost": str(summary["labor_cost"]),
        "other_costs": str(summary["other_costs"]),
        "notes": "",
    }
    for line in summary["lines"]:
        data[f"qty_{line['id']}"] = str(line["quantity"])
        data[f"price_{line['id']}"] = str(line["unit_price"])
    data.update(overrides)
    return data


class SeedAndTotalsTests(TestCase):
    def test_all_four_products_have_profiles(self):
        slugs = set(ProductCost.objects.values_list("product_slug", flat=True))
        self.assertEqual(slugs, set(services.PRODUCTOS))

    def test_guide_tables_total_100_materials_and_175_cost(self):
        for slug in ("wedding-dog", "tactical-dog", "christmas-dog"):
            s = services.product_cost_summary(slug)
            self.assertEqual(s["materials_total"], Decimal("100.00"), slug)
            self.assertEqual(s["labor_cost"], Decimal("60.00"), slug)
            self.assertEqual(s["other_costs"], Decimal("15.00"), slug)
            self.assertEqual(s["total_cost"], Decimal("175.00"), slug)
            self.assertEqual(len(s["lines"]), 10, slug)

    def test_guide_margins(self):
        expected = {"wedding-dog": "475.00", "tactical-dog": "125.00", "christmas-dog": "75.00"}
        for slug, margin in expected.items():
            self.assertEqual(services.product_cost_summary(slug)["margin"], Decimal(margin))

    def test_dog_sweater_estimate(self):
        s = services.product_cost_summary("dog-sweater")
        self.assertEqual(s["materials_total"], Decimal("40.00"))
        self.assertEqual(s["labor_cost"], Decimal("35.00"))
        self.assertEqual(s["other_costs"], Decimal("8.00"))
        self.assertEqual(s["total_cost"], Decimal("83.00"))
        self.assertEqual(s["sale_price"], Decimal("125.00"))
        self.assertEqual(s["margin"], Decimal("42.00"))
        self.assertFalse(s["margin_negative"])
        subtotals = {l["name"]: l["subtotal"] for l in s["lines"]}
        self.assertEqual(subtotals["Hilo premium mezcla merino"], Decimal("17.10"))
        self.assertEqual(subtotals["Hilo elástico para acabados"], Decimal("2.40"))
        self.assertEqual(subtotals["Hilo de confección reforzado"], Decimal("0.80"))

    def test_subtotal_is_consumption_times_price_and_total_is_derived(self):
        for slug in services.PRODUCTOS:
            s = services.product_cost_summary(slug)
            for l in s["lines"]:
                self.assertEqual(
                    l["subtotal"], (l["quantity"] * l["unit_price"]).quantize(Decimal("0.01"))
                )
            self.assertEqual(s["materials_total"], sum(l["subtotal"] for l in s["lines"]))

    def test_seed_is_not_validated_and_reserves_flagged(self):
        for slug in services.PRODUCTOS:
            s = services.product_cost_summary(slug)
            self.assertFalse(s["is_validated"], slug)
            self.assertTrue(s["has_reserve"], slug)
            self.assertTrue(any(l["is_reserve"] for l in s["lines"]))


class RecalculationTests(TestCase):
    def test_changing_consumption_and_price_recalculates(self):
        s = services.product_cost_summary("dog-sweater")
        merino = next(l for l in s["lines"] if l["name"].startswith("Hilo premium"))
        services.update_product_cost(
            "dog-sweater",
            post_data("dog-sweater", **{
                f"qty_{merino['id']}": "0.50",
                f"price_{merino['id']}": "40.00",
            }),
        )
        s = services.product_cost_summary("dog-sweater")
        self.assertEqual(s["materials_total"], Decimal("42.90"))  # 40.00 - 17.10 + 20.00 - ...
        self.assertEqual(s["total_cost"], Decimal("85.90"))
        self.assertEqual(s["margin"], Decimal("39.10"))

    def test_labor_and_other_are_editable(self):
        services.update_product_cost(
            "dog-sweater", post_data("dog-sweater", labor_cost="50", other_costs="10")
        )
        s = services.product_cost_summary("dog-sweater")
        self.assertEqual(s["total_cost"], Decimal("100.00"))
        self.assertEqual(s["margin"], Decimal("25.00"))

    def test_add_and_delete_lines(self):
        s = services.product_cost_summary("dog-sweater")
        victim = s["lines"][0]
        services.update_product_cost(
            "dog-sweater",
            post_data(
                "dog-sweater",
                new_name="Extra button set", new_unit="lote", new_qty="2", new_price="1.25",
                **{f"delete_{victim['id']}": "on"},
            ),
        )
        s2 = services.product_cost_summary("dog-sweater")
        names = [l["name"] for l in s2["lines"]]
        self.assertNotIn(victim["name"], names)
        self.assertIn("Extra button set", names)
        self.assertEqual(s2["materials_total"], Decimal("40.00") - victim["subtotal"] + Decimal("2.50"))

    def test_warning_when_cost_exceeds_price(self):
        services.update_product_cost(
            "dog-sweater", post_data("dog-sweater", labor_cost="200")
        )
        s = services.product_cost_summary("dog-sweater")
        self.assertTrue(s["margin_negative"])
        self.assertLess(s["margin"], 0)

    def test_validation_rejects_bad_values_and_changes_nothing(self):
        before = services.product_cost_summary("dog-sweater")
        line = before["lines"][0]
        for bad in ({"labor_cost": "-1"}, {"labor_cost": "abc"}, {"other_costs": ""},
                    {f"qty_{line['id']}": "-2"}, {f"price_{line['id']}": "x"},
                    {"new_name": "Only name", "new_qty": "", "new_price": ""}):
            with self.assertRaises(services.CostError):
                services.update_product_cost("dog-sweater", post_data("dog-sweater", **bad))
        after = services.product_cost_summary("dog-sweater")
        self.assertEqual(before["total_cost"], after["total_cost"])
        self.assertEqual(MaterialLine.objects.filter(product_cost__product_slug="dog-sweater").count(), 7)

    def test_validation_flags(self):
        s = services.product_cost_summary("dog-sweater")
        data = post_data("dog-sweater", is_validated="on")
        for l in s["lines"]:
            data[f"validated_{l['id']}"] = "on"
        services.update_product_cost("dog-sweater", data)
        self.assertTrue(services.product_cost_summary("dog-sweater")["is_validated"])


class OrderCostTests(TestCase):
    def test_order_snapshot_freezes_product_cost(self):
        order = make_order(slug="dog-sweater")
        frozen = order.snapshot["cost_estimate"]
        self.assertEqual(frozen["total_cost"], "83.00")
        self.assertEqual(frozen["status"], "estimate_not_verified")
        self.assertEqual(len(frozen["lines"]), 7)
        # Cambiar el presupuesto después no altera pedidos existentes.
        services.update_product_cost("dog-sweater", post_data("dog-sweater", labor_cost="90"))
        order.refresh_from_db()
        s = services.cost_summary(order)
        self.assertEqual(s["cost"], Decimal("83.00"))
        self.assertEqual(s["cost_source"], "product_estimate")
        self.assertEqual(s["margin"], Decimal("42.00"))

    def test_order_cost_uses_product_not_flat_175(self):
        order = make_order(slug="dog-sweater")
        self.assertEqual(services.cost_summary(order)["cost"], Decimal("83.00"))

    def test_actual_cost_still_has_priority(self):
        order = make_order(slug="dog-sweater")
        staff = User.objects.create_user("s", password="x", is_staff=True)
        services.update_costs(order, staff, actual_materials=Decimal("50"), actual_labor=Decimal("40"))
        order.refresh_from_db()
        s = services.cost_summary(order)
        self.assertEqual((s["cost_source"], s["cost"]), ("actual", Decimal("90.00")))


class PrivacyAndPermissionsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.urls = [reverse("panel_costs"), reverse("panel_product_cost", args=["dog-sweater"])]

    def test_anonymous_and_non_staff_blocked(self):
        for url in self.urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse("panel_login"), r.url)
        self.client.force_login(User.objects.create_user("u", password="x"))
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        r = self.client.post(self.urls[1], post_data("dog-sweater", labor_cost="1"))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(services.product_cost_summary("dog-sweater")["labor_cost"], Decimal("35.00"))

    def test_csrf_enforced(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.staff)
        r = c.post(self.urls[1], post_data("dog-sweater", labor_cost="1"))
        self.assertEqual(r.status_code, 403)

    def test_staff_pages_render_and_label_estimates(self):
        self.client.force_login(self.staff)
        page = self.client.get(self.urls[0])
        self.assertContains(page, "ESTIMATE — not verified")
        self.assertContains(page, "$83.00")
        detail = self.client.get(self.urls[1])
        self.assertContains(detail, "Hilo premium mezcla merino")
        self.assertContains(detail, "provisional reserve")
        self.assertContains(detail, "Total materials")
        self.assertEqual(
            self.client.get(reverse("panel_product_cost", args=["nope"])).status_code, 404
        )

    def test_edit_through_panel_and_error_display(self):
        self.client.force_login(self.staff)
        r = self.client.post(self.urls[1], post_data("dog-sweater", labor_cost="45"))
        self.assertRedirects(r, self.urls[1])
        self.assertEqual(services.product_cost_summary("dog-sweater")["labor_cost"], Decimal("45.00"))
        r = self.client.post(self.urls[1], post_data("dog-sweater", labor_cost="-3"))
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "Nothing was saved", status_code=400)

    def test_negative_margin_warning_in_panel(self):
        services.update_product_cost("dog-sweater", post_data("dog-sweater", labor_cost="200"))
        self.client.force_login(self.staff)
        r = self.client.get(self.urls[1])
        self.assertContains(r, "exceeds the sale price")
        self.assertContains(self.client.get(self.urls[0]), "cost exceeds price")

    def test_costs_never_in_public_pages(self):
        order = make_order(slug="dog-sweater")
        pages = [
            reverse("inicio"), reverse("productos"),
            reverse("detalle", args=["dog-sweater"]), reverse("smart_fit"),
            reverse("assistant"), reverse("assistant") + "?q=cost+of+materials",
            reverse("smart_quote", args=[order.quote.public_id]),
            reverse("checkout", args=[order.quote.public_id]),
            reverse("order_detail", args=[order.public_id]),
        ]
        forbidden = ["Hilo premium", "merino", "83.00", "Manufacturing", "ESTIMATE",
                     "Satén", "Cordura", "labor", "Labor", "cost_estimate", "42.00"]
        for url in pages:
            body = self.client.get(url, follow=True).content.decode()
            for word in forbidden:
                self.assertNotIn(word, body, f"{word!r} leaked in {url}")
