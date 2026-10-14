# Pagos

**No hay pasarela de pago conectada.** Ningún pago se procesa ni se confirma automáticamente en el sitio, no se piden datos de tarjeta y no se simulan transacciones ni confirmaciones de proveedores.

## Métodos en el checkout

| Método | Estado | Efecto |
|---|---|---|
| A coordinar | Manual | El equipo acuerda el pago con el cliente; el personal lo registra con una referencia. |
| Bitcoin | Manual | Descuento del 15 % sobre el subtotal de productos (sin envío), calculado en el servidor. Queda **pendiente de verificación** hasta que el personal registra el pago con referencia. |
| PayPal | **DEMO, no disponible** | Solo registra la preferencia. No procesa nada; el pedido queda "Unpaid". No puede marcarse como pagado. |
| Tarjeta | **DEMO, no disponible** | Igual que PayPal. No se solicita ningún dato de tarjeta. |

## Reglas

- Un pedido no equivale a un pago confirmado. Los estados de pedido, pago, producción y envío son independientes.
- La producción solo puede iniciar con el pago registrado.
- Los métodos DEMO no pueden registrarse como pagados. Si el cliente acuerda otra forma de pago, el personal puede cambiar el método del pedido a "A coordinar" o "Bitcoin" mientras no esté pagado (queda en el historial).
- Marcar un pedido como pagado exige una referencia, es un registro manual y nunca lo hace el cliente.
- Descuento Bitcoin: el panel `/panel/payments/` permite definir qué productos son elegibles (hoy los 4). Un producto no elegible no recibe descuento y el checkout lo indica.
- El descuento se aplica de forma definitiva solo cuando el pago queda registrado como verificado.

## Procedimientos de verificación pendientes de definir

1. **Bitcoin:** qué se verifica (hash de transacción, confirmaciones de red, monto y cotización BTC/USD aplicada), quién lo confirma y en qué plazo.
2. **PayPal:** requiere cuenta y credenciales de un proveedor, y un mecanismo verificable de confirmación (por ejemplo, notificaciones firmadas).
3. **Tarjeta:** requiere un proveedor de pagos; los datos de tarjeta nunca deben pasar por este sitio.
4. Política de reembolsos, comisiones y tipo de cambio.

Ninguna integración real debe habilitarse sin credenciales, una verificación de transacción y autorización expresa.
