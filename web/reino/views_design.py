"""Estudio de diseño de la tienda + carga real de medios (§13, AC11/AC12).

Borrador y publicación separados, historial con restauración, preview
móvil/escritorio, carga de imágenes por archivo y pruebas de conexión reales
para integraciones. Todo con capacidad «settings» del tenant de la URL.
"""

from django.shortcuts import redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from . import services_integrations, services_media, services_theme
from .models import MediaAsset
from .views_merchant import _flash, merchant_view, require_capability


@merchant_view
@require_capability("settings")
def design_studio(request, store):
    """Editor: controles + preview, borrador vs publicada, historial (§13)."""
    draft = services_theme.get_or_create_draft(store, user=request.user)
    published = store.theme_versions.filter(status="published", is_current=True).first()
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
@xframe_options_sameorigin  # F08: sólo ESTA vista puede embebido mismo-origen
def design_preview(request, store):
    """Vista previa PRIVADA del borrador (F08, §10).

    - Requiere membresía con capacidad «settings» (merchant_view): jamás se
      activa con ?draft=true desde fuera ni la ve el público.
    - Muestra el BORRADOR (no la versión publicada) sobre la portada real,
      con enlaces acotados al propio preview y aviso visible.
    - X-Frame-Options SAMEORIGIN sólo aquí; el resto del sitio mantiene DENY.
    """
    draft = services_theme.get_or_create_draft(store, user=request.user)
    from . import services_visibility as visibility
    from .views_storefront import _store_home_context
    ctx = _store_home_context(request, store, theme_config=draft.config)
    ctx["reino_preview"] = True
    response = render(request, "reino/store_home.html", ctx)
    response["X-Robots-Tag"] = "noindex"
    return response


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
    for key in ("ink", "bg", "surface", "primary", "on_primary", "accent", "soft"):
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
    # Orden EXACTO elegido por la persona (A40): jamás reordenar por
    # alfabeto. Prioridad: lista explícita del editor; si no, orden previo.
    visible = set(request.POST.getlist("modules"))
    posted_order = [k for k in (request.POST.get("module_order") or "").split(",") if k]
    previous = [m.get("key") for m in (config.get("modules") or []) if m.get("key")]
    order = [k for k in (posted_order or previous) if k in services_theme.MODULE_KEYS]
    order += [k for k in previous if k not in order and k in services_theme.MODULE_KEYS]
    order += [k for k in services_theme.MODULE_KEYS if k not in order]  # nuevos al final
    config["modules"] = [{"key": key, "visible": key in visible} for key in order]
    draft.config = config
    draft.created_by = request.user
    draft.save(update_fields=["config"])
    _flash(request, "Borrador guardado. Publicá para que la tienda lo muestre.")
    return redirect("reino_merchant_diseno", slug=store.slug)


@merchant_view
@require_capability("settings")
@require_POST
def media_assign(request, store, asset_id):
    """Asigna una imagen subida a un destino REAL (A37): producto o hero.

    La imagen queda usada de verdad (ProductMedia respaldado por el asset o
    hero.media_asset_id del borrador); verla en una galería no completa nada.
    """
    asset = store.media_assets.filter(pk=asset_id).first()
    if asset is None:
        _flash(request, "Esa imagen no existe en esta tienda.")
        return redirect("reino_merchant_diseno", slug=store.slug)
    target = request.POST.get("target")
    if target == "hero":
        draft = services_theme.get_or_create_draft(store, user=request.user)
        config = dict(draft.config)
        hero = dict(config.get("hero") or {})
        hero["media_asset_id"] = asset.pk
        config["hero"] = hero
        services_theme.save_draft_config(draft, config)
        _flash(request, "Imagen asignada al hero del borrador. Publicala para verla en la tienda.")
    elif target == "product":
        from .models import Product, ProductMedia
        product = Product.objects.filter(store=store, pk=request.POST.get("product_id")).first()
        if product is None:
            _flash(request, "Elegí un producto válido de esta tienda.")
        else:
            ProductMedia.objects.create(
                product=product, asset=asset, path="", alt=asset.alt,
                source=asset.origin or "subida por el comerciante")
            _flash(request, f"Imagen asignada a «{product.short_title}». Ya se ve en la ficha.")
    else:
        _flash(request, "Elegí un destino: hero o producto.")
    return redirect("reino_merchant_diseno", slug=store.slug)


@merchant_view
@require_capability("settings")
@require_POST
def design_module_move(request, store):
    """Subir/bajar un módulo (alternativa accesible al arrastre, §10.4)."""
    draft = services_theme.get_or_create_draft(store, user=request.user)
    config = dict(draft.config)
    modules = [dict(m) for m in (config.get("modules") or [])]
    key = request.POST.get("key", "")
    direction = 1 if request.POST.get("dir") == "down" else -1
    idx = next((i for i, m in enumerate(modules) if m.get("key") == key), None)
    target = None if idx is None else idx + direction
    if idx is not None and 0 <= target < len(modules):
        modules[idx], modules[target] = modules[target], modules[idx]
        config["modules"] = modules
        services_theme.save_draft_config(draft, config)
        _flash(request, f"Módulo «{key}» movido.")
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
