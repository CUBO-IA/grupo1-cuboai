# Task 2 — Catálogo y datos base

## 1. Catálogo (D2-A1 / D2-B1)

- El catálogo está en el diccionario `PRODUCTOS` de `web/tienda/views.py`. Las plantillas (`productos.html`, `detalle.html`) lo consumen; no hay modelo de producto.
- **Decisión:** no se migra a base de datos. No hay aún una necesidad validada (edición por usuarios, inventario, variantes), y migrarlo duplicaría datos y arriesgaría las fichas actuales. Las cotizaciones referencian el producto por su clave (`product_slug`: `wedding-dog`, `tactical-dog`, `christmas-dog`, `dog-sweater`).
- Reconsiderar la migración si en Tasks posteriores se necesitan tallas/variantes por producto o edición sin tocar código.

| Clave | Nombre | Precio base | Imagen |
|---|---|---:|---|
| wedding-dog | Wedding Dog | $650 | `static/tienda/img/wedding-dog.jpg` |
| tactical-dog | Tactical Dog | $300 | `static/tienda/img/tactical-dog.jpg` |
| christmas-dog | Christmas Dog | $250 | `static/tienda/img/christmas-dog.jpg` |
| dog-sweater | Dog Sweater | $125 | `static/tienda/img/dog-sweater.jpg` |

Nota: `precio` es un string con `$` (p. ej. `"$650"`). Quien cree una cotización deberá convertirlo a `Decimal`; no se cambió el formato para no tocar las fichas.

Verificado por `tienda/tests.py` (nombres, precios, existencia de imágenes, render de las páginas).

## 2. Modelos (D2-A2) — `web/tienda/models.py`

Antes de crearlos no existía ningún modelo en el proyecto.

```
DogProfile 1 ──< Quote 1 ──0..1 Order
```

| Modelo | Campos | Notas |
|---|---|---|
| `DogProfile` | `name`, `breed`, `weight_kg` (Dec 5,2), `back_length_cm` (Dec 5,1), `chest_girth_cm` (Dec 5,1), `neck_girth_cm` (Dec 5,1, opcional), `created_at` | Medidas siempre en kg/cm; la conversión de unidades se hace en el formulario. |
| `Quote` | `dog` (FK, PROTECT), `product_slug`, `base_price` (Dec 10,2), `total_price` (Dec 10,2, nulo), `status` (draft/accepted/cancelled), `created_at` | `total_price` es nulo hasta que exista la regla de precio por talla. |
| `Order` | `quote` (OneToOne, PROTECT), `total` (Dec 10,2), `status` (pending/confirmed/cancelled), `created_at` | Un pedido nace de una cotización aceptada. |

Decisiones:
- Importes en `DecimalField`, nunca `float`.
- `PROTECT` en las relaciones para no perder historial por borrados en cascada.
- No se guardan datos personales del cliente (nombre, correo, teléfono, dirección): no son necesarios aún y se definirán con el checkout.
- Sin formularios, vistas, admin ni API para estos modelos (fuera de alcance).

Supuestos pendientes (no se inventaron reglas):
1. **Tallas y precio por talla:** no definidos; por eso `total_price` es nulo y no hay campo de talla.
2. **Estados:** conjunto mínimo; ampliar (p. ej. pago, producción, entrega) cuando exista el flujo real.
3. **Datos de contacto/envío del cliente:** pendientes para checkout.
4. **Un pedido por cotización** (OneToOne): confirmar si se admiten pedidos con varias prendas.
5. **Moneda:** se asume USD por los `$` del catálogo (El Salvador); no hay campo de moneda.

## 3. Especificación Smart Fit (D2-B2)

Solo especificación; el formulario se diseña e implementa en el Día 3.

| Campo | Modelo | Obligatorio | Unidad (entrada) | Rango plausible (a validar con el negocio) | Ayuda propuesta |
|---|---|---|---|---|---|
| Nombre del perro | `name` | Sí | — | 1–80 caracteres | "¿Cómo se llama tu perro?" |
| Raza | `breed` | Sí | — | 1–80 caracteres | "Si es mestizo, escribe la raza más parecida." |
| Peso | `weight_kg` | Sí | kg o lb | 1–40 kg | "Pesa a tu perro en una báscula, con o sin él en brazos restando tu peso." |
| Largo del lomo | `back_length_cm` | Sí | cm o in | 10–100 cm | "Desde la base del cuello hasta la base de la cola, con el perro de pie." |
| Contorno del pecho | `chest_girth_cm` | Sí | cm o in | 15–120 cm | "Rodea la parte más ancha del pecho, detrás de las patas delanteras." |
| Contorno del cuello | `neck_girth_cm` | Solo si el producto lo requiere | cm o in | 10–70 cm | "Mide donde normalmente va el collar; deja pasar dos dedos." |

Reglas:
- Valores numéricos positivos; el formulario convierte lb→kg e in→cm antes de guardar (1 lb = 0,45359237 kg; 1 in = 2,54 cm).
- Los rangos son valores plausibles provisionales para detectar errores de captura (p. ej. cm vs. in); no son reglas comerciales ni tallas.
- Qué productos requieren cuello queda por definir en el Día 3.
- Mensajes de error propuestos: "Ingresa un número mayor que 0", "Este valor parece fuera de rango; revisa la unidad".

Vinculación:
1. El formulario crea un `DogProfile`.
2. Al cotizar, se crea un `Quote` con `dog` y `product_slug`, y `base_price` tomado del catálogo.
3. Cuando la cotización se acepta, se crea un `Order` con `quote` y `total`.

Fuera de alcance de esta Task: consumo de materiales y precio por talla (jornadas posteriores).
