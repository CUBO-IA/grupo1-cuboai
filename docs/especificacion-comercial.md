# Especificación comercial — Wiener Kingdom

Fuente: especificación comercial recibida del negocio. Esta página la resume y la mapea a la implementación.

## Reglas y su implementación

| Regla comercial | Implementación | Estado |
|---|---|---|
| Se mantienen los precios base mientras se valida una fórmula por talla; sin recargos automáticos | `services.get_base_price`; toda cotización es `provisional`; el desglose muestra "Size adjustment: not calculated yet" | Implementado |
| Las cotizaciones con ajustes no definidos se revisan manualmente | Textos en cotización, checkout y pedido: "our team reviews every quote manually before confirming it" | Implementado (aviso); no hay cola de revisión dedicada |
| Límite de US$850 sujeto al procedimiento de cotización | — | **Pendiente de definición** |
| Descuento Bitcoin 15 % sobre el subtotal de productos elegibles, sin envío; separado y calculado en el servidor | `services.compute_discount` (ROUND_HALF_UP a 2 decimales); líneas separadas en checkout, pedido y panel; el envío no entra en la base (aún no existe costo de envío) | Implementado |
| La aplicación definitiva del descuento requiere confirmación verificable del pago | El descuento queda `pending_verification`; pasa a `applied` solo cuando el personal registra el pago con referencia. El procedimiento de verificación real **no está definido** | Parcial: pendiente de procedimiento |
| El registro del pedido no confirma el pago | `payment_status` inicia en `unpaid`; completar el checkout no lo cambia | Implementado |
| La producción solo empieza tras verificar el pago | Transición `not_started → in_production` bloqueada mientras `payment_status != paid` | Implementado |
| Estados de pedido, pago y producción independientes | Campos `status`, `payment_status`, `production_status`, `shipping_status` separados | Implementado |
| US$175 es objetivo provisional, no costo validado | `TARGET_MANUFACTURING_COST`; etiquetado "target, not a proven cost" | Implementado |
| Costos de materiales y mano de obra editables; reportes distinguen estimado y real | Panel: materiales y mano de obra estimados y reales; total = suma; origen etiquetado (actual / estimado / objetivo) | Implementado |
| Smart Fit recopila peso, lomo y pecho; cuello condicional según prenda (a validar con confección) | Cuello opcional para todas las prendas | Parcial: falta definir qué prendas lo requieren |
| Borrador de políticas de envío, cancelación, modificaciones y devoluciones; no publicarlas como vigentes | `docs/politicas-borrador.md`; no se publica en el sitio | Borrador entregado |

## Pendientes de validación

1. Fórmula de ajuste por talla y aplicación del límite de US$850.
2. Procedimiento de verificación de pagos por Bitcoin, tarjeta y PayPal. Hoy solo existe el registro manual con referencia; tarjeta y PayPal no están disponibles en el checkout.
3. Costos reales por producto y talla.
4. Medidas necesarias por tipo de prenda.
5. Condiciones definitivas de envío, cancelación, modificación y devolución.
