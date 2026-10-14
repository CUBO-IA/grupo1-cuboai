"""Crea una línea de pedido para cada pedido existente (anterior al carrito),
a partir de su snapshot."""

from decimal import Decimal

from django.db import migrations


def backfill(apps, schema_editor):
    Order = apps.get_model("tienda", "Order")
    OrderLine = apps.get_model("tienda", "OrderLine")
    for order in Order.objects.all():
        if OrderLine.objects.filter(order=order).exists():
            continue
        snap = order.snapshot or {}
        product = snap.get("product") or {}
        quantity = order.quantity or 1
        try:
            unit = Decimal(str(snap.get("unit_price")))
        except Exception:
            unit = (order.total / quantity).quantize(Decimal("0.01"))
        OrderLine.objects.create(
            order=order,
            quote=order.quote,
            position=1,
            product_slug=product.get("slug", ""),
            product_name=product.get("name", ""),
            quantity=quantity,
            unit_price=unit,
            subtotal=order.total,
            price_is_provisional=order.price_is_provisional,
            discount_eligible=bool(order.discount_rate),
            discount_amount=order.discount_amount,
            size_selected="",
            size_confirmed=order.size_confirmed or "",
            dog_snapshot=snap.get("dog") or {},
            size_reference=snap.get("size_reference") or {},
            required_measurements=snap.get("required_measurements") or {},
            cost_estimate=snap.get("cost_estimate"),
            production_status=order.production_status,
        )


class Migration(migrations.Migration):

    dependencies = [("tienda", "0018_cart_and_order_lines")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
