"""Estudio de diseño de la tienda + carga real de medios (§13, AC11/AC12).

Borrador y publicación separados, historial con restauración, preview
móvil/escritorio, carga de imágenes por archivo y pruebas de conexión reales
para integraciones. Todo con capacidad «settings» del tenant de la URL.
"""

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services_integrations, services_media, services_theme
from .models import MediaAsset
from .views_merchant import _flash, merchant_view, require_capability


@merchant_view
@require_capability("settings")
def design_studio(request, store):
    """Editor: controles + preview, borrador vs publicada, historial (§13)."""
    draft = services_theme.get_or_create_draft(store, user=request.user)
    published = store.theme_versions.filter(status="published").first()
    versions = store.theme_versions.all()[:10]
    visible_modules = {m.get("key") for m in (draft.config.get("modules") or [])
                       if m.get("visible")} or set(services_theme.MODULE_KEYS)
    return render(request, "reino/merchant_diseno.html", {
        "store": store, "draft": draft, "published": published,
        "versions": versions, "shapes": sorted(services_theme.SHAPES),
        "visible_modules": visible_modules,
        "font_pairs": services_theme.FONT_PAIRS,
        "button_styles": sorted(services_theme.BUTTON_STYLES),
        "module_keys": sorted(services_theme.MODULE_KEYS),
        "products": store.products.filter(status="published").prefetch_related("media"),
        "media": store.media_assets.all()[:24],
    })


@merchant_view
@require_capability("settings")
@require_POST
def design_save(request, store):
    """Guardar borrador (sin publicar): colores, tipografía, formas, hero,
    módulos y contenido. Validación de formato; contraste se exige al
    PUBLICAR."""
    draft = services_theme.get_or_create_draft(store, user=request.user)
    config = dict(draft.config)
    colors = dict(config.get("colors") or {})
    for key in ("ink", "bg", "surface", "primary", "accent", "soft"):
        value = (request.POST.get(f"color_{key}") or "").strip()
        if value:
            colors[key] = value[:7]
    config["colors"] = colors
    for key in ("font_pair", "shape", "buttons"):
        value = (request.POST.get(key) or "").strip()
        if value:
            config[key] = value
    hero = dict(config.get("hero") or {})
    hero["headline"] = (request.POST.get("hero_headline") or "")[:80]
    hero["sub"] = (request.POST.get("hero_sub") or "")[:140]
    hero["product_id"] = request.POST.get("hero_product") or None
    config["hero"] = hero
    visible = set(request.POST.getlist("modules"))
    config["modules"] = [
        {"key": key, "visible": key in visible}
        for key in sorted(services_theme.MODULE_KEYS)
    ]
    draft.config = config
    draft.created_by = request.user
    draft.save(update_fields=["config"])
    _flash(request, "Borrador guardado. Publicá para que la tienda lo muestre.")
    return redirect("reino_merchant_diseno", slug=store.slug)


@merchant_view
@require_capability("settings")
@require_POST
def design_publish(request, store):
    """Publicar: validación dura (contraste AA, parejas, módulos). Un error
    NO destruye la versión visible (AC11)."""
    draft = services_theme.get_or_create_draft(store, user=request.user)
    try:
        services_theme.publish(store, draft, user=request.user)
        _flash(request, f"Versión {draft.version} publicada.")
    except services_theme.ThemeError as exc:
        _flash(request, f"No se publicó: {exc}")
    return redirect("reino_merchant_diseno", slug=store.slug)


@merchant_view
@require_capability("settings")
@require_POST
def design_restore(request, store, version):
    """Restaurar una versión anterior (nueva versión; historial intacto)."""
    try:
        new = services_theme.restore(store, version, user=request.user)
        _flash(request, f"Se restauró la versión {version} como v{new.version} publicada.")
    except services_theme.ThemeError as exc:
        _flash(request, f"No se restauró: {exc}")
    return redirect("reino_merchant_diseno", slug=store.slug)


@merchant_view
@require_capability("settings")
@require_POST
def media_upload(request, store):
    """Carga de imagen REAL por archivo (AC12): validada por contenido."""
    try:
        services_media.save_upload(
            store, request.FILES.get("file"),
            alt=request.POST.get("alt", ""), origin=request.POST.get("origin", ""),
            focal_x=request.POST.get("focal_x") or 0.5,
            focal_y=request.POST.get("focal_y") or 0.5, user=request.user)
        _flash(request, "Imagen subida y validada.")
    except services_media.MediaError as exc:
        _flash(request, f"No se subió: {exc}")
    return redirect("reino_merchant_diseno", slug=store.slug)


@merchant_view
@require_capability("settings")
@require_POST
def integration_probe(request, store, key):
    """«Probar conexión»: ejecuta la comprobación REAL y la registra (AC25)."""
    if key == "ai":
        row = services_integrations.probe_ai()
    elif key == "email":
        row = services_integrations.probe_email()
    else:
        _flash(request, "Esa integración no tiene prueba automática.")
        return redirect("reino_merchant_settings", slug=store.slug)
    _flash(request, f"{key}: {row.get_state_display()} — {row.detail}")
    return redirect("reino_merchant_settings", slug=store.slug)
