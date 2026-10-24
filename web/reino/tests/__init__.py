"""Pruebas de aceptación Reino Commerce (matriz §23).

Cada test referencia su ID de la matriz (A03, A04…). Las de dinero,
inventario, identidad, permisos, memoria y exactitud de catálogo bloquean
aprobación; se ejecutan con `python manage.py test reino`.
"""

from decimal import Decimal

from django.test import TestCase

from reino.models import (
    FitRule, Merchant, Product, ProductMedia, RecipientProfile, ShippingZone,
    Store, Variant,
)

DOG_SIZES = [
    {"label": "XS", "neck_min": 18, "neck_max": 23, "chest_min": 28, "chest_max": 34, "back_min": 20, "back_max": 26},
    {"label": "S", "neck_min": 22, "neck_max": 27, "chest_min": 33, "chest_max": 40, "back_min": 25, "back_max": 32},
    {"label": "M", "neck_min": 26, "neck_max": 31, "chest_min": 39, "chest_max": 46, "back_min": 31, "back_max": 38},
]


class ReinoTestCase(TestCase):
    """Base: dos tiendas aisladas con catálogos mínimos reales de prueba."""

    @classmethod
    def setUpTestData(cls):
        cls.merchant_a = Merchant.objects.create(name="WK Test", status="pilot")
        cls.store_a = Store.objects.create(
            merchant=cls.merchant_a, slug="wk-test", name="Wiener Kingdom",
            category="moda canina", status="active", currency="USD",
        )
        cls.merchant_b = Merchant.objects.create(name="Nube Test", status="pilot")
        cls.store_b = Store.objects.create(
            merchant=cls.merchant_b, slug="nube-test", name="Estudio Nube",
            category="papeleria", status="demo", is_demo=True, currency="USD",
        )
        cls.product = cls._make_product(cls.store_a, "arnes-real", "Arnés Real", "63.00",
                                        occasions=["paseo", "diario"], styles=["urban-king"],
                                        stock={"S": 2, "M": 5, "XS": 0}, fit=True)
        cls.product2 = cls._make_product(cls.store_a, "traje-gala", "Traje Gala", "650.00",
                                         occasions=["celebracion", "fotos"], styles=["party-royalty"],
                                         stock={"M": 3}, fit=True)
        cls.product_b = cls._make_product(cls.store_b, "arnes-real", "Cuaderno Nube", "12.00",
                                          occasions=["diario"], stock={"Único": 9}, fit=False)
        ShippingZone.objects.create(store=cls.store_a, name="Retiro", mode="pickup", fee=0)
        ShippingZone.objects.create(store=cls.store_a, name="Centro (demo)", mode="local",
                                    fee=Decimal("3.50"))

    @staticmethod
    def _make_product(store, slug, title, price, occasions=None, styles=None, stock=None, fit=False):
        p = Product.objects.create(
            store=store, slug=slug, title=title, short_title=title,
            base_price=Decimal(price), status="published",
            occasions=occasions or [], styles=styles or [], reason="Razón verificable de prueba",
        )
        for option, units in (stock or {"Único": 5}).items():
            Variant.objects.create(product=p, sku=f"{slug[:8].upper()}-{option}",
                                   option_label=f"Talla {option}" if fit else option, stock=units)
        if fit:
            FitRule.objects.create(product=p, version=1, ranges=DOG_SIZES, approved_by="test")
        ProductMedia.objects.create(product=p, path="reino/img/placeholder.svg", alt=title)
        return p

    def _profile(self, store, session="sesion-test", alias="Bruno"):
        return RecipientProfile.objects.create(store=store, session_key=session, alias=alias)
