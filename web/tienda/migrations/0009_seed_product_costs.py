"""Presupuestos iniciales de materiales por producto.

Fuente: guía maestra (Wedding Dog, Tactical Dog, Christmas Dog) y estimación
inicial del prototipo para Dog Sweater. TODOS son supuestos editables, no
cotizaciones de proveedores; nada queda marcado como validado.
"""

from decimal import Decimal as D

from django.db import migrations

# (nombre, unidad, consumo, precio unitario, es reserva provisional)
SEED = {
    "wedding-dog": {
        "labor": D("60.00"),
        "other": D("15.00"),
        "lines": [
            ("Satén Duchess de poliéster premium", "m", D("1.2"), D("22.00"), False),
            ("Forro de satén Bemberg", "m", D("0.8"), D("12.00"), False),
            ("Encaje Chantilly bordado", "m", D("0.8"), D("24.00"), False),
            ("Tul ilusión premium", "m", D("1.0"), D("7.00"), False),
            ("Cierre invisible YKK", "unidad", D("1"), D("3.00"), False),
            ("Hilo Gütermann Mara", "cono", D("0.15"), D("8.00"), False),
            ("Perlas y cristales decorativos", "lote", D("1"), D("12.00"), False),
            ("Entretela fusible premium", "m", D("0.5"), D("5.00"), False),
            ("Pasamanería y cinta satinada", "lote", D("1"), D("8.00"), False),
            ("Reserva provisional para complementos", "lote", D("1"), D("11.10"), True),
        ],
    },
    "tactical-dog": {
        "labor": D("60.00"),
        "other": D("15.00"),
        "lines": [
            ("Nylon Cordura 1000D", "m", D("1.2"), D("18.00"), False),
            ("Forro de malla 3D transpirable", "m", D("0.8"), D("10.00"), False),
            ("Cincha de nylon de alta resistencia", "m", D("2"), D("3.00"), False),
            ("Hebillas Duraflex", "unidad", D("4"), D("2.50"), False),
            ("Cierre YKK de uso rudo", "unidad", D("1"), D("5.00"), False),
            ("Velcro industrial", "m", D("0.8"), D("3.00"), False),
            ("Hilo bonded nylon Tex 70", "cono", D("0.2"), D("15.00"), False),
            ("Panel acolchado de espuma EVA", "lote", D("1"), D("12.00"), False),
            ("Argollas metálicas resistentes", "unidad", D("2"), D("4.00"), False),
            ("Reserva provisional para refuerzos y accesorios", "lote", D("1"), D("24.00"), True),
        ],
    },
    "christmas-dog": {
        "labor": D("60.00"),
        "other": D("15.00"),
        "lines": [
            ("Terciopelo de poliéster premium", "m", D("1.2"), D("18.00"), False),
            ("Tela tartán escocés premium", "m", D("0.8"), D("15.00"), False),
            ("Forro de satén", "m", D("0.8"), D("8.00"), False),
            ("Ribete de pelo sintético premium", "m", D("1.5"), D("7.00"), False),
            ("Cierre YKK", "unidad", D("1"), D("3.00"), False),
            ("Hilo Gütermann Mara", "cono", D("0.15"), D("8.00"), False),
            ("Galón dorado decorativo", "m", D("1.5"), D("5.00"), False),
            ("Cascabeles y adornos festivos", "lote", D("1"), D("8.00"), False),
            ("Entretela premium", "m", D("0.5"), D("5.00"), False),
            ("Reserva provisional para apliques y accesorios", "lote", D("1"), D("27.30"), True),
        ],
    },
    "dog-sweater": {
        "labor": D("35.00"),
        "other": D("8.00"),
        "lines": [
            ("Hilo premium mezcla merino", "kg", D("0.45"), D("38.00"), False),
            ("Hilo elástico para acabados", "kg", D("0.10"), D("24.00"), False),
            ("Puños y ribetes de punto premium", "lote", D("1"), D("7.50"), False),
            ("Hilo de confección reforzado", "cono", D("0.10"), D("8.00"), False),
            ("Etiqueta tejida de marca", "unidad", D("1"), D("2.50"), False),
            ("Botones o detalle decorativo premium", "lote", D("1"), D("4.50"), False),
            ("Reserva provisional para desperdicio y complementos", "lote", D("1"), D("5.20"), True),
        ],
    },
}


def seed(apps, schema_editor):
    ProductCost = apps.get_model("tienda", "ProductCost")
    MaterialLine = apps.get_model("tienda", "MaterialLine")
    for slug, data in SEED.items():
        profile, created = ProductCost.objects.get_or_create(
            product_slug=slug,
            defaults={
                "labor_cost": data["labor"],
                "other_costs": data["other"],
                "is_validated": False,
                "notes": "Initial estimate — not verified with suppliers.",
            },
        )
        if not created:
            continue  # nunca pisar valores ya editados
        for pos, (name, unit, qty, price, reserve) in enumerate(data["lines"], 1):
            MaterialLine.objects.create(
                product_cost=profile,
                position=pos,
                name=name,
                unit=unit,
                quantity=qty,
                unit_price=price,
                is_provisional_reserve=reserve,
                is_validated=False,
            )


def unseed(apps, schema_editor):
    ProductCost = apps.get_model("tienda", "ProductCost")
    ProductCost.objects.filter(product_slug__in=list(SEED)).delete()


class Migration(migrations.Migration):

    dependencies = [("tienda", "0008_product_costs")]

    operations = [migrations.RunPython(seed, unseed)]
