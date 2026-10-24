"""Descubrimiento y búsqueda por reglas (AC15): sin IA, tildes, filtros
visibles, demo separada, cero resultados honesto."""

from reino import services_search
from reino.tests import ReinoTestCase


class SearchRulesTests(ReinoTestCase):
    def test_accent_insensitive(self):
        results = services_search.search_catalog("arnes")  # sin tilde
        self.assertTrue(any(r["product"].pk == self.product.pk for r in results))

    def test_budget_phrase_parsed(self):
        parsed = services_search.parse_query("regalo por menos de $30")
        self.assertEqual(str(parsed["max_price"]), "30")
        results = services_search.search_catalog("regalo por menos de $30",
                                                 include_demo=True)
        self.assertTrue(all(r["product"].base_price <= 30 for r in results))

    def test_demo_separated_by_default(self):
        results = services_search.search_catalog("cuaderno")
        self.assertEqual(results, [])  # Nube es demo: separada del catálogo comercial
        results = services_search.search_catalog("cuaderno", include_demo=True)
        self.assertTrue(results)
        self.assertTrue(all(r["store"].is_demo for r in results))

    def test_cross_store_results_declare_store(self):
        results = services_search.search_catalog("real")
        for r in results:
            self.assertIsNotNone(r["store"])

    def test_incompatible_filters_zero_honest(self):
        results = services_search.search_catalog("arnes", max_price=1)
        self.assertEqual(results, [])  # cero honesto, no relaja filtros a escondidas


class ExploreViewTests(ReinoTestCase):
    def test_explore_ok(self):
        r = self.client.get("/explorar/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Encontrá cosas con personalidad")
        self.assertContains(r, "Wiener Kingdom")

    def test_search_view_without_ai(self):
        r = self.client.get("/buscar/?q=arnes")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Arnés Real")
        # La URL conserva el estado del filtro (compartible).
        self.assertContains(r, 'value="arnes"')

    def test_search_zero_results_state(self):
        r = self.client.get("/buscar/?q=zzz-inexistente")
        self.assertContains(r, "No encontré nada con esos filtros")

    def test_directory_filters(self):
        r = self.client.get("/tiendas/?categoria=papeleria")
        self.assertContains(r, "Estudio Nube")
        self.assertNotContains(r, "Wiener Kingdom")
        r = self.client.get("/tiendas/?q=wiener")
        self.assertContains(r, "Wiener Kingdom")
