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
        draft.save(update_fields=["config"])
        theme.publish(store, draft)
        self.assertEqual(theme.current_theme(store).config["colors"]["primary"], "#FF4D9D")

        d2 = theme.get_or_create_draft(store)
        d2.config["colors"]["primary"] = "#2C3FFF"
        d2.save(update_fields=["config"])
        theme.publish(store, d2)
        self.assertEqual(theme.current_theme(store).config["colors"]["primary"], "#2C3FFF")

        restored = theme.restore(store, 1)
        self.assertEqual(restored.config["colors"]["primary"], "#FF4D9D")
        self.assertEqual(theme.current_theme(store).version, restored.version)
        # Historial intacto: 3 versiones registradas.
        self.assertEqual(StoreThemeVersion.objects.filter(store=store).count(), 3)
        # Solo UNA publicada.
        self.assertEqual(StoreThemeVersion.objects.filter(
            store=store, status="published").count(), 1)

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
            "color_primary": "#FF4D9D", "color_ink": "#15172E",
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
