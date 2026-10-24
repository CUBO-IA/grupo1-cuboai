"""Tema versionado + estudio de diseño (AC10, AC11, AC12) y medios reales."""

from io import BytesIO

from django.contrib.auth.models import User
from PIL import Image

from reino import services_theme as theme
from reino.models import MediaAsset, MerchantMember, StoreThemeVersion
from reino.tests import ReinoTestCase


class ThemeServiceTests(ReinoTestCase):
    def test_neutral_default_for_new_store(self):
        """AC10: una tienda nueva NUNCA hereda activos ni tema de otra marca."""
        from reino.models import Merchant, Store
        m = Merchant.objects.create(name="Nueva")
        store = Store.objects.create(merchant=m, slug="nueva", name="Tienda Nueva",
                                     category="hogar", status="active")
        current = theme.current_theme(store)
        self.assertEqual(current.config["identity"], "neutral")
        self.assertNotEqual(current.config["colors"]["primary"], "#FF4D9D")  # no WK

    def test_publish_and_restore_flow(self):
        """AC11: publicar, cambiar, republicar y restaurar conserva historial."""
        store = self.store_a
        draft = theme.get_or_create_draft(store)
        draft.config["colors"]["primary"] = "#FF4D9D"
        draft.config["colors"]["on_primary"] = "#15172E"  # par REAL (F07)
        draft.save(update_fields=["config"])
        theme.publish(store, draft)
        self.assertEqual(theme.current_theme(store).config["colors"]["primary"], "#FF4D9D")

        d2 = theme.get_or_create_draft(store)
        d2.config["colors"]["primary"] = "#2C3FFF"
        d2.config["colors"]["on_primary"] = "#FFFFFF"
        d2.save(update_fields=["config"])
        theme.publish(store, d2)
        self.assertEqual(theme.current_theme(store).config["colors"]["primary"], "#2C3FFF")

        restored = theme.restore(store, 1)
        self.assertEqual(restored.config["colors"]["primary"], "#FF4D9D")
        self.assertEqual(theme.current_theme(store).version, restored.version)
        # F09: historial INMUTABLE — 4 versiones registradas y las TRES
        # publicadas siguen existiendo; sólo una es la vigente (is_current).
        self.assertEqual(StoreThemeVersion.objects.filter(store=store).count(), 3)
        self.assertEqual(StoreThemeVersion.objects.filter(
            store=store, status="published").count(), 3)
        self.assertEqual(StoreThemeVersion.objects.filter(
            store=store, is_current=True).count(), 1)

    def test_invalid_contrast_rejected(self):
        store = self.store_a
        draft = theme.get_or_create_draft(store)
        draft.config["colors"]["ink"] = "#FFF8ED"  # casi igual al fondo
        draft.config["colors"]["bg"] = "#FFF8ED"
        draft.save(update_fields=["config"])
        with self.assertRaises(theme.ThemeError):
            theme.publish(store, draft)
        # La versión visible no se destruyó:
        self.assertIsNone(store.theme_versions.filter(status="published").first())

    def test_themes_are_isolated_between_stores(self):
        a = theme.get_or_create_draft(self.store_a)
        a.config["colors"]["primary"] = "#123456"
        a.save(update_fields=["config"])
        theme.publish(self.store_a, a)
        other = theme.current_theme(self.store_b)
        self.assertNotEqual(other.config["colors"].get("primary"), "#123456")


class DesignStudioViewTests(ReinoTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="dueno", password="x")
        MerchantMember.objects.create(user=self.owner, merchant=self.merchant_a,
                                      role="owner")
        self.client.force_login(self.owner)

    def test_studio_save_publish_restore(self):
        base = f"/negocio/{self.store_a.slug}/diseno/"
        r = self.client.get(base)
        self.assertEqual(r.status_code, 200)
        # Guardar borrador con color nuevo.
        self.client.post(base + "guardar/", {
            "color_primary": "#FF4D9D", "color_on_primary": "#15172E",
            "color_ink": "#15172E",
            "color_bg": "#FFF8ED", "color_surface": "#FFFFFF",
            "color_accent": "#FFB548", "color_soft": "#FFE9F2",
            "font_pair": "manrope-fraunces", "shape": "rounded", "buttons": "pill",
            "modules": ["hero", "featured"],
        })
        self.client.post(base + "publicar/")
        self.assertEqual(theme.current_theme(self.store_a).config["colors"]["primary"],
                         "#FF4D9D")
        # La portada pública usa el tema publicado (variables CSS en body).
        r = self.client.get(f"/s/{self.store_a.slug}/")
        self.assertContains(r, "--rk-primary:#FF4D9D")
        # Restaurar versión 1 (nueva versión v2 publicada; historial intacto).
        self.client.post(base + "restaurar/1/")
        self.assertEqual(theme.current_theme(self.store_a).version, 2)

    def test_studio_requires_settings_capability(self):
        from reino.models import MerchantMember as MM
        logistics = User.objects.create_user(username="logi", password="x")
        MM.objects.create(user=logistics, merchant=self.merchant_a, role="logistics")
        self.client.force_login(logistics)
        r = self.client.get(f"/negocio/{self.store_a.slug}/diseno/")
        self.assertEqual(r.status_code, 403)

    def test_media_upload_real_file(self):
        """AC12: el comerciante sube una imagen REAL; se valida el contenido."""
        img = Image.new("RGB", (640, 480), (255, 77, 157))
        buf = BytesIO()
        img.save(buf, "JPEG")
        buf.seek(0)
        buf.name = "portada.jpg"
        r = self.client.post(f"/negocio/{self.store_a.slug}/medios/subir/", {
            "file": buf, "alt": "Portada de prueba", "origin": "foto propia",
        })
        self.assertEqual(r.status_code, 302)
        asset = MediaAsset.objects.get(store=self.store_a)
        self.assertEqual(asset.width, 640)
        self.assertTrue(asset.file.name.endswith(".jpg"))

    def test_media_upload_rejects_non_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile("foto.jpg", b"no soy una imagen", content_type="image/jpeg")
        self.client.post(f"/negocio/{self.store_a.slug}/medios/subir/",
                         {"file": bad, "alt": "x"})
        self.assertEqual(MediaAsset.objects.count(), 0)


class RevisionThreeThemeTests(ReinoTestCase):
    """F07–F09: pares reales, preview privado, versiones inmutables."""

    def test_f07_on_primary_se_guarda_y_renderiza(self):
        """El par acción/texto-sobre-acción persiste y llega al CSS del body."""
        store = self.store_a
        draft = theme.get_or_create_draft(store)
        draft.config["colors"]["primary"] = "#B9A5FF"
        draft.config["colors"]["on_primary"] = "#23234A"
        draft.save(update_fields=["config"])
        theme.publish(store, draft)
        r = self.client.get(f"/s/{store.slug}/")
        self.assertContains(r, "--rk-on_primary:#23234A")
        # El CSS ya no fija blanco sobre la acción: usa el par del tema.
        from django.conf import settings
        css = open(settings.BASE_DIR / "static/reino/css/reino.css").read()
        self.assertIn("var(--rk-on_primary", css)
        self.assertNotIn(".btn--primary, .btn--primary:visited { color: #fff; }", css)

    def test_f07_blanco_sobre_lila_rechazado(self):
        """Blanco fijo sobre #B9A5FF (~2.1:1) NO pasa la validación (F07)."""
        store = self.store_a
        draft = theme.get_or_create_draft(store)
        draft.config["colors"]["primary"] = "#B9A5FF"
        draft.config["colors"]["on_primary"] = "#FFFFFF"
        draft.save(update_fields=["config"])
        errors = theme.validate_config(draft.config)
        self.assertTrue(any("texto de acción" in e.lower() for e in errors))
        with self.assertRaises(theme.ThemeError):
            theme.publish(store, draft)

    def test_f07_pares_por_defecto_cumplen_aa(self):
        """Todas las identidades de fábrica cumplen el par de acción AA."""
        for identity in ("reino", "wiener-kingdom", "estudio-nube", "neutral"):
            cfg = theme.default_config(identity)
            self.assertEqual(theme.validate_config(cfg), [], identity)
            c = cfg["colors"]
            self.assertGreaterEqual(
                theme.contrast_ratio(c["on_primary"], c["primary"]), 4.5, identity)

    def _login_owner(self):
        from django.contrib.auth.models import User
        from reino.models import MerchantMember
        u = User.objects.create_user("duena", password="x12345678")
        MerchantMember.objects.create(user=u, merchant=self.store_a.merchant, role="owner")
        self.client.force_login(u)
        return u

    def test_f08_preview_muestra_borrador_sin_publicar_y_es_privado(self):
        u = self._login_owner()
        draft = theme.get_or_create_draft(self.store_a, user=u)
        draft.config.setdefault("hero", {})["headline"] = "TITULAR DE BORRADOR UNICO"
        draft.save(update_fields=["config"])
        url = f"/negocio/{self.store_a.slug}/diseno/previsualizar/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "TITULAR DE BORRADOR UNICO")
        # Embebible mismo origen SOLO aquí; la portada pública mantiene DENY.
        self.assertEqual(r["X-Frame-Options"], "SAMEORIGIN")
        public = self.client.get(f"/s/{self.store_a.slug}/")
        self.assertNotContains(public, "TITULAR DE BORRADOR UNICO")
        self.assertEqual(public["X-Frame-Options"], "DENY")

    def test_f08_preview_rechaza_a_quien_no_es_del_negocio(self):
        from django.contrib.auth.models import User
        u = User.objects.create_user("ajena", password="x12345678")
        self.client.force_login(u)
        r = self.client.get(f"/negocio/{self.store_a.slug}/diseno/previsualizar/")
        self.assertIn(r.status_code, (302, 403, 404))
        # Y jamás con ?draft=true desde la portada pública.
        r2 = self.client.get(f"/s/{self.store_a.slug}/?draft=true")
        self.assertNotEqual(r2.status_code, 404)
        self.assertNotContains(r2, "Vista previa")

    def test_f09_publicar_no_convierte_historial_en_borrador(self):
        import hashlib, json
        store = self.store_a
        d1 = theme.get_or_create_draft(store)
        d1.config["colors"]["primary"] = "#FF4D9D"
        d1.config["colors"]["on_primary"] = "#15172E"
        theme.save_draft_config(d1, d1.config)
        theme.publish(store, d1)
        d2 = theme.get_or_create_draft(store)
        d2.config["colors"]["primary"] = "#2C3FFF"
        d2.config["colors"]["on_primary"] = "#FFFFFF"
        theme.save_draft_config(d2, d2.config)
        theme.publish(store, d2)

        def hashes():
            return {v.version: hashlib.sha256(
                json.dumps(v.config, sort_keys=True).encode()).hexdigest()
                for v in store.theme_versions.all()}

        before = hashes()
        theme.restore(store, 1)
        after = hashes()
        # Las versiones previas NO cambiaron (ni v1 ni v2); la restauración
        # es una versión NUEVA (v3) copia de v1.
        for version, h in before.items():
            self.assertEqual(after[version], h, f"la versión {version} fue mutada")
        self.assertEqual(len(after), 3)
        self.assertEqual(after[3], before[1])
        # Y una versión publicada no puede editarse como borrador.
        v1 = store.theme_versions.get(version=1)
        with self.assertRaises(theme.ThemeError):
            theme.save_draft_config(v1, v1.config)


class AssignAndOrderTests(ReinoTestCase):
    """A37/A40: asignación real de medios y orden exacto de módulos."""

    def _login(self):
        from django.contrib.auth.models import User
        from reino.models import MerchantMember
        u = User.objects.create_user("dise", password="x12345678")
        MerchantMember.objects.create(user=u, merchant=self.store_a.merchant, role="owner")
        self.client.force_login(u)
        return u

    def _asset(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = BytesIO()
        Image.new("RGB", (60, 60), (200, 30, 120)).save(buf, "PNG")
        buf.seek(0)
        from reino.models import MediaAsset
        return MediaAsset.objects.create(
            store=self.store_a, alt="foto propia", width=60, height=60,
            file=SimpleUploadedFile("f.png", buf.read(), content_type="image/png"))

    def test_asignar_a_producto_aparece_en_ficha(self):
        self._login()
        asset = self._asset()
        r = self.client.post(
            f"/negocio/{self.store_a.slug}/diseno/media/{asset.pk}/asignar/",
            {"target": "product", "product_id": self.product.pk})
        self.assertEqual(r.status_code, 302)
        from reino.models import ProductMedia
        pm = ProductMedia.objects.get(product=self.product, asset=asset)
        self.assertTrue(pm.url.startswith("/media/") or "uploads" in pm.url)
        r = self.client.get(f"/s/{self.store_a.slug}/producto/{self.product.slug}/")
        self.assertContains(r, pm.url)

    def test_asignar_a_hero_se_ve_tras_publicar(self):
        self._login()
        asset = self._asset()
        self.client.post(f"/negocio/{self.store_a.slug}/diseno/media/{asset.pk}/asignar/",
                         {"target": "hero"})
        draft = theme.get_or_create_draft(self.store_a)
        self.assertEqual(draft.config["hero"]["media_asset_id"], asset.pk)
        # Preview del borrador ya la muestra; la pública todavía no.
        r = self.client.get(f"/negocio/{self.store_a.slug}/diseno/previsualizar/")
        self.assertContains(r, asset.file.url)
        theme.publish(self.store_a, draft)
        r = self.client.get(f"/s/{self.store_a.slug}/")
        self.assertContains(r, asset.file.url)

    def test_orden_de_modulos_se_conserva_exacto(self):
        self._login()
        base = f"/negocio/{self.store_a.slug}/diseno/"
        self.client.post(base + "guardar/", {
            "color_primary": "#FF4D9D", "color_on_primary": "#15172E",
            "module_order": "policies,hero,contact",
            "modules": ["hero", "policies"],
        })
        draft = theme.get_or_create_draft(self.store_a)
        keys = [m["key"] for m in draft.config["modules"]]
        self.assertEqual(keys[:3], ["policies", "hero", "contact"])
        visible = [m["key"] for m in draft.config["modules"] if m["visible"]]
        self.assertEqual(visible[:2], ["policies", "hero"])
