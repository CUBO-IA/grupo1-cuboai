"""Política de visibilidad CENTRALIZADA (F06, §5 ámbitos de datos).

Regla pública del mercado: un producto es visible/comprable sólo si
- su negocio (Merchant) está en piloto o activo (nunca borrador/suspendido),
- su tienda (Store) está activa o en demo explícita (nunca borrador),
- el producto está publicado y la variante activa.

TODA lectura pública pasa por aquí: búsqueda, IA, comparador, feeds,
sitemap, recomendaciones y acceso directo. Filtrar una sola vista no basta.
"""

from .models import Merchant, Product, Store, Variant

_STORE_PUBLIC = (Store.Status.ACTIVE, Store.Status.DEMO)
_MERCHANT_PUBLIC = (Merchant.Status.PILOT, Merchant.Status.ACTIVE)


def visible_stores(include_demo=True):
    """Tiendas visibles públicamente; demo siempre identificada y separable."""
    qs = Store.objects.filter(status__in=_STORE_PUBLIC,
                              merchant__status__in=_MERCHANT_PUBLIC)
    if not include_demo:
        qs = qs.exclude(is_demo=True)
    return qs


def visible_products(store=None, include_demo=True):
    """Productos publicados de tiendas/negocios visibles (ámbito público)."""
    qs = Product.objects.filter(
        status=Product.Status.PUBLISHED,
        store__status__in=_STORE_PUBLIC,
        store__merchant__status__in=_MERCHANT_PUBLIC,
    )
    if not include_demo:
        qs = qs.exclude(store__is_demo=True)
    if store is not None:
        qs = qs.filter(store=store)
    return qs


def visible_variants(store=None, include_demo=True):
    return Variant.objects.filter(
        is_active=True,
        product__in=visible_products(store=store, include_demo=include_demo),
    )


def is_store_public(store):
    return (store.status in _STORE_PUBLIC
            and store.merchant.status in _MERCHANT_PUBLIC)


def public_store_or_none(slug):
    """Acceso directo por slug: sólo si la tienda es pública (F06)."""
    store = Store.objects.filter(slug=slug).select_related("merchant").first()
    if store is None or not is_store_public(store):
        return None
    return store


def is_variant_buyable(variant):
    p = variant.product
    return (variant.is_active and p.status == Product.Status.PUBLISHED
            and is_store_public(p.store))
