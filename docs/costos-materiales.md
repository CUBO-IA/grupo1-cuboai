# Módulo de costos de fabricación (privado)

**Uso interno.** Solo accesible con sesión de personal (`is_staff`) en `/panel/costs/`. Nunca se muestra en páginas públicas (hay pruebas que lo verifican).

Todos los valores son **supuestos editables — ESTIMATE, not verified**. No son cotizaciones de proveedores. Se marcan como validados únicamente cuando el personal lo indica.

## Cómo se calcula

- Subtotal de cada partida = consumo × precio unitario (redondeo a 2 decimales, ROUND_HALF_UP).
- Total de materiales = suma de los subtotales (se deriva; no es una constante).
- Costo total de fabricación = materiales + mano de obra + otros costos de producción.
- Margen bruto = precio base de venta − costo total. **No es ganancia neta** (no incluye comisiones, impuestos, marketing ni devoluciones).
- Si el costo supera el precio, el panel muestra una advertencia.

## Valores iniciales

| Producto | Precio base | Materiales | Mano de obra | Otros | Costo total | Margen bruto estimado | Origen |
|---|---:|---:|---:|---:|---:|---:|---|
| Wedding Dog | $650 | $100.00 | $60.00 | $15.00 | $175.00 | $475.00 | Guía maestra |
| Tactical Dog | $300 | $100.00 | $60.00 | $15.00 | $175.00 | $125.00 | Guía maestra |
| Christmas Dog | $250 | $100.00 | $60.00 | $15.00 | $175.00 | $75.00 | Guía maestra |
| Dog Sweater | $125 | $40.00 | $35.00 | $8.00 | $83.00 | $42.00 | Estimación inicial del prototipo |

Las partidas "reserva provisional" no tienen un desglose confirmado de insumos y se identifican como tales; deben reemplazarse por materiales concretos cuando existan cotizaciones reales.

## Pedidos

Al crear un pedido se guarda una copia (snapshot) del presupuesto del producto en ese momento, solo visible en el panel. Si el presupuesto cambia después, los pedidos existentes conservan su costo estimado original. El costo real cargado por el personal tiene prioridad sobre cualquier estimación.

## Limitaciones y pendientes

- El consumo es para una talla de referencia. Las variaciones por talla/tamaño del perro **no están implementadas**: dependen de la tabla de tallas y de los factores de consumo, pendientes de validación con confección.
- Precios y consumos sin validar con proveedores.
- No hay historial de cambios del presupuesto (solo última actualización y usuario).
- Costos de envío no incluidos.
