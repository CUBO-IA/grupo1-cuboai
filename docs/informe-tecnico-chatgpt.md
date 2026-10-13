# Informe técnico — Wiener Kingdom AI Commerce (MVP)

Documento autocontenido para revisión externa. Repositorio: `CUBO-IA/grupo1-cuboai`, rama `main`, aplicación Django en `web/`. Contexto: CUBO_AI Challenge 2026.

**Estado:** Tasks 1–12 completadas y especificación comercial aplicada (commit `c995ff8`). 96 pruebas automatizadas OK. Funciones sujetas a decisiones del negocio quedan marcadas como pendientes.

## 1. Resumen

Tienda web en Django para prendas de perros dachshund. Flujo implementado de extremo a extremo:

Catálogo → asistente guiado → Smart Fit (medidas) → Smart Quote → checkout → pedido persistente → panel privado (estados, pago, costos) → seguimiento del cliente.

Puntos clave del estado actual:
- **Precio provisional:** no existe regla comercial de precio por talla. Toda cotización y pedido usa el precio base del catálogo y se indica que el equipo la revisa manualmente.
- **Sin pagos reales:** el pago es un registro manual del personal con referencia obligatoria. No hay pasarela ni datos de tarjeta.
- **Descuento Bitcoin 15 %:** calculado en el servidor sobre el subtotal de productos (sin envío), mostrado por separado y en estado "pendiente de verificación" hasta registrar el pago.
- **Producción condicionada al pago:** no puede iniciar mientras el pago no esté registrado.
- **Costos:** materiales y mano de obra editables; el objetivo de $175 está etiquetado como provisional, nunca como costo real.

## 2. Stack

| Elemento | Detalle |
|---|---|
| Lenguaje / framework | Python 3.12, Django 5.2 |
| Base de datos | SQLite (`db.sqlite3`, no versionado), transacciones `IMMEDIATE` con espera de 20 s |
| Frontend | Plantillas Django, CSS propio, sin JavaScript funcional |
| Dependencias (`requirements.txt`) | `Django`, `gunicorn`, `whitenoise` (estas dos no se usan en código; gunicorn no corre en Windows) |
| Autenticación | `django.contrib.auth` (usuarios con `is_staff`) |
| IA externa | Ninguna |

## 3. Estructura

```
web/
  config/        settings.py, urls.py, wsgi.py
  tienda/
    models.py    DogProfile, Quote, Order, OrderEvent
    forms.py     SmartFitForm, CheckoutForm, CostForm
    views.py     catálogo (dict PRODUCTOS), Smart Fit, cotización, checkout, pedido, asistente
    panel.py     panel privado (decorador staff_required)
    services.py  precio base, cotización, pedido, descuento, transiciones, costos
    assistant.py asistente determinista
    migrations/  0001–0007
    tests.py, test_panel.py, test_flow.py, test_assistant_costs.py, test_commercial_spec.py
  templates/tienda/   base, inicio, productos, detalle, smartfit(_resultado), smartquote,
                      checkout, order, assistant, panel_login, panel_orders, panel_order
  static/tienda/      css/style.css, js/script.js, img/ (5 imágenes)
docs/                 guía técnica, guion de demo, checklist, ensayo, especificación comercial,
                      borrador de políticas, este informe
README.md
```

## 4. Modelo de datos

```
DogProfile 1 ──< Quote 1 ──0..1 Order 1 ──< OrderEvent
```

- **DogProfile:** `public_id` (UUID), `name`, `breed`, `weight_kg` (Decimal 5,2), `back_length_cm`, `chest_girth_cm`, `neck_girth_cm` (opcional; Decimal 5,1), `created_at`.
- **Quote:** `public_id`, `dog` (FK PROTECT), `product_slug`, `base_price` (Decimal 10,2), `total_price` (nulo mientras sea provisional), `pricing` (`provisional`/`final`), `status` (`draft`/`accepted`/`cancelled`).
- **Order:**
  - Identificación: `public_id`, `quote` (OneToOne PROTECT), número `WK-<pk 6 dígitos>`.
  - Importes: `total` (siempre el subtotal de productos), `price_is_provisional`, `payment_method` (`unspecified`/`bitcoin`), `discount_rate`, `discount_amount`, `discount_status` (`none`/`pending_verification`/`applied`). Propiedades: `amount_due` (descuento solo si está aplicado) y `amount_if_discount`.
  - Cliente: `customer_name`, `customer_email`, `customer_phone`, `country`, `city`, `address`.
  - `snapshot` (JSON): producto, precios, medidas, método de pago y descuento al crear el pedido.
  - Estados independientes: `status` (pending/confirmed/cancelled), `payment_status` (unpaid/paid), `production_status` (not_started/in_production/completed), `shipping_status` (not_shipped/shipped/delivered).
  - Pago manual: `payment_reference`.
  - Costos internos: `estimated_materials`, `estimated_labor`, `actual_materials`, `actual_labor`, `estimated_cost` y `actual_cost` (sumas derivadas), `cost_notes`.
- **OrderEvent:** `order`, `field`, `from_value`, `to_value`, `note`, `by` (User), `created_at`.
- El catálogo **no está en base de datos**: es el diccionario `PRODUCTOS` en `views.py`; las cotizaciones lo referencian por clave.

Catálogo vigente: Wedding Dog $650, Tactical Dog $300, Christmas Dog $250, Dog Sweater $125.

## 5. Rutas

| Ruta | Acceso | Función |
|---|---|---|
| `/`, `/productos/`, `/producto/<slug>/` | Público | Inicio, catálogo, ficha |
| `/guide/` | Público (GET) | Asistente guiado |
| `/smart-fit/`, `/smart-fit/<uuid>/` | Público | Medidas y resumen |
| `POST /smart-fit/<uuid>/cotizar/` | Público | Crea o reutiliza cotización borrador |
| `/quote/<uuid>/`, `/quote/<uuid>/checkout/` | Público | Cotización y checkout |
| `/order/<uuid>/` | Público (por UUID) | Pedido y seguimiento |
| `/panel/login/`, `/panel/logout/` | — | Login staff |
| `/panel/`, `/panel/orders/<uuid>/` | Staff | Lista, filtros, detalle, transiciones, costos |

## 6. Reglas de negocio y decisiones técnicas

- **Precio en el servidor:** `services.get_base_price(slug)` lee `PRODUCTOS` y convierte `"$650"` a `Decimal`. El navegador solo envía la clave del producto; precio, descuento, estado y tipo enviados se ignoran (hay pruebas).
- **Smart Fit:** unidades de entrada kg/lb y cm/in, convertidas y redondeadas (ROUND_HALF_UP) a kg/cm antes de guardar. Rangos plausibles provisionales, aplicados tras convertir: peso 1–40 kg, lomo 10–100 cm, pecho 15–120 cm, cuello 10–70 cm. El cuello es opcional para todas las prendas.
- **Cotización:** siempre provisional; el desglose muestra el precio base y "Size adjustment: not calculated yet". Una cotización borrador igual (perro + producto) se reutiliza.
- **Checkout:** valida correo, teléfono (7–15 dígitos), longitud de campos y método de pago (a coordinar o Bitcoin; tarjeta y PayPal no se ofrecen porque su verificación no está definida). `create_order` corre en transacción con restricción única por cotización: reenvíos, incluso simultáneos, devuelven el pedido existente. Recalcula el total desde el catálogo y guarda el `snapshot`.
- **Descuento Bitcoin:** `compute_discount` = 15 % del subtotal de productos, redondeo a 2 decimales ROUND_HALF_UP; el envío queda fuera de la base (aún no hay costo de envío). Se muestra en línea aparte y no se descuenta del importe a pagar hasta pasar a `applied`, lo que ocurre cuando el personal registra el pago con referencia. Esa es una verificación manual; el procedimiento real de verificación no está definido.
- **Estados y transiciones:** sin retrocesos; `paid` exige referencia; **producción solo si el pago está registrado** (regla de la especificación comercial); no enviar antes de completar producción; pedido enviado no se cancela; cancelado no cambia. Cada cambio crea un `OrderEvent`. Las reglas distintas de la producción tras pago son supuestos técnicos pendientes de aprobación.
- **Costos:** el total es materiales + mano de obra; prioridad costo real > estimado cargado > objetivo provisional de $175. Margen = importe a pagar − costo. Solo visible en el panel, etiquetado como "ACTUAL" o "ESTIMATE — not verified".
- **Seguimiento al cliente:** explica los estados, muestra subtotal, descuento pendiente o aplicado, "Shipping cost: not calculated yet" e importe a pagar; lista actualizaciones sin notas, referencias ni nombres de staff. Nunca sugiere pago o envío sin registro del personal.
- **Asistente:** reglas y palabras clave sobre el catálogo. Responde precios y descripciones reales, recomienda por ocasión y guía a Smart Fit. Para envíos, pagos, descuentos, devoluciones y estado de pedidos responde que no tiene información. Pide aclaración si se mencionan varios productos. No escribe datos.
- **Concurrencia:** `transaction_mode=IMMEDIATE` y `timeout=20` en SQLite; corrige un 500 "database is locked" hallado en el ensayo con envíos simultáneos.
- **IDs públicos:** UUID en todas las URLs de perfil, cotización y pedido; los ids numéricos devuelven 404.

## 7. Seguridad

Implementado: CSRF en todos los POST; panel solo para `is_staff` activo (anónimo → login, sin permisos → 403); escape automático de plantillas; entrada del asistente limitada a 200 caracteres; `DJANGO_SECRET_KEY` por variable de entorno; sin credenciales ni secretos en el repositorio; costos, notas y referencias de pago nunca aparecen en páginas públicas.

Pendiente / limitaciones: sin límite de intentos de login; `DEBUG=True` y `ALLOWED_HOSTS=[]`; sin HTTPS ni cookies seguras; el cliente accede a su pedido solo por UUID (sin cuenta ni verificación); se guardan datos personales (nombre, correo, teléfono, dirección) sin política de privacidad ni retención aprobadas; sin correos de confirmación.

## 8. Pruebas y verificación

`manage.py test`: **96 pruebas, todas OK** (tests.py 35, test_panel.py 20, test_flow.py 8, test_assistant_costs.py 20, test_commercial_spec.py 13). Cubren:
- catálogo, validación y persistencia de Smart Fit, conversión de unidades;
- cotización y precio no manipulable;
- checkout: validación, idempotencia, snapshot, recálculo;
- descuento Bitcoin: montos, redondeo, pendiente/aplicado, no manipulable desde el cliente;
- producción bloqueada hasta registrar el pago;
- permisos, búsqueda y filtros del panel, transiciones válidas e inválidas;
- costos (materiales y mano de obra, real vs estimado) y fugas de datos internos;
- asistente, CSRF y flujo completo.

Otras verificaciones realizadas:
- instalación limpia desde un clon del remoto (Task 12) con 80 pruebas OK en ese momento;
- ensayo manual de la demo en navegador y comprobación de que no hay desbordes horizontales a 375 px (`docs/task-12-ensayo-y-alcance.md`);
- migración `0007` aplicada sobre una base con un pedido existente, sin pérdida de datos.

Defectos hallados y corregidos en el ensayo: 500 por bloqueo de SQLite en envíos simultáneos y texto contradictorio "Paid — no payment has been collected".

**No verificado:** aspecto visual (no hubo capturas de pantalla), las pantallas modificadas por la especificación comercial en navegador, otros navegadores y dispositivos reales, accesibilidad, despliegue en producción, carga.

## 9. Historial de commits (main)

| Commit | Contenido |
|---|---|
| `aa1e6bf` | Copia limpia de `web/` desde el ZIP |
| `cf079b3` | Modelos (Task 2) y Smart Fit (Task 3) |
| `4ca699f` | Smart Quote provisional (Task 4) |
| `7784c63` | Checkout y pedidos, UUID públicos (Task 5) |
| `afaac7c` | Panel privado, transiciones, estimación de costos (Task 6) |
| `b1d5592` | Pruebas de flujo, guía técnica, guion de demo (Task 7) |
| `50c8a5f` | Asistente, costos editables, seguimiento, README (Tasks 9–11) |
| `9ad23c1` | Ensayo, correcciones de concurrencia y texto, alcance congelado (Task 12) |
| `c995ff8` | Especificación comercial: descuento Bitcoin, producción tras pago, costos por componente, borrador de políticas |

## 10. Especificación comercial aplicada

| Regla | Estado |
|---|---|
| Precios base sin recargos automáticos; revisión manual | Implementado (precio provisional + aviso) |
| Límite máximo de US$850 | Pendiente de definición |
| Descuento Bitcoin 15 % sobre productos, sin envío, separado y en el servidor | Implementado |
| Aplicación definitiva del descuento tras verificar el pago | Parcial: registro manual del personal; procedimiento no definido |
| Pedido no confirma el pago; producción solo tras verificar el pago | Implementado |
| Estados de pedido, pago y producción independientes | Implementado |
| US$175 como objetivo provisional | Implementado (etiquetado) |
| Costos de materiales y mano de obra editables; real vs estimado | Implementado |
| Cuello condicional según prenda | Pendiente (hoy opcional en todas) |
| Borrador de políticas, sin publicar | Entregado en `docs/politicas-borrador.md` con campos por definir |

## 11. Decisiones pendientes del negocio

1. Fórmula o tabla de ajuste por talla y aplicación del tope de US$850.
2. Procedimiento de verificación de pagos por Bitcoin, tarjeta y PayPal.
3. Costos reales por producto y talla.
4. Medidas necesarias por tipo de prenda (incluido qué prendas requieren cuello).
5. Condiciones definitivas de envío, cancelación, modificación y devolución, y política de privacidad.
6. Costo de envío y su cálculo (hoy no existe).
7. Si un pedido con precio provisional puede entrar a producción (hoy solo se exige pago registrado).
8. Aprobación de las reglas de transición de estados que no vienen de la especificación.
9. Pasarela de pago real, si se desea (costos, credenciales).

## 12. Preguntas sugeridas para la revisión

- ¿Es adecuado un pedido con snapshot JSON, estados independientes y descuento "pendiente/aplicado" para evolucionar a pago verificable (por ejemplo, webhooks de un proveedor)?
- ¿Qué cambios mínimos hacen falta para producción (PostgreSQL, secretos, HTTPS, throttling de login, correos transaccionales, política de datos personales)?
- ¿Conviene mover el catálogo a base de datos cuando existan tallas y variantes?
- ¿Cómo diseñar la fórmula de talla y el tope de US$850 para que la cotización provisional se convierta en definitiva con revisión manual auditada?
- ¿Cómo integrar un asistente basado en LLM manteniendo "solo datos del catálogo" y sin exponer datos personales?
