"""Motor de recomendación: A03 (agotado), A08 (presupuesto estricto),
exclusiones declaradas, bundle sin duplicar función."""

from reino import services_memory
from reino.services_recommend import compose_bundle, normalize_intent, recommend
from reino.tests import ReinoTestCase


class RecommendTests(ReinoTestCase):
    def test_a03_variante_agotada_no_se_recomienda_como_disponible(self):
        """A03: producto con TODO agotado queda fuera con motivo declarado."""
        for v in self.product.variants.all():
            v.stock = 0
            v.save()
        intent = normalize_intent(occasion="paseo")
        result = recommend(self.store_a, intent)
        titles = [e["product"].short_title for e in result["selection"]]
        self.assertNotIn("Arnés Real", titles)
        self.assertTrue(any(e["reason"] == "OUT_OF_STOCK" for e in result["excluded"]))

    def test_a08_presupuesto_estricto_no_se_relaja(self):
        """A08: presupuesto por pieza excluye lo que lo supera; no se relaja."""
        intent = normalize_intent(occasion="celebracion", budget="100", budget_scope="products")
        result = recommend(self.store_a, intent)
        for e in result["selection"]:
            cheapest = min(v.price for v in e["product"].variants.filter(stock__gt=0))
            self.assertLessEqual(float(cheapest), 100.0)
        self.assertTrue(any(e["reason"] == "OVER_BUDGET" for e in result["excluded"]))

    def test_ocasion_prioriza_coincidencia(self):
        intent = normalize_intent(occasion="celebracion")
        result = recommend(self.store_a, intent)
        self.assertEqual(result["selection"][0]["product"].short_title, "Traje Gala")
        self.assertIn("MATCH_OCCASION", result["selection"][0]["reasons"])

    def test_fit_confirmado_suma_razon(self):
        profile = self._profile(self.store_a)
        services_memory.save_measurement(profile, chest_cm=36, neck_cm=24, back_cm=28)
        measurement = services_memory.latest_measurement(profile)
        intent = normalize_intent(occasion="paseo", profile=profile)
        result = recommend(self.store_a, intent, measurement=measurement)
        arnes = next(e for e in result["selection"] if e["product"].short_title == "Arnés Real")
        self.assertIn("FIT_RANGE_CONFIRMED", arnes["reasons"])

    def test_bundle_sin_duplicar_funcion_y_presupuesto_acumulado(self):
        """Paso F: complementos de otra categoría; presupuesto acumulado estricto."""
        bundle, total = compose_bundle(self.store_a, self.product2)
        categorias = [b["product"].category for b in bundle]
        self.assertEqual(len(categorias), len(set(categorias)))
        bundle_cap, total_cap = compose_bundle(self.store_a, self.product2, budget="660")
        self.assertLessEqual(float(total_cap), 660.0)

    def test_evento_de_recomendacion_auditado(self):
        from reino.models import RecommendationEvent
        recommend(self.store_a, normalize_intent(occasion="paseo"), kind="looklab")
        event = RecommendationEvent.objects.latest("created_at")
        self.assertEqual(event.engine_version, "v1")
        self.assertEqual(event.store, self.store_a)
        self.assertTrue(event.candidates)
