# Informe técnico — Wiener Kingdom AI Commerce (MVP)

Documento autocontenido para revisión externa. Repositorio: `CUBO-IA/grupo1-cuboai`, rama `main`, aplicación Django en `web/`. Contexto: CUBO_AI Challenge 2026. Estado: Tasks 1–12 completadas, con las excepciones marcadas como pendientes.

## 1. Resumen

Tienda web en Django para prendas de perros dachshund. Flujo implementado de extremo a extremo:

Catálogo → asistente guiado → Smart Fit (medidas) → Smart Quote → checkout → pedido persistente → panel privado (estados, costos) → seguimiento del cliente.

Limitación central: **no existe regla comercial de precio por talla**, por lo que toda cotización y pedido tiene **precio provisional** (precio base del catálogo). No hay pagos reales ni descuento Bitcoin.

## 2. Stack

| Elemento | Detalle |
|---|---|
| Lenguaje / framework | Python 3.12, Django 5.2 |
| Base de datos | SQLite (`db.sqlite3`, no versionado) |
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
    services.py  precio base, cotización, creación de pedido, transiciones, costos
    assistant.py asistente determinista
    migrations/  0001–0006
    tests.py, test_panel.py, test_flow.py, test_assistant_costs.py
  templates/tienda/   base, inicio, productos, detalle, smartfit(_resultado), smartquote,
                      checkout, order, assistant, panel_login, panel_orders, panel_order
  static/tienda/      css/style.css, js/script.js, img/ (5 imágenes)
docs/                 guías, checklist, ensayo, este informe
README.md
```

## 4. Modelo de datos

```
DogProfile 1 ──< Quote 1 ──0..1 Order 1 ──< OrderEvent
```

- **DogProfile:** `public_id` (UUID), `name`, `breed`, `weight_kg` (Decimal 5,2), `back_length_cm`, `chest_girth_cm`, `neck_girth_cm` (opcional; Decimal 5,1), `created_at`.
- **Quote:** `public_id`, `dog` (FK PROTECT), `product_slug`, `base_price` (Decimal 10,2), `total_price` (nulo), `pricing` (`provisional`/`final`), `status` (`draft`/`accepted`/`cancelled`).
- **Order:** `public_id`, `quote` (OneToOne PROTECT), `total`, `price_is_provisional`, datos del cliente (`customer_name`, `customer_email`, `customer_phone`, `country`, `city`, `address`), `snapshot` (JSON), `status`, `payment_status`, `production_status`, `shipping_status`, `payment_reference`, `estimated_cost`, `actual_cost`, `cost_notes`, `created_at`. Número de pedido: `WK-<pk 6 dígitos>`.
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

- **Precio en el servidor:** `services.get_base_price(slug)` lee `PRODUCTOS` y convierte `"$650"` a `Decimal`. El navegador solo envía la clave del producto; precio, estado y tipo enviados se ignoran (hay prueba).
- **Smart Fit:** unidades de entrada kg/lb y cm/in, convertidas y redondeadas (ROUND_HALF_UP) a kg/cm antes de guardar. Rangos plausibles provisionales, aplicados tras convertir: peso 1–40 kg, lomo 10–100 cm, pecho 15–120 cm, cuello 10–70 cm.
- **Cotización:** siempre provisional; el desglose muestra precio base y "Size adjustment: not calculated yet". Una cotización borrador igual (perro + producto) se reutiliza.
- **Checkout:** valida correo, teléfono (7–15 dígitos), longitud de campos. `create_order` corre en transacción, con restricción única por cotización: reenvíos devuelven el pedido existente. Recalcula el total desde el catálogo y guarda un `snapshot`.
- **Estados:** `status` (pending/confirmed/cancelled), `payment_status` (unpaid/paid), `production_status` (not_started/in_production/completed), `shipping_status` (not_shipped/shipped/delivered). Independientes; crear el pedido no lo marca pagado.
- **Transiciones** (supuestos técnicos sin aprobación del negocio): secuenciales y sin retrocesos; no enviar antes de completar producción; pedido enviado no se cancela; cancelado no cambia; marcar "paid" exige referencia (registro manual, sin pasarela). Cada cambio crea un `OrderEvent`.
- **Costos:** prioridad costo real > costo estimado cargado > objetivo provisional de $175 (nunca presentado como costo comprobado). Margen = total − costo. Solo visible en el panel.
- **Seguimiento al cliente:** explica los estados y lista actualizaciones sin notas, referencias ni nombres de staff.
- **Asistente:** reglas y palabras clave sobre el catálogo. Responde precios y descripciones reales, recomienda por ocasión y guía a Smart Fit. Para envíos, pagos, descuentos, devoluciones y estado de pedidos responde que no tiene información. Pide aclaración si se mencionan varios productos. No escribe datos.
- **Concurrencia:** SQLite con `transaction_mode=IMMEDIATE` y `timeout=20`, corrección de un error 500 "database is locked" hallado en el ensayo.
- **IDs públicos:** UUID en todas las URLs de perfil, cotización y pedido; los ids numéricos devuelven 404.

## 7. Seguridad

Implementado: CSRF en todos los POST; panel solo para `is_staff` activo (anónimo → login, sin permisos → 403); escape automático de plantillas; entrada del asistente limitada a 200 caracteres; `DJANGO_SECRET_KEY` por variable de entorno; sin credenciales ni secretos en el repositorio.

Pendiente / limitaciones: sin límite de intentos de login; `DEBUG=True` y `ALLOWED_HOSTS=[]`; sin HTTPS ni cookies seguras; el cliente accede a su pedido solo por UUID (sin cuenta ni verificación); se guardan datos personales (nombre, correo, teléfono, dirección) sin política de privacidad ni retención definidas; sin correos.

## 8. Pruebas

`manage.py test`: **82 pruebas, todas OK** (tests.py 35, test_panel.py 20, test_flow.py 8, test_assistant_costs.py 19). Cubren catálogo, validación y persistencia de Smart Fit, conversión de unidades, cotización y precio no manipulable, checkout (validación, idempotencia, snapshot, recálculo), permisos del panel, búsqueda y filtros, transiciones válidas e inválidas, costos, asistente, fugas de datos internos, CSRF y flujo completo.

Ensayo manual (clon limpio del remoto, Windows 10, `runserver`, navegador integrado): flujo completo ejecutado y documentado en `docs/task-12-ensayo-y-alcance.md`. Hallazgos corregidos: error 500 por bloqueo de SQLite en envíos simultáneos y texto contradictorio "Paid — no payment has been collected".

**No verificado:** aspecto visual (no hubo capturas de pantalla), otros navegadores y dispositivos reales, accesibilidad, producción, carga.

## 9. Historial de commits (main)

| Commit | Contenido |
|---|---|
| `aa1e6bf` | Copia limpia de `web/` desde el ZIP |
| `cf079b3` | Modelos (Task 2) y Smart Fit (Task 3) |
| `4ca699f` | Smart Quote provisional (Task 4) |
| `7784c63` | Checkout y pedidos, UUID públicos (Task 5) |
| `afaac7c` | Panel privado, transiciones, costos (Task 6) |
| `b1d5592` | Pruebas de flujo, guía técnica, guion de demo (Task 7) |
| `50c8a5f` | Asistente, costos editables, seguimiento, README (Tasks 9–11) |
| Task 12 | Ensayo, correcciones de concurrencia y texto, congelación de alcance |

## 10. Decisiones pendientes del negocio

1. Fórmula o tabla de precio por talla/peso/materiales y aplicación del tope de $850.
2. Descuento Bitcoin: tasa comercial vigente, base elegible, exclusión de envío.
3. Costos reales de fabricación (el objetivo de $175 no está comprobado).
4. ¿Se puede producir sin pago registrado o con precio provisional?
5. Qué productos requieren contorno de cuello.
6. Política de envíos, devoluciones y privacidad.
7. Aprobación de las reglas de transición de estados.
8. Pasarela de pago real, si se desea (costos, credenciales).

## 11. Preguntas sugeridas para la revisión

- ¿Es adecuado un diseño de pedido con snapshot JSON más estados independientes para evolucionar a pago real?
- ¿Qué cambios mínimos hacen falta para producción (PostgreSQL, secretos, HTTPS, throttling de login, correos transaccionales)?
- ¿Conviene mover el catálogo a base de datos cuando existan tallas y variantes?
- ¿Cómo integrar un asistente basado en LLM manteniendo "solo datos del catálogo" y sin exponer datos personales?
