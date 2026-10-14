"""Catálogo v2: presupuestos de materiales de los 5 productos nuevos y
elegibilidad del descuento Bitcoin.

Fuente: Weiner_Kingdom_Presupuestos_Materiales_5_Productos.docx. Los consumos
y precios son estimaciones hipotéticas para el prototipo, no cotizaciones de
proveedores. La mano de obra y otros costos de estos 5 productos NO están
definidos: quedan en 0 y marcados como incompletos.

Elegibilidad del descuento Bitcoin: el documento v2 no incluye una tabla
inequívoca, así que ningún producto queda elegible hasta que el negocio lo
confirme (editable en /panel/payments/).
"""

from decimal import Decimal as D

from django.db import migrations

# (nombre, unidad, consumo, precio unitario, es reserva provisional)
SEED = {
    "alnut-whip-harness": [
        ("Polar fleece premium antipilling", "m", D("0.70"), D("18.00"), False),
        ("Forro térmico transpirable", "m", D("0.50"), D("12.00"), False),
        ("Refuerzo de nylon para arnés", "m", D("1.20"), D("3.50"), False),
        ("Hebillas de liberación rápida", "unidad", D("2"), D("3.00"), False),
        ("Cinta de ajuste acolchada", "m", D("0.80"), D("4.00"), False),
        ("Cierre YKK", "unidad", D("1"), D("4.00"), False),
        ("Hilo reforzado para exteriores", "cono", D("0.10"), D("15.00"), False),
        ("Etiqueta tejida de marca", "unidad", D("1"), D("2.50"), False),
        ("Argollas metálicas resistentes", "unidad", D("2"), D("3.00"), False),
        ("Reserva para desperdicio y complementos", "lote", D("1"), D("4.00"), True),
    ],
    "beige-anti-rub-harness": [
        ("Tejido beige premium resistente", "m", D("0.35"), D("14.00"), False),
        ("Forro de malla suave", "m", D("0.25"), D("10.00"), False),
        ("Espuma de acolchado", "m²", D("0.20"), D("8.00"), False),
        ("Cinta de nylon de alta resistencia", "m", D("1.00"), D("2.50"), False),
        ("Hebillas ajustables", "unidad", D("2"), D("1.50"), False),
        ("Argolla metálica", "unidad", D("1"), D("2.00"), False),
        ("Hilo de poliéster reforzado", "cono", D("0.05"), D("8.00"), False),
        ("Ribete suave antipellizcos", "m", D("0.80"), D("2.00"), False),
        ("Etiqueta de marca", "unidad", D("1"), D("1.50"), False),
        ("Reserva para desperdicio y complementos", "lote", D("1"), D("2.00"), True),
    ],
    "tutti-frutti-harness": [
        ("Tejido premium pata de gallo", "m", D("0.35"), D("16.00"), False),
        ("Forro suave transpirable", "m", D("0.25"), D("10.00"), False),
        ("Cinta decorativa multicolor", "m", D("1.00"), D("3.50"), False),
        ("Cinta de nylon estructural", "m", D("0.90"), D("2.50"), False),
        ("Hebillas ajustables", "unidad", D("2"), D("1.50"), False),
        ("Argolla metálica", "unidad", D("1"), D("2.00"), False),
        ("Hilo reforzado", "cono", D("0.05"), D("8.00"), False),
        ("Ribete suave de acabado", "m", D("0.80"), D("2.00"), False),
        ("Etiqueta de marca", "unidad", D("1"), D("1.50"), False),
        ("Reserva para desperdicio y complementos", "lote", D("1"), D("2.65"), True),
    ],
    "cable-knit-jumper": [
        ("Hilo premium de lana merino", "kg", D("0.35"), D("42.00"), False),
        ("Hilo de mezcla de alpaca", "kg", D("0.15"), D("36.00"), False),
        ("Hilo elástico para puños", "kg", D("0.08"), D("20.00"), False),
        ("Hilo de confección", "cono", D("0.05"), D("8.00"), False),
        ("Etiqueta tejida de marca", "unidad", D("1"), D("2.50"), False),
        ("Refuerzo suave para el pecho", "pieza", D("1"), D("3.00"), False),
        ("Botones decorativos premium", "unidad", D("2"), D("1.50"), False),
        ("Reserva para desperdicio y complementos", "lote", D("1"), D("4.40"), True),
    ],
    "bamboo-drying-robe": [
        ("Tela de rizo con fibra de bambú", "m", D("0.65"), D("16.00"), False),
        ("Forro ligero absorbente", "m", D("0.30"), D("9.00"), False),
        ("Cinta de ajuste suave", "m", D("0.80"), D("2.50"), False),
        ("Velcro suave de contacto", "m", D("0.30"), D("3.00"), False),
        ("Ribete de algodón premium", "m", D("1.20"), D("2.50"), False),
        ("Hilo resistente a lavados", "cono", D("0.08"), D("10.00"), False),
        ("Etiqueta tejida de marca", "unidad", D("1"), D("2.00"), False),
        ("Broche de ajuste", "unidad", D("1"), D("1.50"), False),
        ("Reserva para desperdicio y complementos", "lote", D("1"), D("2.70"), True),
    ],
}

ACTIVE = [
    "wedding-dog", "tactical-dog", "christmas-dog",
    "alnut-whip-harness", "beige-anti-rub-harness", "tutti-frutti-harness",
    "cable-knit-jumper", "bamboo-drying-robe",
]


def seed(apps, schema_editor):
    ProductCost = apps.get_model("tienda", "ProductCost")
    MaterialLine = apps.get_model("tienda", "MaterialLine")
    Measurement = apps.get_model("tienda", "ProductMeasurement")
    Rule = apps.get_model("tienda", "ProductPaymentRule")

    for slug, lines in SEED.items():
        profile, created = ProductCost.objects.get_or_create(
            product_slug=slug,
            defaults={
                "labor_cost": D("0.00"),
                "other_costs": D("0.00"),
                "is_validated": False,
                "notes": "Materials estimated; labor and other production costs not defined yet.",
            },
        )
        if created:
            for pos, (name, unit, qty, price, reserve) in enumerate(lines, 1):
                MaterialLine.objects.create(
                    product_cost=profile, position=pos, name=name, unit=unit,
                    quantity=qty, unit_price=price, is_provisional_reserve=reserve,
                    is_validated=False,
                )

    for slug in ACTIVE:
        Measurement.objects.get_or_create(
            product_slug=slug,
            defaults={
                "requires_neck": False,
                "is_validated": False,
                "notes": "Pending validation with tailoring.",
            },
        )
        # Elegibilidad Bitcoin: pendiente de confirmar para todos.
        rule, _ = Rule.objects.get_or_create(
            product_slug=slug, defaults={"bitcoin_discount_eligible": False}
        )
        if rule.bitcoin_discount_eligible:
            rule.bitcoin_discount_eligible = False
            rule.save(update_fields=["bitcoin_discount_eligible"])


class Migration(migrations.Migration):

    dependencies = [("tienda", "0015_order_copilot")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
