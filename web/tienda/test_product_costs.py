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
    NEW = {
        # slug: (precio, materiales según Presupuestos_Materiales_5_Productos)
        "alnut-whip-harness": ("250.00", "50.00"),
        "beige-anti-rub-harness": ("63.00", "22.00"),
        "tutti-frutti-harness": ("63.00", "25.00"),
        "cable-knit-jumper": ("150.00", "35.00"),
        "bamboo-drying-robe": ("88.00", "26.00"),
    }

    def test_all_active_products_have_profiles(self):
        slugs = set(ProductCost.objects.values_list("product_slug", flat=True))
        self.assertTrue(set(services.PRODUCTOS) <= slugs)
        self.assertEqual(len(services.PRODUCTOS), 8)

    def test_guide_tables_total_100_materials_and_175_cost(self):
        for slug in ("wedding-dog", "tactical-dog", "christmas-dog"):
            s = services.product_cost_summary(slug)
            self.assertEqual(s["materials_total"], Decimal("100.00"), slug)
            self.assertEqual(s["labor_cost"], Decimal("60.00"), slug)
            self.assertEqual(s["other_costs"], Decimal("15.00"), slug)
            self.assertEqual(s["total_cost"], Decimal("175.00"), slug)
            self.assertEqual(len(s["lines"]), 10, slug)
            self.assertFalse(s["incomplete"], slug)

    def test_guide_margins(self):
        expected = {"wedding-dog": "475.00", "tactical-dog": "125.00", "christmas-dog": "75.00"}
        for slug, margin in expected.items():
            self.assertEqual(services.product_cost_summary(slug)["margin"], Decimal(margin))

    def test_new_products_materials_from_budget_document(self):
        for slug, (price, materials) in self.NEW.items():
            s = services.product_cost_summary(slug)
            self.assertEqual(s["sale_price"], Decimal(price), slug)
            self.assertEqual(s["materials_total"], Decimal(materials), slug)
            self.assertTrue(s["has_reserve"], slug)
            self.assertFalse(s["is_validated"], slug)

    def test_new_products_flag_missing_labor_and_other(self):
        for slug in self.NEW:
            s = services.product_cost_summary(slug)
            self.assertEqual((s["labor_cost"], s["other_costs"]), (Decimal("0.00"), Decimal("0.00")))
            self.assertTrue(s["incomplete"], slug)
            self.assertEqual(s["total_cost"], s["materials_total"])

    def test_retired_dog_sweater_is_not_active(self):
        retired = "dog-sweater"
        self.assertNotIn(retired, services.PRODUCTOS)
        self.assertNotIn(retired, [p["slug"] for p in services.all_product_costs()])
        with self.assertRaises(services.UnknownProduct):
            services.get_base_price(retired)

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


class RecalculationTests(TestCase):
    SLUG = "cable-knit-jumper"  # materiales 35.00, mano de obra y otros en 0, precio 150

    def test_changing_consumption_and_price_recalculates(self):
        s = services.product_cost_summary(self.SLUG)
        merino = next(l for l in s["lines"] if l["name"].startswith("Hilo premium"))
        services.update_product_cost(
            self.SLUG,
            post_data(self.SLUG, **{
                f"qty_{merino['id']}": "0.50",
                f"price_{merino['id']}": "40.00",
            }),
        )
        s = services.product_cost_summary(self.SLUG)
        self.assertEqual(s["materials_total"], Decimal("40.30"))  # 35.00 - 14.70 + 0.50 * 40.00
        self.assertEqual(s["total_cost"], Decimal("40.30"))
        self.assertEqual(s["margin"], Decimal("109.70"))

    def test_labor_and_other_are_editable(self):
        services.update_product_cost(
            self.SLUG, post_data(self.SLUG, labor_cost="50", other_costs="10")
        )
        s = services.product_cost_summary(self.SLUG)
        self.assertEqual(s["total_cost"], Decimal("95.00"))
        self.assertEqual(s["margin"], Decimal("55.00"))
        self.assertFalse(s["incomplete"])

    def test_add_and_delete_lines(self):
        s = services.product_cost_summary(self.SLUG)
        victim = s["lines"][0]
        services.update_product_cost(
            self.SLUG,
            post_data(
                self.SLUG,
                new_name="Extra button set", new_unit="lote", new_qty="2", new_price="1.25",
                **{f"delete_{victim['id']}": "on"},
            ),
        )
        s2 = services.product_cost_summary(self.SLUG)
        names = [l["name"] for l in s2["lines"]]
        self.assertNotIn(victim["name"], names)
        self.assertIn("Extra button set", names)
        self.assertEqual(s2["materials_total"], Decimal("35.00") - victim["subtotal"] + Decimal("2.50"))

    def test_warning_when_cost_exceeds_price(self):
        services.update_product_cost(self.SLUG, post_data(self.SLUG, labor_cost="200"))
        s = services.product_cost_summary(self.SLUG)
        self.assertTrue(s["margin_negative"])
        self.assertLess(s["margin"], 0)

    def test_validation_rejects_bad_values_and_changes_nothing(self):
        before = services.product_cost_summary(self.SLUG)
        line = before["lines"][0]
        for bad in ({"labor_cost": "-1"}, {"labor_cost": "abc"}, {"other_costs": ""},
                    {f"qty_{line['id']}": "-2"}, {f"price_{line['id']}": "x"},
                    {"new_name": "Only name", "new_qty": "", "new_price": ""}):
            with self.assertRaises(services.CostError):
                services.update_product_cost(self.SLUG, post_data(self.SLUG, **bad))
        after = services.product_cost_summary(self.SLUG)
        self.assertEqual(before["total_cost"], after["total_cost"])
        self.assertEqual(MaterialLine.objects.filter(product_cost__product_slug=self.SLUG).count(), 8)

    def test_validation_flags(self):
        s = services.product_cost_summary(self.SLUG)
        data = post_data(self.SLUG, is_validated="on")
        for l in s["lines"]:
            data[f"validated_{l['id']}"] = "on"
        services.update_product_cost(self.SLUG, data)
        self.assertTrue(services.product_cost_summary(self.SLUG)["is_validated"])


class OrderCostTests(TestCase):
    def test_order_snapshot_freezes_product_cost(self):
        order = make_order(slug="cable-knit-jumper")
        frozen = order.snapshot["cost_estimate"]
        self.assertEqual(frozen["total_cost"], "35.00")
        self.assertEqual(frozen["status"], "estimate_not_verified")
        self.assertEqual(len(frozen["lines"]), 8)
        # Cambiar el presupuesto después no altera pedidos existentes.
        services.update_product_cost(
            "cable-knit-jumper", post_data("cable-knit-jumper", labor_cost="90")
        )
        order.refresh_from_db()
        s = services.cost_summary(order)
        self.assertEqual(s["cost"], Decimal("35.00"))
        self.assertEqual(s["cost_source"], "product_estimate")
        self.assertEqual(s["margin"], Decimal("115.00"))

    def test_order_cost_uses_product_not_flat_175(self):
        order = make_order(slug="cable-knit-jumper")
        self.assertEqual(services.cost_summary(order)["cost"], Decimal("35.00"))

    def test_actual_cost_still_has_priority(self):
        order = make_order(slug="cable-knit-jumper")
        staff = User.objects.create_user("s", password="x", is_staff=True)
        services.update_costs(order, staff, actual_materials=Decimal("50"), actual_labor=Decimal("40"))
        order.refresh_from_db()
        s = services.cost_summary(order)
        self.assertEqual((s["cost_source"], s["cost"]), ("actual", Decimal("90.00")))


class PrivacyAndPermissionsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.urls = [reverse("panel_costs"), reverse("panel_product_cost", args=["cable-knit-jumper"])]

    def test_anonymous_and_non_staff_blocked(self):
        for url in self.urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse("panel_login"), r.url)
        self.client.force_login(User.objects.create_user("u", password="x"))
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        r = self.client.post(self.urls[1], post_data("cable-knit-jumper", labor_cost="1"))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(services.product_cost_summary("cable-knit-jumper")["labor_cost"], Decimal("0.00"))

    def test_csrf_enforced(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.staff)
        r = c.post(self.urls[1], post_data("cable-knit-jumper", labor_cost="1"))
        self.assertEqual(r.status_code, 403)

    def test_staff_pages_render_and_label_estimates(self):
        self.client.force_login(self.staff)
        page = self.client.get(self.urls[0])
        self.assertContains(page, "ESTIMATE — not verified")
        self.assertContains(page, "$35.00")
        detail = self.client.get(self.urls[1])
        self.assertContains(detail, "Hilo premium de lana merino")
        self.assertContains(detail, "provisional reserve")
        self.assertContains(detail, "Total materials")
        self.assertEqual(
            self.client.get(reverse("panel_product_cost", args=["nope"])).status_code, 404
        )

    def test_edit_through_panel_and_error_display(self):
        self.client.force_login(self.staff)
        r = self.client.post(self.urls[1], post_data("cable-knit-jumper", labor_cost="45"))
        self.assertRedirects(r, self.urls[1])
        self.assertEqual(services.product_cost_summary("cable-knit-jumper")["labor_cost"], Decimal("45.00"))
        r = self.client.post(self.urls[1], post_data("cable-knit-jumper", labor_cost="-3"))
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "Nothing was saved", status_code=400)

    def test_negative_margin_warning_in_panel(self):
        services.update_product_cost("cable-knit-jumper", post_data("cable-knit-jumper", labor_cost="200"))
        self.client.force_login(self.staff)
        r = self.client.get(self.urls[1])
        self.assertContains(r, "exceeds the sale price")
        self.assertContains(self.client.get(self.urls[0]), "cost exceeds price")

    def test_costs_never_in_public_pages(self):
        order = make_order(slug="cable-knit-jumper")
        pages = [
            reverse("inicio"), reverse("productos"),
            reverse("detalle", args=["cable-knit-jumper"]), reverse("smart_fit"),
            reverse("assistant"), reverse("assistant") + "?q=cost+of+materials",
            reverse("smart_quote", args=[order.quote.public_id]),
            reverse("checkout", args=[order.quote.public_id]),
            reverse("order_detail", args=[order.public_id]),
        ]
        # Los nombres de materiales sí son públicos; consumos, costos y márgenes no.
        forbidden = ["Manufacturing", "ESTIMATE", "labor", "Labor", "cost_estimate",
                     "35.00", "115.00", "14.70", "Consumption", "Total materials",
                     "margin", "Margin"]
        for url in pages:
            body = self.client.get(url, follow=True).content.decode()
            for word in forbidden:
                self.assertNotIn(word, body, f"{word!r} leaked in {url}")
