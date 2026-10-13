# Guion de demo — 2 a 3 minutos

Preparación (antes de grabar): `migrate`, `createsuperuser`, `runserver`; base de datos vacía.

| Tiempo | Acción | Qué decir |
|---|---|---|
| 0:00 | Inicio → **Products** | "Cuatro prendas para dachshunds; cada ficha conserva su diseño original." |
| 0:20 | Abrir **Wedding Dog** | "Precio base $650, descripción y características." |
| 0:35 | Menú **Smart Fit** | "Registramos las medidas; si mezclo unidades, el sistema las valida." |
| 0:50 | Enviar el formulario vacío, luego con valores válidos (p. ej. Luna, 6 kg, 33 cm, 40 cm) | "Errores claros; los datos se conservan; se guardan en kg y cm." |
| 1:15 | **Get quote** → Wedding Dog | "La cotización la calcula el servidor. Es provisional: el ajuste por talla aún no está aprobado." |
| 1:35 | **Continue to checkout** → completar datos → **Place order** | "Se crea el pedido WK-000001. Pago: *Unpaid*; no se cobra nada." |
| 2:00 | `/panel/login/` → ver pedido | "Panel privado: búsqueda, filtros y estados separados de pago, producción y envío." |
| 2:20 | Marcar pago con referencia, producción, envío | "Cada cambio queda registrado; no se puede enviar antes de producir." |
| 2:45 | Mostrar estimación de costos | "Estimación con objetivo de $175, marcada como no verificada." |

## Mensajes clave
- Precio provisional hasta aprobar la regla de tallas.
- No hay pasarela de pago: el pago se registra manualmente.
- El descuento Bitcoin y los costos reales quedan pendientes de aprobación.
