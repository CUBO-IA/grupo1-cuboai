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


class QuoteNotOrderable(Exception):
    pass


def _dec(value):
    return None if value is None else str(value)


def create_order(quote, customer):
    """Crea el pedido de una cotización; idempotente por cotización.

    El total se recalcula aquí desde el catálogo; nada del navegador influye.
    Si la cotización ya tiene pedido, devuelve (pedido_existente, False).
    """
    from django.db import IntegrityError, transaction

    from .models import Order

    with transaction.atomic():
        quote = Quote.objects.select_for_update().select_related("dog").get(pk=quote.pk)
        existing = Order.objects.filter(quote=quote).first()
        if existing:
            return existing, False
        if quote.status == Quote.Status.CANCELLED:
            raise QuoteNotOrderable("cancelled")

        base_price = get_base_price(quote.product_slug)
        is_final = quote.pricing == Quote.Pricing.FINAL and quote.total_price is not None
        total = quote.total_price if is_final else base_price
        product = get_product(quote.product_slug)
        dog = quote.dog
        snapshot = {
            "currency": "USD",
            "product": {"slug": quote.product_slug, "name": product["nombre"]},
            "base_price": _dec(base_price),
            "total": _dec(total),
            "pricing": "final" if is_final else "provisional",
            "dog": {
                "name": dog.name,
                "breed": dog.breed,
                "weight_kg": _dec(dog.weight_kg),
                "back_length_cm": _dec(dog.back_length_cm),
                "chest_girth_cm": _dec(dog.chest_girth_cm),
                "neck_girth_cm": _dec(dog.neck_girth_cm),
            },
            "quote_public_id": str(quote.public_id),
        }
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    quote=quote,
                    total=total,
                    price_is_provisional=not is_final,
                    snapshot=snapshot,
                    **customer,
                )
        except IntegrityError:
            return Order.objects.get(quote=quote), False
        quote.base_price = base_price
        quote.status = Quote.Status.ACCEPTED
        quote.save(update_fields=["base_price", "status"])
        return order, True
