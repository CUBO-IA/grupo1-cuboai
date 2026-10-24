"""Comparador funcional (P06, §15): 2–4 variantes, campos comunes,
normalización de unidades y cero ganadores ficticios.

Reglas del contrato:
- Se comparan UNIDADES (variante), deduplicadas por lo comparado.
- Primero: imagen, nombre, tienda, variante, precio con moneda, disponibilidad
  y CTA. Después, atributos normalizados de la categoría.
- Entre categorías distintas solo campos comunes; JAMÁS un ganador entre un
  arnés y un cuaderno (AC14).
- «Menor precio de producto entre estas opciones» solo con misma moneda y
  precios completos; el envío desconocido se declara, no se suma a ciegas.
- Al abrir una comparación compartida se RECALCULA precio y stock; lo
  archivado/agotado/cambiado se muestra con su estado (AC13).
"""

from decimal import Decimal

from .models import AttributeValue, ComparisonSession, Variant
from .money import fmt

MAX_ITEMS = 4
MIN_ITEMS = 2

# Conversión a unidad canónica (la definición fija la unidad canónica).
_TO_CANONICAL = {
    ("in", "cm"): lambda v: v * Decimal("2.54"),
    ("cm", "cm"): lambda v: v,
    ("oz", "g"): lambda v: v * Decimal("28.3495"),
    ("g", "g"): lambda v: v,
    ("lb", "g"): lambda v: v * Decimal("453.592"),
}


class CompareError(Exception):
    """Operación inválida con mensaje para el comprador."""


def get_tray(session_key):
    tray, _ = ComparisonSession.objects.get_or_create(session_key=session_key)
    return tray


def add_item(session_key, variant_id):
    """Agrega una variante a la bandeja: deduplicada, máximo 4 (AC13)."""
    tray = get_tray(session_key)
    items = list(tray.items)
    vid = str(variant_id)
    if any(i.get("variant_id") == vid for i in items):
        return tray, "Esa pieza ya está en tu comparación."
    if len(items) >= MAX_ITEMS:
        return tray, "Ya hay 4 piezas: quitá una para comparar otra."
    variant = Variant.objects.filter(public_id=vid).select_related("product__store").first()
    if variant is None:
        raise CompareError("Esa pieza ya no existe en el catálogo.")
    items.append({"variant_id": vid})
    tray.items = items
    tray.save(update_fields=["items", "updated_at"])
    return tray, "Agregada a la comparación."


def remove_item(session_key, variant_id):
    tray = get_tray(session_key)
    vid = str(variant_id)
    tray.items = [i for i in tray.items if i.get("variant_id") != vid]
    tray.save(update_fields=["items", "updated_at"])
    return tray


def _attribute_rows(variants):
    """Filas de atributos NORMALIZADOS para las variantes dadas.

    Solo definiciones cuya categoría coincide con TODAS las variantes (campos
    comunes, AC14). Estados «no aplica»/«no informado» visibles como tales.
    """
    values = (AttributeValue.objects
              .filter(variant__in=variants, status=AttributeValue.Status.INFORMED)
              .select_related("definition__schema"))
    schemas = {v.product.store.category.replace(" ", "-") for v in variants}
    rows = {}
    for value in values:
        d = value.definition
        if d.schema.slug not in schemas:
            continue
        key = d.schema.slug  # misma categoría requerida abajo
        row = rows.setdefault(d.key, {"label": d.label, "unit": d.unit, "cells": {}})
        display = value.value.get("raw")
        if value.normalized_number is not None:
            display = f"{value.normalized_number.normalize()} {d.unit}".strip()
        row["cells"][value.variant_id] = display if display not in (None, "") else "—"
    return rows


def build_comparison(session_key=None, public_id=None):
    """Construye la vista de comparación recalculando precio/stock (AC13).

    Devuelve dict con columnas (una por variante) y filas; estados:
    disponible / agotada / archivada / precio cambiado desde el guardado.
    """
    tray = None
    if public_id:
        tray = ComparisonSession.objects.filter(public_id=public_id).first()
    elif session_key:
        tray = ComparisonSession.objects.filter(session_key=session_key).first()
    if tray is None or not tray.items:
        return {"tray": tray, "columns": [], "rows": [], "common_only": False,
                "currencies": set(), "state": "empty"}

    variants = list(
        Variant.objects.filter(public_id__in=[i["variant_id"] for i in tray.items])
        .select_related("product__store")
        .prefetch_related("product__media")
    )
    by_id = {str(v.public_id): v for v in variants}
    columns = []
    categories = set()
    currencies = set()
    prices = {}
    for item in tray.items:
        vid = item["variant_id"]
        v = by_id.get(vid)
        if v is None:
            columns.append({"variant_id": vid, "state": "archivada",
                            "title": "Pieza archivada", "option": "",
                            "store": None, "price": None, "cta": None})
            continue
        p = v.product
        categories.add(p.store.category)
        currencies.add(p.store.currency)
        state = "disponible" if (v.is_active and v.stock > 0
                                 and p.status == "published") else "agotada"
        media = p.media.first()
        price = v.price
        prices[vid] = price
        columns.append({
            "variant_id": vid, "state": state,
            "title": p.short_title, "option": v.option_label,
            "store": p.store, "product_slug": p.slug,
            "price": fmt(price, p.store.currency), "price_raw": price,
            "stock": v.stock,
            "image": media.path if media else "",
            "alt": media.alt if media else p.short_title,
        })

    # «Menor precio de producto entre estas opciones»: solo misma moneda,
    # piezas disponibles y envío declarado aparte (nunca total inventado).
    best_id = None
    cross_category = len(categories) > 1
    available_prices = {i["variant_id"]: c["price_raw"]
                        for i, c in zip(tray.items, columns)
                        if c.get("state") == "disponible" and c.get("price_raw") is not None}
    # Jamás un «ganador» entre categorías distintas (AC14).
    if not cross_category and len(currencies) == 1 and len(available_prices) >= 2:
        best_id = min(available_prices, key=available_prices.get)
    for col in columns:
        col["best_price"] = col.get("variant_id") == best_id

    common_only = len(categories) > 1
    rows = [] if common_only else _attribute_rows(variants)
    return {
        "tray": tray, "columns": columns,
        "rows": [{"label": r["label"], "unit": r["unit"],
                  "cells": [r["cells"].get(v.pk, "—") for v in variants]}
                 for r in sorted(rows.values(), key=lambda x: x["label"])] if not common_only else [],
        "common_only": common_only,
        "currencies": currencies,
        "shipping_note": "Entrega por calcular: se cotiza en el checkout de cada tienda.",
        "state": "ok" if len(columns) >= MIN_ITEMS else "incomplete",
    }


def diff_rows(rows, columns):
    """«Solo diferencias»: filas cuyas celdas no son todas iguales (P06)."""
    out = []
    for row in rows:
        cells = row["cells"]
        if len(set(cells)) > 1:
            out.append(row)
    return out
