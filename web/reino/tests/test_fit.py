"""Smart Fit: A04 (cm/in equivalentes), A05 (sin datos = incertidumbre)."""

from decimal import Decimal

from reino import services_fit
from reino.tests import ReinoTestCase


class FitTests(ReinoTestCase):
    def test_a04_cm_y_pulgadas_equivalentes(self):
        """A04: 40 cm y 15.75 in (≈40 cm) producen el mismo resultado."""
        r_cm = services_fit.evaluate(self.product, chest_cm=Decimal("40"),
                                     neck_cm=Decimal("26"), back_cm=Decimal("32"))
        inches = services_fit.to_cm("15.75", "in")
        r_in = services_fit.evaluate(self.product, chest_cm=inches,
                                     neck_cm=services_fit.to_cm("10.25", "in"),
                                     back_cm=services_fit.to_cm("12.6", "in"))
        self.assertEqual(r_cm["state"], r_in["state"])
        self.assertEqual(r_cm["candidates"], r_in["candidates"])

    def test_a04_unidad_invalida_rechazada(self):
        with self.assertRaises(services_fit.InvalidMeasurement):
            services_fit.to_cm("abc", "cm")
        with self.assertRaises(services_fit.InvalidMeasurement):
            services_fit.to_cm("-5", "cm")

    def test_a05_falta_medida_es_incertidumbre(self):
        """A05: sin pecho o sin regla => sin_datos; nunca se inventa talla."""
        r = services_fit.evaluate(self.product, chest_cm=None, back_cm=Decimal("30"))
        self.assertEqual(r["state"], services_fit.UNKNOWN)
        self.assertIn("chest", r["missing"])

    def test_a05_producto_sin_regla_es_incertidumbre(self):
        r = services_fit.evaluate(self.product_b, chest_cm=Decimal("40"))
        self.assertEqual(r["state"], services_fit.UNKNOWN)
        self.assertIn("rule", r["missing"])

    def test_compatible_al_limite_incompatible(self):
        ok = services_fit.evaluate(self.product, chest_cm=Decimal("36.5"),
                                   neck_cm=Decimal("24"), back_cm=Decimal("28"))
        self.assertEqual(ok["state"], services_fit.COMPATIBLE)
        self.assertEqual(ok["candidates"], ["S"])
        borde = services_fit.evaluate(self.product, chest_cm=Decimal("33.5"),
                                      neck_cm=Decimal("24"), back_cm=Decimal("28"))
        self.assertEqual(borde["state"], services_fit.EDGE)
        fuera = services_fit.evaluate(self.product, chest_cm=Decimal("70"),
                                      neck_cm=Decimal("50"), back_cm=Decimal("60"))
        self.assertEqual(fuera["state"], services_fit.INCOMPATIBLE)
        self.assertEqual(fuera["candidates"], [])
