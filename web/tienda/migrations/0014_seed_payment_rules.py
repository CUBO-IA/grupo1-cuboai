from django.db import migrations

PRODUCTS = ["wedding-dog", "tactical-dog", "christmas-dog", "dog-sweater"]


def seed(apps, schema_editor):
    Rule = apps.get_model("tienda", "ProductPaymentRule")
    for slug in PRODUCTS:
        # El descuento Bitcoin del 15 % aplica a los 4 productos del catálogo.
        Rule.objects.get_or_create(
            product_slug=slug, defaults={"bitcoin_discount_eligible": True}
        )


class Migration(migrations.Migration):

    dependencies = [("tienda", "0013_payment_rules")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
