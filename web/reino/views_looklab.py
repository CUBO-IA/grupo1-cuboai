"""S04 · LookLab: flujo de cuatro etapas editables y una revelación.

- Borrador en sesión; volver atrás conserva información (A07).
- La foto jamás es obligatoria ni se usa para deducir medidas.
- «No tengo las medidas» continúa con talla pendiente.
- La revelación no simula una espera de análisis ni premarca extras.
- Memoria solo con consentimiento explícito separado.
"""

from decimal import Decimal, InvalidOperation

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services_fit, services_memory, tenancy
from .models import Consent, Product, Variant
from .services_recommend import compose_bundle, normalize_intent, recommend, variants_with_fit
from .views_storefront import _store_view

STEPS = ["perfil", "medidas", "personalidad", "ocasion", "revelacion"]

STYLES = [
    ("royal-classic", "Royal Classic", "Sobrio y pulido."),
    ("urban-king", "Urban King", "Cotidiano y moderno."),
    ("little-adventurer", "Little Adventurer", "Práctico para explorar."),
    ("party-royalty", "Party Royalty", "Ocasión especial."),
]

OCCASIONS = [
    ("paseo", "Paseo"), ("celebracion", "Celebración"),
    ("fotos", "Fotos"), ("diario", "Día a día"), ("regalo", "Es un regalo"),
]


def _step(request, store):
    step = request.GET.get("paso", "perfil")
    return step if step in STEPS else "perfil"


@_store_view
def looklab(request, store):
    """Pantalla principal del flujo (una URL, pasos por ?paso=)."""
    session_key = request.session.session_key
    draft = tenancy.looklab_draft(request, store)
    step = _step(request, store)
    errors = {}

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "perfil":
            profile_id = request.POST.get("profile_id", "")
            if profile_id == "new":
                alias = request.POST.get("alias", "").strip()
                if not alias:
                    errors["alias"] = "Poné un nombre o alias a tu pequeño rey."
                else:
                    profile = services_memory.create_profile(
                        store, session_key, alias, kind="dog",
                        breed=request.POST.get("breed", "").strip(),
                    )
                    tenancy.set_active_profile(request, store, profile.public_id)
                    draft["profile_id"] = str(profile.public_id)
            elif profile_id == "explore":
                draft["profile_id"] = None
                tenancy.set_active_profile(request, store, None)
            else:
                profile = services_memory.get_profile(store, session_key, profile_id)
                if profile is None:
                    errors["profile"] = "Ese perfil ya no existe."
                else:
                    tenancy.set_active_profile(request, store, profile.public_id)
                    draft["profile_id"] = str(profile.public_id)
            if not errors:
                draft["step"] = "medidas"
                tenancy.set_looklab_draft(request, store, draft)
                return redirect(f"{request.path}?paso=medidas")

        elif action == "medidas":
            unit = request.POST.get("unit", "cm")
            draft["unit"] = unit
            converted = {}
            for field in ("chest", "neck", "back"):
                raw = request.POST.get(field, "").strip()
                draft[field] = raw
                if raw:
                    try:
                        converted[field] = services_fit.to_cm(raw, unit)
                    except services_fit.InvalidMeasurement as exc:
                        errors[field] = str(exc)
            if not errors:
                profile = _draft_profile(request, store, draft)
                # Reiniciar SIEMPRE la medida del intento: «no tengo las
                # medidas» nunca arrastra silenciosamente un borrador viejo.
                draft["converted"] = {}
                draft["measurement_saved"] = False
                if any(converted.values()):
                    if profile and request.POST.get("remember") == "1":
                        # Guardar medidas requiere consentimiento explícito.
                        services_memory.grant_consent(
                            store, session_key, Consent.Purpose.MEASUREMENTS, profile)
                        services_memory.save_measurement(
                            profile, chest_cm=converted.get("chest"),
                            neck_cm=converted.get("neck"), back_cm=converted.get("back"),
                            original={"chest": draft.get("chest"), "neck": draft.get("neck"),
                                      "back": draft.get("back"), "unit": unit},
                            source="looklab",
                        )
                        draft["measurement_saved"] = True
                    # Medidas de esta visita (con o sin perfil): precedencia
                    # sobre cualquier dato guardado (R09).
                    draft["converted"] = {k: str(v) for k, v in converted.items()}
                draft["step"] = "personalidad"
                tenancy.set_looklab_draft(request, store, draft)
                return redirect(f"{request.path}?paso=personalidad")

        elif action == "personalidad":
            style = request.POST.get("style", "")
            if style not in {s[0] for s in STYLES}:
                errors["style"] = "Elegí una de las cuatro opciones."
            else:
                draft["style"] = style
                draft["step"] = "ocasion"
                tenancy.set_looklab_draft(request, store, draft)
                return redirect(f"{request.path}?paso=ocasion")

        elif action == "ocasion":
            occasion = request.POST.get("occasion", "")
            if occasion not in dict(OCCASIONS):
                errors["occasion"] = "Elegí una ocasión."
            budget_raw = request.POST.get("budget", "").strip()
            budget = None
            if budget_raw:
                try:
                    budget = Decimal(budget_raw)
                    if budget <= 0 or budget > Decimal("100000"):
                        raise InvalidOperation
                except InvalidOperation:
                    errors["budget"] = "Ingresá un presupuesto válido (opcional)."
            if not errors:
                draft["occasion"] = occasion
                draft["budget"] = str(budget) if budget else None
                draft["budget_scope"] = request.POST.get("budget_scope", "products")
                draft["step"] = "revelacion"
                tenancy.set_looklab_draft(request, store, draft)
                return redirect(f"{request.path}?paso=revelacion")

    # ---- render por paso ------------------------------------------------
    profile = _draft_profile(request, store, draft)
    context = {
        "step": step, "step_index": STEPS.index(step) + 1, "total_steps": 4,
        "draft": draft, "profile": profile, "errors": errors,
        "profiles": services_memory.list_profiles(store, session_key),
        "styles": STYLES, "occasions": OCCASIONS,
        "measurement": services_memory.latest_measurement(profile) if profile else None,
    }

    if step == "revelacion":
        context.update(_reveal(request, store, draft, profile))
    return render(request, "reino/looklab.html", context)


def _draft_profile(request, store, draft):
    pid = draft.get("profile_id")
    if not pid:
        return None
    return services_memory.get_profile(store, request.session.session_key, pid)


class _DraftMeasurement:
    """Medidas temporales del borrador (sin consentimiento de guardado)."""

    def __init__(self, converted):
        from decimal import Decimal as D
        self.chest_cm = D(converted["chest"]) if converted.get("chest") else None
        self.neck_cm = D(converted["neck"]) if converted.get("neck") else None
        self.back_cm = D(converted["back"]) if converted.get("back") else None


def _resolve_measurement(request, store, draft, profile):
    """Precedencia explícita de medidas (R09):

    1. Las introducidas para ESTE intento (borrador convertido), siempre.
    2. Después, las persistentes vigentes y AUTORIZADAS (consentimiento).
    3. Finalmente, datos insuficientes (talla honestamente pendiente).
    """
    if draft.get("converted") and any(draft["converted"].values()):
        return _DraftMeasurement(draft["converted"]), "esta_visita"
    if profile is not None:
        saved = services_memory.authorized_measurement(store, profile.session_key, profile)
        if saved is not None:
            return saved, "guardadas"
    return None, "sin_datos"


def _pick_variant(product, measurement, needs_fit):
    """Unidad comprable real: producto + variante + regla de talla + precio (R08).

    Devuelve (variante|None, fit, variantes_para_elegir, agotada_tu_talla).
    NUNCA sustituye la talla compatible por otra: si la talla de la persona
    está agotada, la pieza no se ofrece como compatible.
    """
    rows, fit = variants_with_fit(product, measurement)
    in_stock = [r for r in rows if r["variant"].stock > 0]
    if not needs_fit:
        chosen = in_stock[0]["variant"] if in_stock else None
        return chosen, fit, rows, False
    if fit is None or fit["state"] == "sin_datos":
        # Sin medidas: la talla queda pendiente; la elección es explícita.
        fit = fit or {"state": "sin_datos", "label": "Talla por confirmar",
                      "candidates": [], "explanation": ""}
        return None, fit, rows, False
    suggested = [r for r in rows if r["fit_hint"] == "sugerida"]
    available_suggested = [r for r in suggested if r["variant"].stock > 0]
    if available_suggested:
        return available_suggested[0]["variant"], fit, rows, False
    if suggested:
        # La talla compatible existe pero está agotada: NO ofrecer otra (R08).
        return None, fit, rows, True
    # Sin candidatas (incompatible): la pieza no aplica para estas medidas.
    return None, fit, rows, False


def _reveal(request, store, draft, profile):
    """Calcula la revelación: UNA pieza principal + complementos coherentes.

    - Precedencia de medidas de esta visita sobre las guardadas (R09).
    - Talla por variante exacta; nunca sustitución silenciosa (R08).
    - Presupuesto del conjunto acumulado y estricto (R10).
    """
    measurement, measurement_origin = _resolve_measurement(request, store, draft, profile)
    if measurement and not any([measurement.chest_cm, measurement.neck_cm, measurement.back_cm]):
        measurement, measurement_origin = None, "sin_datos"

    needs_fit = store.category == "moda canina"
    budget = Decimal(draft["budget"]) if draft.get("budget") else None
    budget_scope = draft.get("budget_scope", "products")
    intent = normalize_intent(
        occasion=draft.get("occasion", ""), style=draft.get("style", ""),
        budget=draft.get("budget"), budget_scope=budget_scope,
        profile=profile, needs_fit=needs_fit,
    )
    result = recommend(store, intent, measurement=measurement, kind="looklab")

    selection, unavailable, excluded = [], [], list(result["excluded"])
    total = Decimal("0")
    total_budget = budget if (budget is not None and budget_scope in
                              ("total", "conjunto", "pedido")) else None

    for entry in result["selection"]:
        product = entry["product"]
        chosen, fit, rows, size_sold_out = _pick_variant(product, measurement, needs_fit)
        if size_sold_out:
            unavailable.append({
                "product": product, "fit": fit,
                "note": "Tu talla está agotada en esta pieza.",
            })
            continue
        if chosen is None and not (needs_fit and fit["state"] == "sin_datos"):
            continue  # sin unidad comprable y con talla conocida: no entra
        # Precio de la unidad REALMENTE seleccionada (variante); si la talla
        # está pendiente, el precio de referencia honesto es el base.
        unit_price = chosen.price if chosen else product.base_price
        if total_budget is not None and total + unit_price > total_budget:
            excluded.append({"product": product.short_title, "reason": "OVER_BUDGET_TOTAL"})
            continue  # menos piezas, jamás inventar que el presupuesto alcanzó (R10)
        selection.append({
            "product": product, "variant": chosen, "score": entry["score"],
            "reasons": entry["reasons"], "fit": fit,
            "size_pending": chosen is None,
            "selectable_variants": [r["variant"] for r in rows if r["variant"].stock > 0],
            "unit_price": unit_price,
        })
        total += unit_price

    # Conjunto coherente (§6.6 / §7.3): UNA pieza principal; las demás
    # candidatas son ALTERNATIVAS (opciones de look), nunca se suman. Los
    # complementos son de función distinta, opcionales y dentro del
    # presupuesto restante.
    main = selection[0] if selection else None
    alternatives = selection[1:] if len(selection) > 1 else []
    complements = []
    if main is not None:
        remaining = (total_budget - main["unit_price"]) if total_budget is not None else None
        bundle, _ = compose_bundle(store, main["product"], measurement=measurement,
                                   budget=remaining, max_extras=2)
        selected_ids = {e["product"].pk for e in selection}
        comp_total = main["unit_price"]
        for item in bundle:
            if item["role"] != "complemento" or item["product"].pk in selected_ids:
                continue
            c_variant, c_fit, c_rows, c_sold_out = _pick_variant(
                item["product"], measurement, needs_fit)
            if c_sold_out:
                continue
            c_price = c_variant.price if c_variant else item["product"].base_price
            if total_budget is not None and comp_total + c_price > total_budget:
                continue  # presupuesto acumulado también en complementos (R10)
            complements.append({
                "product": item["product"], "variant": c_variant, "fit": c_fit,
                "size_pending": c_variant is None,
                "selectable_variants": [r["variant"] for r in c_rows if r["variant"].stock > 0],
                "unit_price": c_price,
            })
            comp_total += c_price

    return {
        "selection": selection,          # compatibilidad con pruebas (matriz A)
        "main": main, "alternatives": alternatives, "complements": complements,
        "unavailable": unavailable, "excluded": excluded,
        "engine_version": result["engine_version"], "selection_total": total,
        "budget": budget, "budget_scope": budget_scope,
        "measurement_origin": measurement_origin,
        "alias": profile.alias if profile else "",
    }


@_store_view
@require_POST
def looklab_add(request, store):
    """Agrega la selección elegida al carrito (una operación, clave idempotente).

    El cliente elige qué piezas incorporar; nunca se premarcan extras.
    """
    from . import services_commerce as commerce

    variant_ids = request.POST.getlist("variant")
    if not variant_ids:
        return redirect("reino_looklab", slug=store.slug)
    cart = commerce.get_open_cart(store, request.session.session_key, create=True)
    errors = []
    profile_id = tenancy.active_profile_id(request, store)
    recipient = services_memory.get_profile(store, request.session.session_key, profile_id) if profile_id else None
    for vid in variant_ids:
        variant = Variant.objects.filter(
            public_id=vid, product__store=store, is_active=True, stock__gt=0
        ).first()
        if variant is None:
            errors.append("Una pieza ya no está disponible.")
            continue
        try:
            commerce.add_item(cart, variant, 1, recipient=recipient)
        except (commerce.CartError, commerce.StockConflict) as exc:
            errors.append(str(exc))
    if errors:
        request.session["reino_cart_error"] = " ".join(errors)
    return redirect("reino_cart", slug=store.slug)


@_store_view
@require_POST
def looklab_save(request, store):
    """Guarda el look (no reserva precio ni stock) con consentimiento separado."""
    from .models import Look

    draft = tenancy.looklab_draft(request, store)
    profile = _draft_profile(request, store, draft)
    items = []
    for vid in request.POST.getlist("variant"):
        v = Variant.objects.filter(public_id=vid, product__store=store).first()
        if v:
            items.append({"variant_id": str(v.public_id), "title": v.product.short_title,
                          "option": v.option_label, "price": str(v.price)})
    if items:
        Look.objects.create(
            store=store, session_key=request.session.session_key, profile=profile,
            occasion=draft.get("occasion", ""), style=draft.get("style", ""),
            budget=Decimal(draft["budget"]) if draft.get("budget") else None,
            items=items,
        )
        request.session["reino_flash"] = "Look guardado en tu cuenta."
    return redirect("reino_looklab", slug=store.slug)
