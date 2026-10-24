"""Carga real de imágenes del comerciante (§13).

Valida tipo y tamaño con el contenido real del archivo (no la extensión),
guarda dimensiones, punto focal y texto alternativo. Nunca se piden rutas
internas al comerciante.
"""

from django.conf import settings
from PIL import Image

from .models import MediaAsset

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_DIMENSION = 2400  # se redimensiona proporcionalmente por encima de esto


class MediaError(Exception):
    """Archivo rechazado con mensaje accionable."""


def save_upload(store, uploaded, alt, origin="", focal_x=0.5, focal_y=0.5, user=None):
    """Guarda un archivo subido como MediaAsset validado."""
    if uploaded is None:
        raise MediaError("Adjuntá un archivo de imagen.")
    if uploaded.size > settings.REINO_MEDIA_MAX_BYTES:
        limit_mb = settings.REINO_MEDIA_MAX_BYTES // (1024 * 1024)
        raise MediaError(f"La imagen supera el máximo de {limit_mb} MB.")
    try:
        img = Image.open(uploaded)
        img.verify()
    except Exception:
        raise MediaError("El archivo no es una imagen válida.")
    uploaded.seek(0)
    img = Image.open(uploaded)
    if img.format not in ALLOWED_FORMATS:
        raise MediaError("Formato no admitido: usá JPG, PNG o WebP.")
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if max(img.size) > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    asset = MediaAsset(store=store, alt=(alt or "")[:160], origin=(origin or "")[:160],
                       focal_x=min(max(float(focal_x or 0.5), 0.0), 1.0),
                       focal_y=min(max(float(focal_y or 0.5), 0.0), 1.0),
                       width=img.width, height=img.height, uploaded_by=user)
    # Guardamos el contenido validado (no el stream crudo del cliente).
    from io import BytesIO
    from django.core.files.base import ContentFile
    buffer = BytesIO()
    img.save(buffer, "JPEG", quality=86, optimize=True)
    asset.file.save(f"{store.slug}-{asset.pk or 'nuevo'}.jpg",
                    ContentFile(buffer.getvalue()), save=False)
    asset.save()
    return asset
