"""Comparador (AC13, AC14): bandeja, dedupe, tope, solo diferencias,
compartir con recálculo, categorías distintas sin ganador ficticio."""

from decimal import Decimal

from reino import services_compare as cmp
from reino.models import AttributeDefinition, AttributeValue, CategorySchema
from reino.tests import ReinoTestCase


class CompareTrayTests(ReinoTestCase):
    def setUp(self):
        self.v1 = self.product.variants.get(option_label="Talla M")
        self.v2 = self.product2.variants.get(option_label="Talla M")
        self.v_nube = self.product_b.variants.first()

    def test_add_dedupe_and_limit(self):
        key = "cmp-1"
        _, msg = cmp.add_item(key, str(self.v1.public_id))
        self.assertIn("comparación", msg)
        _, msg = cmp.add_item(key, str(self.v1.public_id))
        self.assertIn("ya está", msg)  # duplicado
        others = [v for v in self.product.variants.all() if v != self.v1]
        for v in list(others)[:2]:
            cmp.add_item(key, str(v.public_id))
        cmp.add_item(key, str(self.v2.public_id))  # cuarta
        _, msg = cmp.add_item(key, str(self.v_nube.public_id))  # quinta
        self.assertIn("4 piezas", msg)

    def test_build_recalculates_price_and_state(self):
        key = "cmp-2"
        cmp.add_item(key, str(self.v1.public_id))
        cmp.add_item(key, str(self.v2.public_id))
        data = cmp.build_comparison(session_key=key)
        self.assertEqual(data["state"], "ok")
        prices = {c["title"]: c["price_raw"] for c in data["columns"]}
        self.assertEqual(prices["Arnés Real"], Decimal("63.00"))
        self.assertEqual(prices["Traje Gala"], Decimal("650.00"))
        # Menor precio de producto: misma moneda, ambos disponibles.
        best = [c for c in data["columns"] if c.get("best_price")]
        self.assertEqual(len(best), 1)
        self.assertEqual(best[0]["title"], "Arnés Real")
        # Agotado se muestra con su estado.
        self.v2.stock = 0
        self.v2.save()
        data = cmp.build_comparison(session_key=key)
        states = {c["title"]: c["state"] for c in data["columns"]}
        self.assertEqual(states["Traje Gala"], "agotada")

    def test_shared_comparison_recalculates(self):
        key = "cmp-3"
        tray, _ = cmp.add_item(key, str(self.v1.public_id))
        cmp.add_item(key, str(self.v2.public_id))
        self.product.base_price = Decimal("70.00")
        self.product.save(update_fields=["base_price"])
        data = cmp.build_comparison(public_id=tray.public_id)
        prices = {c["title"]: c.get("price_raw") for c in data["columns"]}
        self.assertEqual(prices["Arnés Real"], Decimal("70.00"))  # recalculado

    def test_archived_variant_shows_state(self):
        key = "cmp-4"
        cmp.add_item(key, str(self.v1.public_id))
        cmp.add_item(key, str(self.v2.public_id))
        vid = str(self.v1.public_id)
        self.v1.delete()
        data = cmp.build_comparison(session_key=key)
        archived = [c for c in data["columns"] if c["variant_id"] == vid]
        self.assertEqual(archived[0]["state"], "archivada")

    def test_cross_category_no_fake_winner(self):
        """AC14: arnés vs cuaderno: campos comunes, SIN ganador ni atributos
        mezclados de categorías distintas."""
        key = "cmp-5"
        cmp.add_item(key, str(self.v1.public_id))
        cmp.add_item(key, str(self.v_nube.public_id))
        data = cmp.build_comparison(session_key=key)
        self.assertTrue(data["common_only"])
        self.assertEqual(data["rows"], [])
        self.assertFalse(any(c.get("best_price") for c in data["columns"]))

    def test_attribute_rows_normalized(self):
        """Atributos tipados con unidad canónica y procedencia (§15)."""
        schema = CategorySchema.objects.create(slug="moda-canina", name="Moda canina")
        peso = AttributeDefinition.objects.create(
            schema=schema, key="peso", label="Peso", value_type="measure", unit="g")
        AttributeValue.objects.create(
            variant=self.v1, definition=peso, value={"raw": "8", "unit": "oz"},
            normalized_number=Decimal("226.796"), source="ficha del proveedor")
        key = "cmp-6"
        cmp.add_item(key, str(self.v1.public_id))
        cmp.add_item(key, str(self.product2.variants.first().public_id))
        data = cmp.build_comparison(session_key=key)
        self.assertTrue(any(r["label"] == "Peso" for r in data["rows"]))


class CompareViewTests(ReinoTestCase):
    def test_tray_flow_over_http(self):
        v = self.product.variants.get(option_label="Talla M")
        v2 = self.product2.variants.first()
        self.client.post("/comparar/agregar/", {"variant_id": str(v.public_id)})
        self.client.post("/comparar/agregar/", {"variant_id": str(v2.public_id)})
        r = self.client.get("/comparar/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Arnés Real")
        self.assertContains(r, "Traje Gala")
        r = self.client.get("/comparar/?vista=diferencias")
        self.assertEqual(r.status_code, 200)
        # Compartir: la misma bandeja por ID público.
        tray = cmp.get_tray(self.client.session.session_key)
        r2 = self.client.get(f"/comparar/?c={tray.public_id}")
        self.assertContains(r2, "Arnés Real")
        # Quitar una pieza.
        self.client.post("/comparar/quitar/", {"variant_id": str(v2.public_id)})
        r3 = self.client.get("/comparar/")
        self.assertNotContains(r3, "Traje Gala")
