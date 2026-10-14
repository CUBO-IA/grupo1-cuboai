"""Elegibilidad del descuento Bitcoin según el listado comercial aportado.

El listado muestra "Sale price with BTC payments" solo para el Luxury Cable
Knit Jumper y el Showercover Bamboo Drying Robe; el resto figura a precio
regular. Por eso solo esos dos productos quedan elegibles. El resto sigue sin
descuento. La regla del 15 % la calcula el backend; los precios de referencia
del listado ($110 y $76) no coinciden con el 15 % y están documentados como
pendientes de confirmar.
"""

from django.db import migrations

ELIGIBLE = ["cable-knit-jumper", "bamboo-drying-robe"]


def apply(apps, schema_editor):
    Rule = apps.get_model("tienda", "ProductPaymentRule")
    for slug in ELIGIBLE:
        rule, _ = Rule.objects.get_or_create(product_slug=slug)
        if not rule.bitcoin_discount_eligible:
            rule.bitcoin_discount_eligible = True
            rule.save(update_fields=["bitcoin_discount_eligible"])


class Migration(migrations.Migration):

    dependencies = [("tienda", "0016_catalog_v2_seed")]

    operations = [migrations.RunPython(apply, migrations.RunPython.noop)]
