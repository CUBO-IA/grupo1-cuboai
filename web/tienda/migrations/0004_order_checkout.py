import uuid

from django.db import migrations, models


def fill_order_public_ids(apps, schema_editor):
    Order = apps.get_model("tienda", "Order")
    for obj in Order.objects.all():
        obj.public_id = uuid.uuid4()
        obj.save(update_fields=["public_id"])


def char(name, max_length):
    # default="" solo rellena filas previas (no debería haber pedidos).
    return migrations.AddField(
        model_name="order",
        name=name,
        field=models.CharField(max_length=max_length, default=""),
        preserve_default=False,
    )


def choice(name, choices, default):
    return migrations.AddField(
        model_name="order",
        name=name,
        field=models.CharField(choices=choices, default=default, max_length=20),
    )


class Migration(migrations.Migration):

    dependencies = [("tienda", "0003_public_ids")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="public_id",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(fill_order_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
        migrations.AddField(
            model_name="order",
            name="price_is_provisional",
            field=models.BooleanField(default=True),
        ),
        char("customer_name", 120),
        migrations.AddField(
            model_name="order",
            name="customer_email",
            field=models.EmailField(max_length=254, default=""),
            preserve_default=False,
        ),
        char("customer_phone", 30),
        char("country", 80),
        char("city", 80),
        migrations.AddField(
            model_name="order",
            name="address",
            field=models.TextField(max_length=300, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="snapshot",
            field=models.JSONField(default=dict),
        ),
        choice(
            "payment_status",
            [("unpaid", "Unpaid"), ("paid", "Paid")],
            "unpaid",
        ),
        choice(
            "production_status",
            [
                ("not_started", "Not started"),
                ("in_production", "In production"),
                ("completed", "Completed"),
            ],
            "not_started",
        ),
        choice(
            "shipping_status",
            [
                ("not_shipped", "Not shipped"),
                ("shipped", "Shipped"),
                ("delivered", "Delivered"),
            ],
            "not_shipped",
        ),
    ]
