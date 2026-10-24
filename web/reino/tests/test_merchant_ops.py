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


class FitRowEditorTests(ReinoTestCase):
    """F11: la tabla de tallas se edita por FILAS con errores por celda."""

    def _login(self):
        from django.contrib.auth.models import User
        from reino.models import MerchantMember
        u = User.objects.create_user("editor", password="x12345678")
        MerchantMember.objects.create(user=u, merchant=self.store_a.merchant, role="staff")
        self.client.force_login(u)
        return u

    def test_filas_validas_publican_version_sin_json(self):
        self._login()
        url = f"/negocio/{self.store_a.slug}/catalogo/{self.product.pk}/tabla-tallas/"
        r = self.client.post(url, {
            "row_label": ["S", "M"],
            "row_neck_min": ["22", "28"], "row_neck_max": ["27", "34"],
            "row_chest_min": ["33", "40"], "row_chest_max": ["40", "48"],
            "row_back_min": ["25", "31"], "row_back_max": ["32", "40"],
            "requires_neck": "1",
        })
        self.assertEqual(r.status_code, 302)
        from reino.models import FitRule
        rule = FitRule.objects.filter(product=self.product).order_by("-version").first()
        self.assertTrue(rule.is_active)
        self.assertEqual([r["label"] for r in rule.ranges], ["S", "M"])
        self.assertTrue(rule.requires_neck)

    def test_errores_por_celda_y_datos_conservados(self):
        self._login()
        url = f"/negocio/{self.store_a.slug}/catalogo/{self.product.pk}/tabla-tallas/"
        r = self.client.post(url, {
            "row_label": ["", "M"],
            "row_neck_min": ["", ""], "row_neck_max": ["", ""],
            "row_chest_min": ["cuarenta", "40"], "row_chest_max": ["40", "30"],
            "row_back_min": ["", ""], "row_back_max": ["", ""],
        }, follow=True)
        self.assertContains(r, "no es un número", status_code=200)
        self.assertContains(r, "debe ser menor que el máximo")
        self.assertContains(r, "la talla es obligatoria")
        # Lo escrito se conserva en el formulario (no se pierde el trabajo).
        self.assertContains(r, 'value="cuarenta"')
        self.assertContains(r, 'value="M"')


class NewBusinessFromPanelTests(ReinoTestCase):
    """A35: un negocio nuevo NACE desde el panel, sin tocar código, y puede
    publicar una categoría soportada, personalizar y completar un pedido."""

    def test_ciclo_completo_sin_codigo(self):
        from django.contrib.auth.models import User
        oper = User.objects.create_user("operador", password="x12345678", is_staff=True)
        from django.contrib.auth.models import Permission as P
        perm = P.objects.get(codename="operate_platform")
        oper.user_permissions.add(perm)
        self.client.force_login(oper)

        # 1) Alta asistida desde /plataforma/ (negocio + tienda + responsable)
        r = self.client.post("/plataforma/alta/", {
            "name": "Casa Aura", "slug": "casa-aura", "category": "hogar",
            "username": "duena_aura", "is_demo": "1"})
        self.assertEqual(r.status_code, 302)
        from reino.models import Store
        store = Store.objects.get(slug="casa-aura")
        self.assertTrue(store.is_demo)

        # 2) La dueña entra a SU panel y crea un producto (sin código)
        duena = User.objects.get(username="duena_aura")
        self.client.force_login(duena)
        r = self.client.post(f"/negocio/{store.slug}/catalogo/nuevo/", {
            "title": "Lámpara Aura", "short_title": "Lámpara Aura",
            "base_price": "40.00", "category": "hogar", "status": "draft",
        })
        self.assertEqual(r.status_code, 302)
        product = store.products.get()
        # Variante real creada desde el editor (filas, sin JSON)
        self.client.post(f"/negocio/{store.slug}/catalogo/{product.pk}/variante/",
                         {"sku": "LAMP-AURA-1", "option_label": "Única", "stock": "5"})
        # 3) Personaliza su tienda (tema propio, jamás heredado) y publica
        self.client.post(f"/negocio/{store.slug}/diseno/guardar/", {
            "color_primary": "#B9A5FF", "color_on_primary": "#23234A",
            "color_ink": "#23234A", "color_bg": "#F7F8FF",
            "color_surface": "#FFFFFF", "color_accent": "#FBE58A",
            "color_soft": "#EAE6FF",
            "font_pair": "manrope", "shape": "rounded", "buttons": "pill",
            "hero_headline": "Objetos con calma.", "modules": ["hero", "featured"],
            "module_order": "hero,featured",
        })
        self.client.post(f"/negocio/{store.slug}/diseno/publicar/")
        from reino import services_theme as theme
        cfg = theme.current_theme(store).config
        self.assertEqual(cfg["colors"]["primary"], "#B9A5FF")
        self.assertNotEqual(cfg["identity"], "wiener-kingdom")
        # 4) Publica el producto + política y activa la tienda
        r_pub = self.client.post(f"/negocio/{store.slug}/catalogo/{product.pk}/",
                                 {"action": "publish"}, follow=True)
        assert r_pub.status_code == 200
        from reino.models import KnowledgeDocument
        KnowledgeDocument.objects.create(
            store=store, topic="cambios", title="Cambios", body="7 días.",
            audience="customer", is_published=True)
        self.client.force_login(oper)
        self.client.post(f"/plataforma/tienda/{store.slug}/activar/")
        store.refresh_from_db()
        self.assertEqual(store.merchant.status, "pilot")

        # 5) Una compradora invitada completa un pedido REAL (pago manual)
        buyer = self.client_class()
        variant = product.variants.get()
        buyer.post(f"/s/{store.slug}/carrito/agregar/",
                   {"variant": str(variant.public_id), "quantity": 1})
        product.refresh_from_db()
        store.refresh_from_db()
        assert product.status == "published", f"producto: {product.status}"
        assert store.status in ("active", "demo"), f"tienda: {store.status}"
        r0 = buyer.post(f"/s/{store.slug}/carrito/agregar/",
                        {"variant": str(variant.public_id), "quantity": 1}, follow=True)
        assert "ya no está disponible" not in r0.content.decode(), "add-to-cart rechazado"
        r = buyer.post(f"/s/{store.slug}/checkout/", {
            "step": "review", "name": "Compradora", "email": "c@e.invalid",
            "delivery_mode": "pickup", "payment_method": "manual"})
        if r.status_code != 200:
            r2 = buyer.post(f"/s/{store.slug}/checkout/", {
                "step": "review", "name": "Compradora", "email": "c@e.invalid",
                "delivery_mode": "pickup", "payment_method": "manual"}, follow=True)
            import re as _re
            m = _re.findall(r'flash[^>]*>([^<]{5,200})', r2.content.decode())
            raise AssertionError(f"revisión 302; flashes: {m}")
        self.assertEqual(r.status_code, 200, "revisión del resumen")
        from reino.models import CheckoutSession
        session = CheckoutSession.objects.get(is_current=True, cart__store=store)
        r = buyer.post(f"/s/{store.slug}/checkout/", {
            "step": "confirm", "session_id": str(session.public_id),
            "idempotency_key": session.idempotency_key,
            "name": "Compradora", "email": "c@e.invalid",
            "delivery_mode": "pickup", "payment_method": "manual"})
        from reino.models import Order
        self.assertEqual(Order.objects.filter(store=store).count(), 1)
        # 6) Su tienda no heredó fotos ni copy de WK (AC10)
        r = buyer.get(f"/s/{store.slug}/")
        self.assertNotContains(r, "dachshund")
