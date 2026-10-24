"""G4 · Envíos (A51–A56 a nivel local: flujo manual completo + contrato de
adaptador; la verificación con cuenta de proveedor queda como bloqueo)."""

from reino import services_commerce as c
from reino import services_shipping as ship
from reino.models import Shipment
from reino.tests import ReinoTestCase


class ShippingBase(ReinoTestCase):
    def _order(self, session="sh-1", qty=2):
        v = self.product.variants.get(option_label="Talla M")
        v.stock = max(v.stock, qty)
        v.save()
        cart = c.get_open_cart(self.store_a, session, create=True)
        c.add_item(cart, v, qty)
        ch = c.prepare_checkout(cart, "manual", idempotency_key=session)
        return c.confirm_checkout(ch, {"name": "S", "email": "s@e.invalid"},
                                  ch.idempotency_key)


class ShipmentFlowTests(ShippingBase):
    def test_creacion_idempotente_mismo_contenido(self):
        order = self._order()
        s1 = ship.create_shipment(order)
        s2 = ship.create_shipment(order)
        self.assertEqual(s1.pk, s2.pk, "doble clic no duplica el envío")
        self.assertEqual(Shipment.objects.count(), 1)

    def test_despacho_parcial_sin_exceder_comprado(self):
        order = self._order(qty=2)
        item = order.items.get()
        s1 = ship.create_shipment(order, lines=[{"order_item_id": item.pk, "quantity": 1}])
        self.assertEqual(ship.shippable_lines(order)[0]["pending"], 1)
        again = ship.create_shipment(order, lines=[{"order_item_id": item.pk, "quantity": 1}])
        self.assertEqual(again.pk, s1.pk, "mismo despacho: idempotente")
        with self.assertRaises(c.CartError):
            ship.create_shipment(order, lines=[{"order_item_id": item.pk, "quantity": 2}])

    def test_lineas_digitales_no_se_empaquetan(self):
        from reino.models import Product, Variant
        ebook = Product.objects.create(
            store=self.store_a, slug="pdf-x", title="PDF X", short_title="PDF X",
            base_price="5.00", status="published", offer_type="digital")
        vv = Variant.objects.create(product=ebook, sku="PDF-1", option_label="PDF", stock=9)
        cart = c.get_open_cart(self.store_a, "sh-dig", create=True)
        c.add_item(cart, vv, 1)
        ch = c.prepare_checkout(cart, "manual", idempotency_key="sh-dig")
        order = c.confirm_checkout(ch, {"name": "S", "email": "s@e.invalid"},
                                   ch.idempotency_key)
        self.assertEqual(ship.shippable_lines(order), [])
        with self.assertRaises(c.CartError):
            ship.create_shipment(order)

    def test_estados_no_retroceden_y_etiqueta_no_es_recogida(self):
        order = self._order()
        s1 = ship.create_shipment(order)
        ship.mark_status(s1, Shipment.Status.LABEL_CREATED, note="etiqueta")
        s1.refresh_from_db()
        self.assertEqual(s1.status, "label_created")
        s1, changed = ship.mark_status(s1, Shipment.Status.PREPARING)
        self.assertFalse(changed, "sin retroceso en la línea de tiempo")
        ship.mark_status(s1, Shipment.Status.IN_TRANSIT)
        ship.mark_status(s1, Shipment.Status.DELIVERED)
        s1, changed = ship.mark_status(s1, Shipment.Status.IN_TRANSIT)
        self.assertFalse(changed, "entregado no vuelve a tránsito")

    def test_tracking_duplicado_es_noop(self):
        order = self._order()
        s1 = ship.create_shipment(order)
        e1, c1 = ship.record_tracking(s1, "picked_up", event_id="prov-1")
        e2, c2 = ship.record_tracking(s1, "picked_up", event_id="prov-1")
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(s1.events.count(), 1)

    def test_proveedor_desconocido_rechazado(self):
        with self.assertRaises(c.CartError):
            ship.create_shipment(self._order("sh-x"), provider="dhl")


class QuoteTests(ShippingBase):
    def test_cotizacion_manual_con_zona_real(self):
        adapter = ship.adapter_for("manual")
        r = adapter.quote(None, {"zone": "Centro", "fee": "3.50"}, [])
        self.assertTrue(r.ok)
        self.assertEqual(r.amount, "3.50")
        r2 = adapter.quote(None, {}, [])
        self.assertFalse(r2.ok, "sin zona/tarifa no se inventa la cifra")
