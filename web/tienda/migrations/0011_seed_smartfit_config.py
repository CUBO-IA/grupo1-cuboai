"""Configuración inicial de Smart Fit.

- Tabla de tallas de referencia: tomada de la imagen de la guía maestra
  (medidas en cm; 3 grupos de perros). NO está validada con confección.
- Requisitos de medidas por prenda: el cuello no se exige a ninguna hasta que
  confección lo defina. Ambos son editables desde el panel.
"""

from decimal import Decimal as D

from django.db import migrations

PRODUCTS = ["wedding-dog", "tactical-dog", "christmas-dog", "dog-sweater"]

# (grupo, talla, cuello min-max, pecho min-max, largo de espalda min-max)
SIZES = [
    ("small", "XS", (18, 23), (28, 34), (20, 26)),
    ("small", "S", (22, 27), (33, 40), (25, 32)),
    ("small", "M", (26, 31), (39, 46), (31, 38)),
    ("medium", "M", (30, 36), (45, 53), (35, 42)),
    ("medium", "L", (35, 41), (52, 61), (41, 49)),
    ("medium", "XL", (40, 46), (60, 70), (48, 56)),
    ("large", "XL", (42, 49), (65, 77), (53, 62)),
    ("large", "XXL", (48, 55), (76, 89), (61, 70)),
    ("large", "XXXL", (54, 62), (88, 103), (69, 80)),
]


def seed(apps, schema_editor):
    ProductMeasurement = apps.get_model("tienda", "ProductMeasurement")
    SizeRange = apps.get_model("tienda", "SizeRange")
    for slug in PRODUCTS:
        ProductMeasurement.objects.get_or_create(
            product_slug=slug,
            defaults={
                "requires_neck": False,
                "is_validated": False,
                "notes": "Pending validation with tailoring.",
            },
        )
    if SizeRange.objects.exists():
        return  # no pisar una tabla ya editada
    for pos, (group, label, neck, chest, back) in enumerate(SIZES, 1):
        SizeRange.objects.create(
            group=group,
            label=label,
            position=pos,
            neck_min=D(neck[0]),
            neck_max=D(neck[1]),
            chest_min=D(chest[0]),
            chest_max=D(chest[1]),
            back_min=D(back[0]),
            back_max=D(back[1]),
            is_validated=False,
        )


def unseed(apps, schema_editor):
    apps.get_model("tienda", "SizeRange").objects.all().delete()
    apps.get_model("tienda", "ProductMeasurement").objects.filter(
        product_slug__in=PRODUCTS
    ).delete()


class Migration(migrations.Migration):

    dependencies = [("tienda", "0010_smartfit_config")]

    operations = [migrations.RunPython(seed, unseed)]
