"""Dinero: una sola política de redondeo por moneda (USD P0).

Regla: Decimal, ROUND_HALF_UP a centavos. Nunca se suman monedas distintas;
el envío y los impuestos se registran aparte del valor de mercancía.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
BITCOIN_DISCOUNT_RATE = Decimal("0.15")  # promoción histórica preservada (15 %)


def money(value):
    """Normaliza un importe a centavos con la política única de redondeo."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(value, currency="USD"):
    """Formato de presentación consistente en toda la plataforma."""
    symbol = {"USD": "$"}.get(currency, f"{currency} ")
    return f"{symbol}{money(value):,.2f}"
