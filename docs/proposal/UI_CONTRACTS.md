# UI_CONTRACTS — Contratos de interfaz y sitemap

> Contratos para el refresh visual SIN tocar lógica de negocio ni backend.

## 1. Sitemap de páginas (vista propuesta)
| Ruta | Página | Estado | Cambio propuesto |
|---|---|---|---|
| `/` | Home premium | existe | Hero con foto real, valor Smart Fit, catálogo destacado |
| `/productos/` | Catálogo | existe | Grid editorial responsive |
| `/producto/<slug>/` | Ficha | existe | Materiales + Smart Fit CTA + precio provisional etiquetado |
| `/smart-fit/` | Medidas | existe | Formulario legible móvil, errores claros |
| `/smart-fit/<uuid>/` | Resultado | existe | Resumen medidas + acciones |
| `/smart-fit/<uuid>/cotizar/` | Cotizar | existe | Precio servidor, provisional etiquetado |
| `/quote/<uuid>/` | Cotización | existe | Desglose + checkout |
| `/quote/<uuid>/checkout/` | Checkout | existe | Total real, estado unpaid, BTC demo |
| `/cart/` | Carrito | existe | Líneas, cantidades, total |
| `/cart/checkout/` | Checkout carrito | existe | Igual checkout |
| `/order/<uuid>/` | Seguimiento | existe | Sin costos internos |
| `/guide/` | Asistente | existe | Determinista |
| `/panel/*` | Panel staff | existe | Sin cambios de lógica; solo skin |

## 2. Contratos de componentes
### 2.1 Componente `ProductCard`
- Input: `{slug, nombre_corto, precio, imagen, tagline}`
- Comportamiento: enlace a ficha; precio siempre desde catálogo (nunca del DOM).
- Estados: normal / loading (skeleton) / imagen no disponible (fallback honesto).

### 2.2 Componente `QuoteBreakdown`
- Input: `{unit_base_price, quantity, subtotal, discount_rate, discount_amount, amount_due, is_final, shipping}`
- Regla: si `is_final=false`, mostrar etiqueta "precio provisional — regla de talla pendiente".
- Descuento BTC: mostrar "aplicado al verificar pago", nunca restar silenciosamente.

### 2.3 Componente `OrderStatusTimeline`
- Input: `{status, payment_status, production_status, shipping_status, events}`
- Regla: los 4 estados son independientes; mostrar cada uno por separado.
- Solo staff ve costos y referencia de pago.

### 2.4 Componente `SmartFitForm`
- Campos: name (opt), breed, weight+unit, back_length+unit, chest_girth+unit, neck_girth (opt/req).
- Regla: neck_girth requerido solo si la prenda lo exige (measurement_requirements).
- Errores de rango con unidades equivalentes (kg/lb, cm/in).

## 3. Tokens de interacción (estados de la UI)
- **Carga:** skeleton/spinner; nunca bloquear el teclado.
- **Error:** mensaje específico + retención del formulario (ya implementado en _save_dog).
- **Vacío:** carrito vacío con CTA a catálogo; panel sin pedidos con mensaje.
- **Éxito:** flash "Measurements saved." (ya existe), confirmación de pedido con número WK-XXXXXX.

## 4. Wireframes textuales
### 4.1 Home (móvil 375px)
```
[ header: logo corona + nav ]
[ hero: foto real dachshund + "Wiener Kingdom" ]
[ Smart Fit destacado: "Mide a tu perro" ]
[ grid 2 col: ProductCards (8) ]
[ footer: contacto, políticas (borrador), aviso demo ]
```

### 4.2 Ficha producto
```
[ imagen principal + thumbnails ]
[ nombre + precio (provisional etiquetado) ]
[ tagline + descripción ]
[ características (iconos) ]
[ materiales (nombre + función breve) ]
[ CTA: Smart Fit → cotizar ]
```

### 4.3 Checkout
```
[ resumen: producto, cantidad, subtotal ]
[ descuento BTC: pendiente de verificación ]
[ envío: por confirmar ]
[ total a pagar ]
[ formulario: nombre, email, teléfono, país, ciudad, dirección ]
[ método: to be arranged / bitcoin / paypal demo / card demo ]
[ aviso: "demo, no se procesará pago real" ]
[ submit: crear pedido (queda unpaid) ]
```

## 5. Viewports de prueba
- 375px (móvil), 768px (tablet), 1440px (desktop).
- Navegación por teclado y screen reader en las 3 resoluciones.