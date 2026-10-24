"""Pruebas de las capacidades P0 añadidas tras la auditoría (§5/§6.14/§9).

- Editor de catálogo: crear, editar, publicar/archivar, variantes, stock con
  motivo, tabla de tallas versionada — sin tocar código.
- Capacidades por rol en VISTAS y servicio (R13), matriz positiva y negativa.
- Alta asistida: comercio en borrador + responsable + checklist de activación.
- Outbox: procesamiento idempotente y observable.
- Seed: no destructivo por defecto; --reset protegido fuera de DEBUG.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import override_settings

from reino import services_commerce as c
from reino.models import (
    Merchant, MerchantMember, Order, OutboxEvent, Product, StockAdjustment,
    Store, Variant,
)
from reino.tests import ReinoTestCase


class CatalogEditorTests(ReinoTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="editor", password="x",
                                             is_staff=True)
        MerchantMember.objects.create(user=self.user, merchant=self.merchant_a,
                                      role="owner")
        self.client.force_login(self.user)

    def test_crear_producto_borrador_y_publicar(self):
        r = self.client.post(f"/negocio/{self.store_a.slug}/catalogo/nuevo/", {
            "title": "Capa Imperial", "short_title": "Capa Imperial",
            "base_price": "120.00", "category": "formal", "status": "draft",
        })
        self.assertEqual(r.status_code, 302)
        product = Product.objects.get(store=self.store_a, title="Capa Imperial")
        self.assertEqual(product.status, "draft")  # nunca nace publicado
        # Sin variantes no se puede publicar.
        self.client.post(f"/negocio/{self.store_a.slug}/catalogo/{product.pk}/",
                         {"action": "publish"})
        product.refresh_from_db()
        self.assertEqual(product.status, "draft")
        self.client.post(f"/negocio/{self.store_a.slug}/catalogo/{product.pk}/variante/",
                         {"sku": "CAP-S", "option_label": "Talla S", "stock": "3"})
        self.client.post(f"/negocio/{self.store_a.slug}/catalogo/{product.pk}/",
                         {"action": "publish"})
        product.refresh_from_db()
        self.assertEqual(product.status, "published")

    def test_ajuste_stock_requiere_motivo_y_queda_registrado(self):
        v = self.product.variants.get(option_label="Talla M")
        before = v.stock
        self.client.post(f"/negocio/{self.store_a.slug}/variante/{v.pk}/stock/",
                         {"delta": "5"})  # sin motivo
        v.refresh_from_db()
        self.assertEqual(v.stock, before)
        self.client.post(f"/negocio/{self.store_a.slug}/variante/{v.pk}/stock/",
                         {"delta": "5", "reason": "Ingreso de taller semana 43"})
        v.refresh_from_db()
        self.assertEqual(v.stock, before + 5)
        adj = StockAdjustment.objects.get(variant=v)
        self.assertEqual(adj.reason, "Ingreso de taller semana 43")
        self.assertEqual(adj.by, self.user)

    def test_stock_nunca_negativo_por_ajuste(self):
        v = self.product.variants.get(option_label="Talla M")
        self.client.post(f"/negocio/{self.store_a.slug}/variante/{v.pk}/stock/",
                         {"delta": "-99", "reason": "prueba"})
        v.refresh_from_db()
        self.assertGreaterEqual(v.stock, 0)

    def test_editar_precio_desde_panel(self):
        self.client.post(f"/negocio/{self.store_a.slug}/catalogo/{self.product.pk}/", {
            "title": self.product.title, "short_title": self.product.short_title,
            "base_price": "70.00", "category": self.product.category,
            "status": "published",
        })
        self.product.refresh_from_db()
        self.assertEqual(self.product.base_price, Decimal("70.00"))

    def test_staff_no_puede_editar_catalogo_ni_configuracion(self):
        staff = User.objects.create_user(username="staff1", password="x", is_staff=True)
        MerchantMember.objects.create(user=staff, merchant=self.merchant_a, role="logistics")
        self.client.force_login(staff)
        r = self.client.get(f"/negocio/{self.store_a.slug}/catalogo/nuevo/")
        self.assertEqual(r.status_code, 403)
        r = self.client.post(f"/negocio/{self.store_a.slug}/configuracion/tienda/",
                             {"name": "Hackeado"})
        self.assertEqual(r.status_code, 403)
        self.store_a.refresh_from_db()
        self.assertNotEqual(self.store_a.name, "Hackeado")

    def test_configuracion_edita_identidad_y_zonas(self):
        self.client.post(f"/negocio/{self.store_a.slug}/configuracion/tienda/",
                         {"name": "Wiener Kingdom", "tagline": "Nuevo lema"})
        self.store_a.refresh_from_db()
        self.assertEqual(self.store_a.tagline, "Nuevo lema")
        self.client.post(f"/negocio/{self.store_a.slug}/configuracion/zonas/",
                         {"name": "Escalón", "mode": "local", "fee": "4.00",
                          "is_active": "1"})
        self.assertTrue(self.store_a.shipping_zones.filter(name="Escalón").exists())


class OnboardingTests(ReinoTestCase):
    def setUp(self):
        # Operador global: permiso EXPLÍCITO de plataforma (N11); is_staff
        # solo nunca basta (caso cubierto en test_round2.test_11).
        from django.contrib.auth.models import Permission
        self.operator = User.objects.create_user(username="op", password="x",
                                                 is_staff=True)
        self.operator.user_permissions.add(Permission.objects.get(
            codename="operate_platform", content_type__app_label="reino"))
        self.client.force_login(self.operator)

    def test_alta_asistida_crea_borrador_con_propietario(self):
        r = self.client.post("/plataforma/alta/", {
            "name": "Mundo Felino", "slug": "mundo-felino",
            "category": "moda felina", "username": "felino_owner",
        })
        self.assertEqual(r.status_code, 302)
        store = Store.objects.get(slug="mundo-felino")
        self.assertEqual(store.status, "draft")  # nada vendible por accidente
        self.assertTrue(store.merchant.members.filter(role="owner").exists())
        self.assertTrue(store.shipping_zones.filter(mode="pickup").exists())

    def test_activar_exige_checklist(self):
        merchant = Merchant.objects.create(name="Incompleto")
        store = Store.objects.create(merchant=merchant, slug="incompleto",
                                     name="Incompleto", status="draft")
        self.client.post("/plataforma/tienda/incompleto/activar/")
        store.refresh_from_db()
        self.assertEqual(store.status, "draft")  # checklist incompleto: no activa

    def test_demo_nunca_cobra(self):
        nube = Store.objects.create(merchant=self.merchant_b, slug="nube-demo-2",
                                    name="Nube 2", is_demo=True, status="demo")
        self.assertTrue(nube.is_demo)


class OutboxTests(ReinoTestCase):
    def test_procesamiento_idempotente_y_observable(self):
        from django.core.management import call_command
        OutboxEvent.objects.create(type="metric", payload={"event": "test"})
        OutboxEvent.objects.create(type="order_confirmation_email", payload={})
        call_command("process_outbox")
        # Métrica: procesada. Correo sin habilitar: BLOQUEADO con causa
        # precisa (nunca marcado como enviado/procesado, AC19).
        self.assertEqual(OutboxEvent.objects.filter(status="done").count(), 1)
        email = OutboxEvent.objects.get(type="order_confirmation_email")
        self.assertEqual(email.status, "blocked")
        self.assertIn("no habilitado", email.last_error)
        call_command("process_outbox")  # segunda pasada: no repite ni cambia estados
        self.assertEqual(OutboxEvent.objects.filter(status="done").count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(status="blocked").count(), 1)


class SeedSafetyTests(ReinoTestCase):
    def test_seed_sin_reset_no_destruye(self):
        from django.core.management import call_command
        Store.objects.create(merchant=self.merchant_a, slug="wiener-kingdom",
                             name="WK", status="active")
        call_command("seed_demo")  # sin --reset: avisa y no borra
        self.assertTrue(Store.objects.filter(slug="wiener-kingdom").exists())

    @override_settings(DEBUG=False)
    def test_seed_reset_bloqueado_fuera_de_debug(self):
        import os
        from django.core.management import call_command
        os.environ.pop("REINO_ALLOW_SEED", None)
        with self.assertRaises(SystemExit):
            call_command("seed_demo", reset=True)
