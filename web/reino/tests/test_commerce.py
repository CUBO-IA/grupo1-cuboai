"""Comercio: A17 (última unidad), A18 (doble clic), A25 (pedido ajeno),
A29 (coherencia de importes), vencimiento de checkout y Bitcoin 15 %."""

import threading
from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone

from reino import services_commerce as commerce
from reino.models import Cart, Order, StockReservation, Variant
from reino.tests import ReinoTestCase

CUSTOMER = {"name": "Cliente Prueba", "email": "c@test.dev", "phone": "",
            "address": "", "city": ""}


class CommerceTests(ReinoTestCase):
    def _cart_with(self, store, variant, qty=1):
        cart = commerce.get_open_cart(store, f"sesion-{variant.sku}", create=True)
        commerce.add_item(cart, variant, qty)
        return cart

    def test_a18_doble_clic_un_pedido(self):
        """A18: misma clave idempotente => mismo pedido, sin doble descuento."""
        variant = self.product.variants.get(option_label="Talla M")
        stock0 = variant.stock
        cart = self._cart_with(self.store_a, variant)
        session = commerce.prepare_checkout(cart, "manual", idempotency_key="k-1")
        o1 = commerce.confirm_checkout(session, CUSTOMER, "k-1")
        o2 = commerce.confirm_checkout(session, CUSTOMER, "k-1")
        self.assertEqual(o1.pk, o2.pk)
        self.assertEqual(Order.objects.filter(idempotency_key="k-1").count(), 1)
        variant.refresh_from_db()
        self.assertEqual(variant.stock, stock0 - 1)

    def test_a17_dos_checkouts_ultima_unidad(self):
        """A17: dos compras de la última unidad no obtienen ambas reserva."""
        variant = self.product.variants.get(option_label="Talla S")
        variant.stock = 1
        variant.save()
        c1 = commerce.get_open_cart(self.store_a, "s-1", create=True)
        c2 = commerce.get_open_cart(self.store_a, "s-2", create=True)
        commerce.add_item(c1, variant, 1)
        commerce.add_item(c2, variant, 1)
        commerce.prepare_checkout(c1, "manual", idempotency_key="k-a")
        with self.assertRaises(commerce.StockConflict):
            commerce.prepare_checkout(c2, "manual", idempotency_key="k-b")

    def test_checkout_vencido_no_confirma(self):
        """La expiración de la reserva es una condición operativa real."""
        variant = self.product.variants.get(option_label="Talla M")
        cart = self._cart_with(self.store_a, variant)
        session = commerce.prepare_checkout(cart, "manual", idempotency_key="k-old")
        session.expires_at = timezone.now() - timedelta(minutes=1)
        session.save()
        with self.assertRaises(commerce.CartError):
            commerce.confirm_checkout(session, CUSTOMER, "k-old")

    def test_carrito_cambiado_invalida_resumen(self):
        """Cambio de carrito tras preparar => pedir revisar el nuevo resumen."""
        variant = self.product.variants.get(option_label="Talla M")
        cart = self._cart_with(self.store_a, variant)
        session = commerce.prepare_checkout(cart, "manual", idempotency_key="k-x")
        commerce.add_item(cart, self.product2.variants.first(), 1)  # bump version
        with self.assertRaises(commerce.CartError):
            commerce.confirm_checkout(session, CUSTOMER, "k-x")

    def test_bitcoin_descuento_15_porciento_pendiente(self):
        """A22 (núcleo): 15 % sobre mercancía ELEGIBLE, pendiente de verificación.

        Actualizado por R05: el descuento aplica solo a líneas con elegibilidad
        migrada de la regla histórica del negocio; una pieza no elegible no
        recibe descuento aunque pague con Bitcoin.
        """
        self.product.bitcoin_discount_eligible = True  # elegibilidad migrada
        self.product.save()
        variant = self.product.variants.get(option_label="Talla M")  # $63
        cart = self._cart_with(self.store_a, variant, 2)  # $126
        session = commerce.prepare_checkout(cart, "bitcoin", idempotency_key="k-btc")
        order = commerce.confirm_checkout(session, CUSTOMER, "k-btc")
        self.assertEqual(str(order.discount_amount), "18.90")
        self.assertEqual(str(order.total), "107.10")
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        # Cesta mixta: la línea NO elegible no se descuenta.
        cart2 = self._cart_with(self.store_a, self.product2.variants.first(), 1)  # $650
        commerce.add_item(cart2, variant, 1)  # + $63 elegible
        summary = commerce.cart_summary(cart2, "bitcoin")
        self.assertEqual(str(summary["discount"]), "9.45")  # 15 % solo de $63

    def test_a29_coherencia_de_importes(self):
        """A29: mismos importes en carrito, pedido y líneas."""
        variant = self.product.variants.get(option_label="Talla M")
        cart = self._cart_with(self.store_a, variant, 2)
        summary = commerce.cart_summary(cart)
        session = commerce.prepare_checkout(cart, "manual", idempotency_key="k-29")
        order = commerce.confirm_checkout(session, CUSTOMER, "k-29")
        self.assertEqual(order.subtotal, summary["subtotal"])
        item = order.items.get()
        self.assertEqual(item.unit_price, variant.price)
        self.assertEqual(item.subtotal, variant.price * 2)
        self.assertEqual(order.total, order.subtotal)  # pickup = envío $0

    def test_a25_pedido_ajeno_no_visible(self):
        """A25: otra sesión sin token no ve el pedido; con token sí."""
        variant = self.product.variants.get(option_label="Talla M")
        cart = self._cart_with(self.store_a, variant)
        session = commerce.prepare_checkout(cart, "manual", idempotency_key="k-25")
        order = commerce.confirm_checkout(session, CUSTOMER, "k-25")
        r = self.client.get(f"/s/{self.store_a.slug}/pedido/{order.public_id}/")
        self.assertEqual(r.status_code, 404)
        r = self.client.get(f"/s/{self.store_a.slug}/pedido/{order.public_id}/{order.access_token}/")
        self.assertEqual(r.status_code, 200)

    def test_envio_local_requiere_zona(self):
        """A27: sin tarifa configurada no se aplica envío gratis ficticio."""
        variant = self.product.variants.get(option_label="Talla M")
        cart = self._cart_with(self.store_a, variant)
        with self.assertRaises(commerce.CartError):
            commerce.prepare_checkout(cart, "manual", delivery_mode="local", zone=None,
                                      idempotency_key="k-27")

    def test_transiciones_de_panel_validadas(self):
        variant = self.product.variants.get(option_label="Talla M")
        cart = self._cart_with(self.store_a, variant)
        session = commerce.prepare_checkout(cart, "manual", idempotency_key="k-t")
        order = commerce.confirm_checkout(session, CUSTOMER, "k-t")
        with self.assertRaises(commerce.CartError):
            commerce.apply_transition(order, "payment_status", "refunded")  # inválida
        commerce.apply_transition(order, "payment_status", "paid", note="verificado")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")


class ConcurrencyTests(TransactionTestCase):
    """A17 en concurrencia real: dos hilos, última unidad, una sola reserva."""

    def test_ultima_unidad_en_paralelo(self):
        from reino.tests import ReinoTestCase
        ReinoTestCase.setUpTestData()
        store = ReinoTestCase.store_a
        variant = ReinoTestCase.product.variants.get(option_label="Talla M")
        variant.stock = 1
        variant.save()
        results = []

        def buy(n):
            try:
                cart = commerce.get_open_cart(store, f"hilo-{n}", create=True)
                commerce.add_item(cart, Variant.objects.get(pk=variant.pk), 1)
                commerce.prepare_checkout(cart, "manual", idempotency_key=f"h-{n}")
                results.append("ok")
            except commerce.StockConflict:
                results.append("conflict")
            except Exception as exc:  # SQLite puede serializar escrituras
                results.append(type(exc).__name__)

        threads = [threading.Thread(target=buy, args=(i,)) for i in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertIn("ok", results)
        self.assertEqual(results.count("ok"), 1)
