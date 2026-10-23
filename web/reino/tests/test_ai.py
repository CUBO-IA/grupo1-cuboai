"""Royal Stylist: A10 (consulta natural con herramientas), A11 (ID inventado),
A14 (consentimiento), A15 (IA caída = honestidad), A16 (ambigüedad)."""

import json
from unittest import mock

from django.test import override_settings

from reino import services_memory
from reino.ai import adapter, orchestrator
from reino.ai.tools import ToolContext, run_tool
from reino.models import AIConversation, Consent
from reino.tests import ReinoTestCase

AI_SETTINGS = {
    "PROVIDER": "openai", "API_KEY": "test-key", "BASE_URL": "https://api.test/v1",
    "MODEL": "test-model", "TIMEOUT_SECONDS": 5, "MAX_TOOL_ROUNDS": 4,
}


def _fake_chat_factory(product_ids):
    """Proveedor falso: 1ª llamada pide herramienta; 2ª redacta respuesta."""
    calls = {"n": 0}

    def fake_chat(messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1", "type": "function",
                    "function": {"name": "search_products",
                                 "arguments": json.dumps({"query": "arnés"})},
                }],
                "content": None,
            }
        return {"role": "assistant", "content": "Encontré estas opciones reales para Bruno.",
                "tool_calls": []}

    return fake_chat


@override_settings(REINO_AI=AI_SETTINGS)
class StylistAITests(ReinoTestCase):
    def _conv(self):
        return AIConversation.objects.create(store=self.store_a, session_key="s-ai", mode="ai")

    def _ctx(self):
        profile = self._profile(self.store_a, session="s-ai")
        return ToolContext(self.store_a, "s-ai", profile)

    def test_a10_consulta_natural_usa_herramientas_y_catalogo(self):
        """A10: el turno consulta herramientas y las tarjetas son IDs reales."""
        with mock.patch.object(adapter, "chat", _fake_chat_factory(None)):
            reply = orchestrator.respond(self._conv(), "algo elegante para Bruno", self._ctx())
        self.assertEqual(reply["mode"], "ai")
        self.assertTrue(reply["cards"])
        real_ids = {str(p.public_id) for p in self.store_a.products.all()}
        for card in reply["cards"]:
            self.assertIn(card["product_id"], real_ids)

    def test_a11_id_inventado_no_se_hidrata(self):
        """A11: un product_id inventado por el modelo no produce tarjeta."""
        result = run_tool("get_product_details",
                          {"product_ids": ["00000000-0000-0000-0000-000000000000"]},
                          self._ctx())
        self.assertEqual(result["products"], [])

    def test_herramienta_no_listada_rechazada(self):
        """No hay SQL libre ni acciones fuera de la política de herramientas."""
        self.assertEqual(run_tool("execute_sql", {"q": "select 1"}, self._ctx()),
                         {"error": "tool_not_allowed"})
        self.assertEqual(run_tool("refund_payment", {}, self._ctx()),
                         {"error": "tool_not_allowed"})

    def test_pedido_ajeno_no_visible_por_herramienta(self):
        """get_order_status solo ve pedidos de la sesión propietaria."""
        result = run_tool("get_order_status", {"reference": "WK-999999"}, self._ctx())
        self.assertEqual(result["error"], "not_found")

    def test_a15_ia_caida_modo_reglas_etiquetado(self):
        """A15: proveedor inalcanzable => modo rules, honesto, tienda usable.

        Actualizado por la auditoría R12/UI: el mensaje al comprador no expone
        detalles de infraestructura; sigue etiquetando el modo honestamente.
        """
        with mock.patch.object(adapter, "chat",
                               side_effect=adapter.ProviderUnavailable("down")):
            reply = orchestrator.respond(self._conv(), "algo para paseo", self._ctx())
        self.assertEqual(reply["mode"], "rules")
        self.assertIn("no está disponible", reply["mode_note"])
        self.assertNotIn("API", reply["mode_note"])  # nada de infraestructura
        self.assertTrue(reply["cards"])  # la selección por reglas sigue sirviendo

    def test_a16_agregar_ambiguo_no_adivina(self):
        """A16: variante inexistente en add_item_to_cart => rechazo, no adivinanza.

        Actualizado por R11: primero se exige autorización del comprador; con
        ella, la variante inexistente sigue sin «adivinarse».
        """
        result = run_tool("add_item_to_cart",
                          {"variant_id": "00000000-0000-0000-0000-000000000000"},
                          self._ctx())
        self.assertEqual(result["error"], "action_authorization_required")
        result = run_tool("add_item_to_cart",
                          {"variant_id": "00000000-0000-0000-0000-000000000000",
                           "action_id": "aprobada-por-el-comprador"},
                          self._ctx())
        self.assertEqual(result["error"], "unknown_variant")

    def test_a16_agregar_explicito_ejecuta_una_accion(self):
        """R11: la acción explícita AUTORIZADA ejecuta exactamente una vez."""
        variant = self.product.variants.get(option_label="Talla M")
        result = run_tool("add_item_to_cart",
                          {"variant_id": str(variant.public_id), "quantity": 1,
                           "action_id": "accion-aprobada-a16"},
                          self._ctx())
        self.assertTrue(result["ok"])
        self.assertEqual(result["cart_units"], 1)
        # Reintentar la MISMA acción aprobada no duplica (idempotencia).
        again = run_tool("add_item_to_cart",
                         {"variant_id": str(variant.public_id), "quantity": 1,
                          "action_id": "accion-aprobada-a16"},
                         self._ctx())
        self.assertEqual(again["cart_units"], 1)


class MemoryConsentTests(ReinoTestCase):
    def test_a14_revocar_impide_reutilizar(self):
        """A14: preferencia guardada y borrada no se reutiliza ni deja derivados."""
        profile = self._profile(self.store_a, session="s14")
        consent = services_memory.grant_consent(
            self.store_a, "s14", Consent.Purpose.PREFERENCES, profile)
        services_memory.save_preference(profile, consent, "color", "azul")
        self.assertEqual(
            services_memory.authorized_preferences(profile, self.store_a, "s14"),
            {"color": "azul"})
        services_memory.revoke_consent(self.store_a, "s14",
                                       Consent.Purpose.PREFERENCES, profile)
        self.assertEqual(
            services_memory.authorized_preferences(profile, self.store_a, "s14"), {})

    def test_borrar_memoria_elimina_derivados(self):
        profile = self._profile(self.store_a, session="s-del")
        consent = services_memory.grant_consent(
            self.store_a, "s-del", Consent.Purpose.PREFERENCES, profile)
        services_memory.save_preference(profile, consent, "ocasion", "paseo")
        services_memory.delete_profile_memory(self.store_a, "s-del", profile)
        self.assertEqual(profile.preferences.count(), 0)
        self.assertEqual(profile.memory_summaries.count(), 0)
        self.assertFalse(
            services_memory.has_consent(self.store_a, "s-del",
                                        Consent.Purpose.PREFERENCES, profile))

    def test_memoria_desactivada_no_impide_comprar(self):
        """Comprar nunca exige consentimiento de memoria."""
        variant = self.product.variants.get(option_label="Talla M")
        cart = commerce_cart = __import__("reino.services_commerce", fromlist=["x"])
        cart = commerce_cart.get_open_cart(self.store_a, "sin-consent", create=True)
        commerce_cart.add_item(cart, variant, 1)
        session = commerce_cart.prepare_checkout(cart, "manual", idempotency_key="nc-1")
        order = commerce_cart.confirm_checkout(session, {"name": "N", "email": "n@n.dev"}, "nc-1")
        self.assertEqual(order.status, "placed")
