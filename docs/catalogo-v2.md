# Catálogo v2 — decisiones de producto y estado

Fuente: `Weiner_Kingdom_Guia_Maestra_Organizada_v2.docx` y `Weiner_Kingdom_Presupuestos_Materiales_5_Productos.docx`.

## Productos activos (8)

| # | Producto | Precio base | Fotos |
|---|---|---:|---|
| 1 | Waterproof Linen Dachshund Wedding Dog Suit Pair for Two | $650 | `wedding-dog.jpg` (repositorio) |
| 2 | Tactical Dog | $300 | `tactical-dog.jpg` (repositorio) |
| 3 | Christmas Dog | $250 | `christmas-dog.jpg` (repositorio) |
| 4 | Walnut Whip Dachshund Harness Fleece | $250.00 | 2 fotos (carpeta de WINIPINIS) |
| 5 | Beige Sophisticated Sausage Dachshund Anti-Rub Dog Harness | $63.00 | 2 fotos |
| 6 | Tutti Frutti Houndstooth Anti-Rub Harness – Ribbon | $63.00 | 1 foto |
| 7 | Luxury Cable Knit Dachshund Jumper | $150.00 | 1 foto |
| 8 | Showercover Bamboo Dachshund Drying Robe | $88.00 | 3 fotos |

**Dog Sweater** fue retirado del catálogo activo: no se puede cotizar y su ficha devuelve 404. Las cotizaciones o pedidos históricos que lo referencian siguen siendo legibles en el panel; no se usa para calcular costos de otros productos.

**Nombre del producto 4:** el documento v2 dice "Alnut"; el listado comercial posterior dice "Walnut". Se usa **Walnut** (corrección de la errata). El identificador interno sigue siendo `alnut-whip-harness`.

**Precio del Wedding Dog:** el catálogo y la guía indican **$650**, pero el listado comercial más reciente muestra "Regular price 600$". Se mantiene **$650** hasta que el negocio confirme cuál es correcto.

## Asignación de fotografías

Las fotos de los 5 productos nuevos son las que el documento v2 coloca junto a cada fila; coinciden con los archivos de `Downloads\Copia de WINIPINIS` (se convirtieron a JPG para el sitio). No se usaron las capturas de pantalla de la tienda de referencia.

**Fotos confirmadas por el negocio** para usarse en el sitio.

**Limitaciones:**
- Son miniaturas de 168 × 168 px (excepto el jumper, 1284 × 1712 px): se ven borrosas ampliadas.
- Parecen provenir de tiendas de terceros (los nombres de archivo incluyen `doxiedri` y `sausagedogbox`); el negocio confirmó su uso.
- La foto asignada al jumper (cable knit) en el documento muestra una prenda tipo fleece; conviene confirmarla.

## Ficha pública "Materiales del traje"

Cada producto muestra los materiales y componentes con una breve explicación de su función. **Nunca** incluye consumos, precios unitarios, subtotales, mano de obra, costos ni márgenes (hay pruebas que lo verifican). Los textos describen cada material sin atribuirle propiedades que su nombre no respalde.

## HOME

Muestra el render `Publicidad de Alta Costura Canina.png` (carpeta de WINIPINIS; optimizado a JPG, 1671 × 941) como imagen principal, sin textos ni tarjetas encima. La navegación es una cinta transparente en la parte superior (Products a la izquierda; Smart Fit y Guide a la derecha); en móvil pasa debajo de la imagen. Debajo del render hay la propuesta de valor, el proceso en 3 pasos y los accesos a Products y Smart Fit.

## Costos

- Wedding, Tactical y Christmas: objetivo provisional de $175 (materiales $100, mano de obra $60, otros $15).
- Los 5 productos nuevos usan las tablas de materiales del documento de presupuestos (estimaciones, no cotizaciones). Su **mano de obra y otros costos no están definidos**: quedan en $0 y el panel lo advierte ("labor/other not set"), porque el margen mostrado está sobreestimado.

| Producto | Materiales estimados | Precio | Margen (solo materiales) |
|---|---:|---:|---:|
| Alnut Whip Harness | $50.00 | $250.00 | $200.00 |
| Beige Anti-Rub Harness | $22.00 | $63.00 | $41.00 |
| Tutti Frutti Harness | $25.00 | $63.00 | $38.00 |
| Cable Knit Jumper | $35.00 | $150.00 | $115.00 |
| Bamboo Drying Robe | $26.00 | $88.00 | $62.00 |

## Descuento Bitcoin

Según el listado comercial aportado, solo dos productos tienen "Sale price with BTC payments"; el resto figura a precio regular. Por eso **solo estos dos son elegibles**:

| Producto | Precio regular | Precio con BTC en el listado | Descuento implementado (15 %) |
|---|---:|---:|---:|
| Luxury Cable Knit Dachshund Jumper | $150.00 | $110.00 (−$40) | $127.50 (−$22.50) |
| Showercover Bamboo Dachshund Drying Robe | $88.00 | $76.00 (−$12, 14 %) | $74.80 (−$13.20) |

**Discrepancia por resolver:** los precios con BTC del listado ($110 y $76) **no equivalen al 15 %** que el negocio definió. El sistema aplica la regla del 15 % calculada en el servidor sobre el subtotal elegible (sin envío). Si el negocio prefiere precios BTC fijos, hay que indicarlo.

La elegibilidad es editable en `/panel/payments/`. El descuento sigue pendiente de verificación del pago.

## Pendiente de la siguiente fase

- Carrito multiproducto con una línea por producto, talla y medidas propias.
- Selección de talla por producto y medidas requeridas por prenda.
- Ficha de producción por línea y seguimiento por línea en el panel.
- Ajuste de precio por talla y tope de $850 (sin regla aprobada).
