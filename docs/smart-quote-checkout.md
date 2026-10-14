# Smart Quote y checkout

## Flujo

Perfil del perro → elegir producto y cantidad → cotización → checkout (datos) → **revisión** → confirmar → pedido.

El servidor calcula todos los importes. El navegador solo envía la clave del producto, la cantidad (1 a 10) y los datos de entrega; cualquier precio, descuento o total enviado se ignora.

## Resumen comercial

| Elemento | Origen |
|---|---|
| Producto e imagen | Catálogo |
| Cantidad | Elegida por el cliente (1–10; el máximo es un supuesto técnico) |
| Perfil del perro y medidas confirmadas | Perfil guardado; el pedido guarda su copia |
| Talla de referencia | Informativa, no validada; no cambia precios |
| Precio base unitario | Catálogo (tope técnico de US$850 por producto) |
| Ajuste por talla | **No calculado**: regla pendiente de aprobación; la cotización queda provisional y requiere revisión manual |
| Subtotal de productos | Precio unitario × cantidad |
| Descuento Bitcoin | 15 % del subtotal de productos, sin envío; se muestra por separado y queda "pendiente" hasta verificar el pago |
| Envío | "To be confirmed": no hay tarifa definida |
| Importe a pagar | Subtotal (el descuento solo cuenta cuando está aplicado) |
| Método de pago | Elegido en el checkout: a coordinar o Bitcoin |

## Corregir antes de confirmar

- **Cantidad:** desde la cotización (solo mientras no exista pedido).
- **Medidas:** "Edit measurements" desde la cotización o la revisión; vuelve a la cotización.
- **Producto:** "Change product" regresa al perfil para cotizar otra prenda.
- **Datos de entrega:** "Edit details" desde la revisión.

## Paso de revisión

El formulario de checkout envía `step=review`: el servidor valida y muestra el desglose completo sin crear el pedido. Solo `step=confirm` (o un POST directo válido) crea el pedido, que es idempotente por cotización.

## Pendiente de decisión comercial

1. Fórmula de ajuste por talla y procedimiento de cotización para el límite de US$850.
2. Tarifa o cálculo de envío.
3. Cantidad máxima por pedido y carrito multiproducto.
4. Procedimiento de verificación de pagos (Bitcoin, tarjeta, PayPal).
