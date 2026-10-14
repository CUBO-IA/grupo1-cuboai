# Carrito multiproducto

## Flujo del cliente

Smart Fit (perfil del perro y medidas) → elegir producto, **talla** y cantidad → **Add to cart** → carrito (editar cantidad, talla o medidas; quitar productos) → un solo checkout → revisión → confirmar → un pedido con varias líneas.

- Cada línea conserva **su propio perfil de perro, medidas, talla y cantidad**. Dos productos pueden usar el mismo perro o perros distintos.
- Si una prenda exige una medida que falta (p. ej. cuello cuando se configure), no se puede añadir ni hacer checkout hasta completarla.
- "Checkout this item only" sigue disponible desde una cotización individual.
- El carrito vive en la sesión del navegador; no hay cuentas de cliente.

## Cálculo (siempre en el servidor)

| Concepto | Regla |
|---|---|
| Precio unitario | Catálogo; el navegador no envía precios |
| Subtotal por línea | Precio unitario × cantidad (1 a 10 por línea) |
| Subtotal general | Suma de las líneas |
| Descuento Bitcoin | 15 % del subtotal de **cada línea elegible**, solo con método Bitcoin y sin envío; pendiente hasta verificar el pago |
| Envío | "To be confirmed" (sin tarifa definida) |
| Ajuste por talla | No calculado (regla pendiente); precios provisionales y revisión manual |

La talla elegida por el cliente **no cambia el precio**. Se compara con la talla de referencia calculada desde las medidas: si coincide con una fila posible, el pedido queda sin trabajo manual; si no, el panel pide al personal confirmarla.

## Pedido y líneas

- `Order` + `OrderLine` (una por producto): cantidad, precio unitario, subtotal, descuento, talla elegida/confirmada, copia de medidas, talla de referencia, materiales y costo estimado.
- `Order.production_status` es el agregado de las líneas (no iniciado / en producción / completado).
- Los pagos y los envíos siguen siendo estados del pedido completo.
- Los pedidos anteriores al carrito se migraron creando una línea cada uno.

## Panel y Order Copilot

- Cada línea muestra su talla, medidas, estado de confección y si está **lista**; el personal puede confirmar la talla y **iniciar/terminar la confección por línea**.
- Una línea solo puede iniciarse con el pago registrado, datos de entrega completos, medidas completas y talla clara o confirmada.
- Iniciar la producción desde el pedido completo aplica a todas las líneas y exige que todas estén listas.
- El envío exige que todas las líneas estén completadas.
- La ficha de taller agrupa las líneas con producto, cantidad, talla, medidas y materiales necesarios (solo personal).
- Los costos del pedido suman el presupuesto de cada línea × su cantidad.

## Limitaciones

- Cantidad máxima por línea: 10 (supuesto técnico).
- Sin cuentas ni historial de pedidos para el cliente.
- El carrito no caduca ni se fusiona entre dispositivos.
- Sin personalización por línea ni notas del cliente.
- Pendientes de negocio: regla de ajuste por talla, tope de $850, tarifa de envío, verificación de pagos.
