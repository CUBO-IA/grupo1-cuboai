"""Smart Quote: cotización calculada siempre en el servidor.

El cliente solo indica qué perro y qué producto; el precio se toma del
catálogo controlado (`tienda.views.PRODUCTOS`) y nunca de datos del navegador.

La regla de ajuste por talla/peso/materiales NO está definida por el negocio,
así que toda cotización es PROVISIONAL (precio base, sin ajuste).
"""

from decimal import Decimal, InvalidOperation

from .models import Quote
from .views import PRODUCTOS


class UnknownProduct(Exception):
    pass


class InvalidCatalogPrice(Exception):
    pass


def get_product(slug):
    try:
        return PRODUCTOS[slug]
    except KeyError:
        raise UnknownProduct(slug) from None


def get_base_price(slug):
    """Precio base como Decimal, a partir del catálogo (p. ej. "$650")."""
    raw = get_product(slug)["precio"]
    try:
        price = Decimal(str(raw).strip().lstrip("$").replace(",", ""))
    except InvalidOperation:
        raise InvalidCatalogPrice(raw) from None
    if price <= 0:
        raise InvalidCatalogPrice(raw)
    return price.quantize(Decimal("0.01"))


def create_quote(dog, slug):
    """Crea (o reutiliza) la cotización provisional borrador de un perro/producto."""
    base_price = get_base_price(slug)
    existing = (
        Quote.objects.filter(
            dog=dog,
            product_slug=slug,
            status=Quote.Status.DRAFT,
            pricing=Quote.Pricing.PROVISIONAL,
        )
        .order_by("-pk")
        .first()
    )
    if existing:
        # Si el catálogo cambió, el precio del borrador se refresca.
        if existing.base_price != base_price:
            existing.base_price = base_price
            existing.save(update_fields=["base_price"])
        return existing
    return Quote.objects.create(dog=dog, product_slug=slug, base_price=base_price)


def build_breakdown(quote):
    """Desglose legible; el total mostrado es provisional mientras no haya regla."""
    lines = [
        {
            "label": f"{get_product(quote.product_slug)['nombre']} — base price",
            "amount": quote.base_price,
            "note": "",
        },
        {
            "label": "Size adjustment",
            "amount": None,
            "note": "Not calculated yet. The sizing rule is pending business approval.",
        },
    ]
    is_final = quote.pricing == Quote.Pricing.FINAL and quote.total_price is not None
    return {
        "lines": lines,
        "total": quote.total_price if is_final else quote.base_price,
        "is_final": is_final,
    }
