"""Flujos HTTP: A07 (borrador LookLab), compra completa coherente (A29),
estados vacíos y navegación por pasos."""

from reino.models import Order, RecipientProfile
from reino.tests import ReinoTestCase


class FlowTests(ReinoTestCase):
    def test_a07_looklab_conserva_borrador_al_volver(self):
        """A07: atrás/adelante conserva la sesión sin memoria persistente."""
        s = self.client.session
        s.save()
        self.client.post(f"/s/{self.store_a.slug}/looklab/",
                         {"action": "perfil", "profile_id": "new", "alias": "Bruno"})
        self.client.post(f"/s/{self.store_a.slug}/looklab/?paso=medidas",
                         {"action": "medidas", "unit": "cm", "chest": "40", "back": "32"})
        r = self.client.get(f"/s/{self.store_a.slug}/looklab/?paso=medidas")
        self.assertContains(r, 'value="40"')  # el borrador conserva el pecho

    def test_looklab_sin_medidas_continua_con_talla_pendiente(self):
        """«No tengo las medidas» continúa; la revelación etiqueta talla por confirmar."""
        self.client.post(f"/s/{self.store_a.slug}/looklab/",
                         {"action": "perfil", "profile_id": "new", "alias": "Bruno"})
        self.client.post(f"/s/{self.store_a.slug}/looklab/?paso=medidas",
                         {"action": "medidas", "unit": "cm"})
        self.client.post(f"/s/{self.store_a.slug}/looklab/?paso=personalidad",
                         {"action": "personalidad", "style": "urban-king"})
        self.client.post(f"/s/{self.store_a.slug}/looklab/?paso=ocasion",
                         {"action": "ocasion", "occasion": "paseo"})
        r = self.client.get(f"/s/{self.store_a.slug}/looklab/?paso=revelacion")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Talla por confirmar")

    def test_compra_completa_http(self):
        """A29 HTTP: ficha → carrito → checkout → pedido con importes iguales."""
        variant = self.product.variants.get(option_label="Talla M")
        r = self.client.post(f"/s/{self.store_a.slug}/carrito/agregar/",
                             {"variant": str(variant.public_id), "quantity": 1})
        self.assertEqual(r.status_code, 302)
        self.client.post(f"/s/{self.store_a.slug}/checkout/", {
            "step": "review", "name": "Cliente", "email": "c@c.dev", "phone": "",
            "delivery_mode": "pickup", "payment_method": "manual",
            "idempotency_key": "http-1"})
        self.client.post(f"/s/{self.store_a.slug}/checkout/", {
            "step": "confirm", "name": "Cliente", "email": "c@c.dev", "phone": "",
            "delivery_mode": "pickup", "payment_method": "manual",
            "idempotency_key": "http-1"})
        order = Order.objects.get(idempotency_key="http-1")
        self.assertEqual(order.subtotal, variant.price)
        r = self.client.get(f"/s/{self.store_a.slug}/pedido/{order.public_id}/{order.access_token}/")
        self.assertContains(r, order.reference)
        self.assertContains(r, "pendiente de verificación")

    def test_estado_vacio_carrito(self):
        """EmptyState honesto: explica y propone acción, sin inventar productos."""
        r = self.client.get(f"/s/{self.store_a.slug}/carrito/")
        self.assertContains(r, "Tu próximo look empieza acá")

    def test_coleccion_filtro_imposible_devuelve_cero(self):
        """Un filtro incompatible devuelve cero resultados (aceptación S02)."""
        r = self.client.get(f"/s/{self.store_a.slug}/coleccion/?max=1")
        self.assertContains(r, "No encontramos coincidencias")

    def test_coleccion_informa_interpretacion(self):
        r = self.client.get(f"/s/{self.store_a.slug}/coleccion/?q=arnés&categoria=arnes")
        self.assertContains(r, "Buscando:")

    def test_segunda_tienda_sin_fit(self):
        """Estudio Nube funciona sin medidas caninas (categoría obliga)."""
        r = self.client.get(f"/s/{self.store_b.slug}/")
        self.assertEqual(r.status_code, 200)
        r = self.client.get(f"/s/{self.store_b.slug}/coleccion/")
        self.assertContains(r, "Cuaderno Nube")
        # Compra en tienda demo funciona sin fit
        variant = self.product_b.variants.get()
        self.client.post(f"/s/{self.store_b.slug}/carrito/agregar/",
                         {"variant": str(variant.public_id), "quantity": 1})
        r = self.client.get(f"/s/{self.store_b.slug}/carrito/")
        self.assertContains(r, "Cuaderno Nube")

    def test_perfil_ajeno_no_accesible(self):
        """Un perfil de otra sesión no se activa ni expone."""
        ajeno = self._profile(self.store_a, session="otra-sesion", alias="Rocky")
        r = self.client.post(f"/cuenta/perfiles/{ajeno.public_id}/activar/",
                             {"store": self.store_a.slug})
        self.assertNotEqual(self.client.session.get("reino_profile", {}).get(self.store_a.slug),
                            str(ajeno.public_id))
