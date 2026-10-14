# Order Copilot y panel administrativo

El Order Copilot organiza los datos **ya confirmados** de un pedido para el taller. No genera instrucciones de confección que el cliente no haya aprobado y no completa datos faltantes.

## Indicadores por pedido (independientes)

| Indicador | Se cumple cuando |
|---|---|
| Pedido guardado | El pedido existe. |
| Pago confirmado | El pago está registrado con una referencia y el método no es DEMO. |
| Información validada | Datos de entrega completos, medidas completas (más el cuello si la prenda lo exige) y talla clara o confirmada por el personal. |
| Listo para fabricar | Pago confirmado + información validada + pedido no cancelado. |

"Información validada" comprueba que los datos existen y son coherentes; no es una validación de confección.

## Inicio de producción

La producción solo puede comenzar si el pedido está listo para fabricar. Si falta algo, la acción queda bloqueada con el motivo (por ejemplo: pago no registrado, dirección incompleta, talla ambigua sin confirmar).

La **talla de referencia** del cliente proviene de una tabla no validada. Cuando es ambigua o está fuera de tabla, el personal debe registrar la **talla confirmada** (queda en el historial) antes de producir. Esa confirmación no cambia precios.

## Panel

- **Resumen por etapa** (clicable como filtro): por revisar (sin pago), pagados / listos para fabricar, en producción, terminados, enviados. "Needs attention" agrupa los que requieren una acción: sin pago, listos para iniciar y terminados sin enviar. Los cancelados se excluyen.
- **Línea de progreso:** guardado → pago verificado → en producción → producción terminada → enviado → entregado.
- **Seguimiento:** número y transportista opcionales; se muestran al cliente solo cuando existen. Enviar sin número está permitido.
- **Ficha de taller** (`/panel/orders/<uuid>/sheet/`, imprimible): número y fecha, producto y cantidad, personalización (ninguna registrada), medidas confirmadas, talla, entrega, precio y descuento, método y estado de pago, estados, materiales y costos internos (estimación), e historial. Solo para personal.

## Limitaciones

- No hay personalización de producto registrada.
- No existe una validación de medidas por confección; las tallas son de referencia.
- Sin notificaciones al cliente ni estimaciones de tiempo (no hay datos de plazos definidos).
- Sin paginación: la lista muestra los 25 pedidos más recientes del filtro.
