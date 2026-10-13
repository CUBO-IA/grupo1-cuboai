# Checklist de aceptación del MVP, IA y limitaciones

Estado a la Task 11. "Verificado" significa cubierto por pruebas automatizadas ejecutadas en esta sesión (`manage.py test`: 80 pruebas OK). No hubo una revisión visual completa en navegador.

## Checklist

| # | Criterio | Estado |
|---|---|---|
| 1 | Catálogo con 4 productos, precios, imágenes y fichas intactos | Verificado |
| 2 | Smart Fit: registro de medidas con unidades, validación y persistencia | Verificado |
| 3 | Smart Quote: precio calculado en el servidor, no manipulable | Verificado (solo precio base) |
| 4 | Cotización con ajuste por talla | **Pendiente: regla comercial no definida** |
| 5 | Checkout con datos de contacto y entrega, validados en el servidor | Verificado |
| 6 | Pedido persistente, sin duplicados por reenvío, con snapshot | Verificado |
| 7 | Estados de pago, producción y envío separados; pago no se marca por completar el formulario | Verificado |
| 8 | Panel privado con acceso restringido, búsqueda y filtros | Verificado |
| 9 | Transiciones de estado con historial | Verificado |
| 10 | Costos y margen con distinción real/estimado | Verificado |
| 11 | Asistente limitado al catálogo, sin inventar datos | Verificado (flujo determinista) |
| 12 | Descuento Bitcoin | **No implementado: falta la tasa comercial** |
| 13 | Pagos reales | **Fuera de alcance** |
| 14 | Revisión visual y responsive en navegador | **Pendiente de revisión humana** |
| 15 | Ensayo completo de demo (Task 12) | Pendiente |

## Integraciones de IA

- **Ninguna.** El asistente (`tienda/assistant.py`) es determinista: reglas fijas y palabras clave sobre `PRODUCTOS`. No llama a modelos ni a servicios externos, no usa claves y no añade dependencias.
- Limitaciones: entiende solo preguntas cortas en inglés/español básico, no mantiene conversación, no usa contexto de pedidos, y declara "no tengo esa información" para envíos, pagos, descuentos, devoluciones y estado de pedidos.
- Si se integrara un modelo de lenguaje habría que decidir costo, claves y filtrado de datos personales antes de activarlo.

## Limitaciones conocidas

- Toda cotización y pedido tiene **precio provisional** (precio base) hasta aprobar la regla de tallas.
- Sin pasarela de pago: el pago se registra manualmente con referencia.
- El cliente accede a su pedido solo por la URL con UUID (sin cuenta ni verificación por correo).
- Sin límite de intentos de login, `DEBUG=True` y sin configuración de producción (HTTPS, hosts, cookies seguras).
- Costos: el objetivo de $175 es provisional; los costos reales los carga el personal.
- Rangos de validación de medidas provisionales (no validados por el negocio).
- Sin correos de confirmación ni notificaciones.
- Las reglas de transición (p. ej. no enviar antes de terminar producción) son supuestos técnicos pendientes de aprobación.

## Decisiones comerciales pendientes
1. Fórmula/tabla de precio por talla y aplicación del tope de $850.
2. Tasa y base elegible del descuento Bitcoin.
3. Costos reales de fabricación.
4. Si se puede producir sin pago o con precio provisional.
5. Qué productos requieren el contorno del cuello.
6. Política de envíos, devoluciones y privacidad de datos.

## Registro de trabajo
No existe un registro de trabajo previo en el repositorio; el historial de commits (`git log`) documenta cada etapa.
