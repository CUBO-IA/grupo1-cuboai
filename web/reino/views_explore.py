"""Descubrimiento, búsqueda y comparación de Reino (P01, P04, P06).

Rutas de plataforma nuevas; las históricas quedan intactas. Todo funciona
sin clave de IA: reglas, filtros visibles y estado compartible por URL.
"""

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services_analytics, services_compare, services_search
from .models import Variant


def _session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def explore(request):
    """P01 · Explorar Reino: descubrimiento del catálogo disponible."""
    data = services_search.explore_home()
    return render(request, "reino/explorar.html", {
        **data,
        "examples": ["algo para paseo", "regalo por menos de $30", "para celebración"],
    })


def search(request):
    """P04 · Búsqueda universal del catálogo disponible (reglas, sin IA)."""
    q = request.GET.get("q", "").strip()
    occasion = request.GET.get("ocasion", "")
    max_price = request.GET.get("max", "").strip()
    category = request.GET.get("categoria", "")
    from decimal import Decimal, InvalidOperation
    try:
        max_price = Decimal(max_price) if max_price else None
    except InvalidOperation:
        max_price = None
    results = services_search.search_catalog(
        q, occasion=occasion, max_price=max_price, category=category) if q or occasion or max_price else []
    return render(request, "reino/buscar.html", {
        "q": q, "occasion": occasion, "max_price": max_price or "",
        "category": category, "results": results,
        "searched": bool(q or occasion or max_price),
        "examples": ["algo para paseo", "regalo por menos de $30", "para celebración"],
    })


def compare(request):
    """P06 · Comparador: 2–4 variantes, solo diferencias, compartir."""
    key = _session_key(request)
    public_id = request.GET.get("c")  # comparación compartida (IDs no sensibles)
    data = services_compare.build_comparison(
        session_key=None if public_id else key, public_id=public_id)
    rows = data["rows"]
    if request.GET.get("vista") == "diferencias":
        rows = services_compare.diff_rows(rows, data["columns"])
    if data["columns"]:
        services_analytics.track("compare_opened", session_key=key,
                                 items=len(data["columns"]))
    return render(request, "reino/comparar.html", {
        **data, "rows": rows, "vista": request.GET.get("vista", "todos"),
        "shared": bool(public_id),
    })


@require_POST
def compare_add(request):
    key = _session_key(request)
    variant_id = request.POST.get("variant_id", "")
    try:
        tray, message = services_compare.add_item(key, variant_id)
        request.session["reino_flash"] = message
        services_analytics.track("compare_selected", session_key=key,
                                 variant_id=variant_id)
    except services_compare.CompareError as exc:
        request.session["reino_flash"] = str(exc)
    return redirect(request.POST.get("next") or "reino_compare")


@require_POST
def compare_remove(request):
    key = _session_key(request)
    services_compare.remove_item(key, request.POST.get("variant_id", ""))
    return redirect(request.POST.get("next") or "reino_compare")
