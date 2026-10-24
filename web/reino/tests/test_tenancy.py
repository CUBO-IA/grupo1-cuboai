"""Aislamiento: A13 (tenants con nombres iguales), A26 (staff ajeno),
A28 (panel sin datos), y resolución fail-closed de tienda."""

from django.contrib.auth.models import User

from reino import services_memory
from reino.models import MerchantMember, Order
from reino.services_recommend import normalize_intent, recommend
from reino.tests import ReinoTestCase
from reino import services_commerce as commerce


class TenancyTests(ReinoTestCase):
    def test_a13_productos_mismo_nombre_no_se_filtran(self):
        """A13: dos tiendas con «arnes-real»: cada búsqueda ve solo lo suyo."""
        intent = normalize_intent()
        result_a = recommend(self.store_a, intent)
        result_b = recommend(self.store_b, intent)
        self.assertTrue(all(e["product"].store_id == self.store_a.pk for e in result_a["selection"]))
        self.assertTrue(all(e["product"].store_id == self.store_b.pk for e in result_b["selection"]))
        self.assertEqual({e["product"].short_title for e in result_b["selection"]},
                         {"Cuaderno Nube"})

    def test_a13_perfil_no_cruza_tienda(self):
        """Un perfil de WK no existe para Nube aunque la sesión sea la misma."""
        profile = self._profile(self.store_a, session="multi", alias="Bruno")
        self.assertIsNone(services_memory.get_profile(self.store_b, "multi", profile.public_id))

    def test_a06_dos_perros_nombres_parecidos(self):
        """A06: selección por ID; «Bruno» y «bruno» no mezclan medidas."""
        p1 = self._profile(self.store_a, session="s", alias="Bruno")
        p2 = self._profile(self.store_a, session="s", alias="bruno")
        services_memory.save_measurement(p1, chest_cm=36)
        self.assertIsNone(services_memory.latest_measurement(p2))
        self.assertNotEqual(p1.public_id, p2.public_id)

    def test_tienda_inexistente_404(self):
        r = self.client.get("/s/no-existe/")
        self.assertEqual(r.status_code, 404)

    def test_a26_staff_ajeno_no_entra_al_panel(self):
        """A26: staff de Nube no abre pedidos/configuración de Wiener Kingdom."""
        user = User.objects.create_user("nube_staff", password="x")
        user.is_staff = True
        user.save()
        MerchantMember.objects.create(user=user, merchant=self.merchant_b)
        self.client.force_login(user)
        r = self.client.get(f"/negocio/{self.store_a.slug}/pedidos/")
        self.assertEqual(r.status_code, 403)
        r = self.client.get(f"/negocio/{self.store_b.slug}/pedidos/")
        self.assertEqual(r.status_code, 200)

    def test_a28_panel_sin_ventas_no_inventa_porcentajes(self):
        """A28: sin pedidos pagados, «Sin datos suficientes», nunca 0 %."""
        user = User.objects.create_user("wk_staff", password="x")
        user.is_staff = True
        user.save()
        MerchantMember.objects.create(user=user, merchant=self.merchant_a)
        self.client.force_login(user)
        r = self.client.get(f"/negocio/{self.store_a.slug}/")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["kpis"])
        self.assertContains(r, "Sin datos suficientes")

    def test_carritos_separados_por_tienda(self):
        """Cambiar de tienda conserva carritos separados."""
        v_a = self.product.variants.get(option_label="Talla M")
        v_b = self.product_b.variants.get()
        cart_a = commerce.get_open_cart(self.store_a, "multi", create=True)
        cart_b = commerce.get_open_cart(self.store_b, "multi", create=True)
        commerce.add_item(cart_a, v_a, 1)
        commerce.add_item(cart_b, v_b, 2)
        self.assertEqual(cart_a.items.count(), 1)
        self.assertEqual(cart_b.items.get().quantity, 2)
        self.assertNotEqual(cart_a.store_id, cart_b.store_id)

    def test_pedidos_no_cruzan_tienda(self):
        v_b = self.product_b.variants.get()
        cart = commerce.get_open_cart(self.store_b, "comprador", create=True)
        commerce.add_item(cart, v_b, 1)
        session = commerce.prepare_checkout(cart, "manual", idempotency_key="iso-1")
        order = commerce.confirm_checkout(session, {"name": "T", "email": "t@t.dev"}, "iso-1")
        self.assertEqual(order.store, self.store_b)
        self.assertEqual(Order.objects.filter(store=self.store_a).count(), 0)
