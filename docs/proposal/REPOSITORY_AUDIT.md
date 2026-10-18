# REPOSITORY_AUDIT — Wiener Kingdom (CUBO-IA/grupo1-cuboai)

> Modo: lectura. Commit auditado: `68f50327de47454a81f52cd476a772b03df8423a` (main).
> Fecha: 2026-10-17. Ningún archivo modificado; sin push, sin rama remota, sin PR.

## 1. Resumen ejecutivo (máx. 8 líneas)
- Django 5.2 + Python 3.12+, app `tienda` en `web/`, SQLite de desarrollo.
- Catálogo de 8 productos activos + 1 retirado (dog-sweater, solo histórico) en `tienda/catalog.py`.
- Flujo completo cliente: Smart Fit (medidas) → Smart Quote (cotización servidor, provisional) → carrito multiproducto → checkout → pedido persistente con 4 estados independientes.
- Panel privado staff (login Django, `is_staff`), pagos manuales, costos internos, descuento Bitcoin 15% sujeto a verificación manual.
- Asistente determinista por reglas (NO IA generativa).
- Suite de 11 archivos de tests presente. NO re-ejecutada en esta entrega (sin runtime Django disponible en el sandbox).
- Bloqueante: credencial GitHub no configurada en el agente → read-only confirmado; no es posible crear fork/PR todavía.

## 2. Árbol relevante
```
web/
├── config/            settings.py (DEBUG=True, ALLOWED_HOSTS=[]), urls.py, wsgi.py
├── manage.py
├── requirements.txt   Django>=5.0,<6.0 · gunicorn · whitenoise
├── static/tienda/     css/style.css (14KB), js/script.js (140B), img/ (fotos catálogo)
└── tienda/
    ├── catalog.py      PRODUCTOS (8 activos) + RETIRED_SLUGS
    ├── models.py       DogProfile, Cart, Quote, Order, OrderEvent, OrderLine,
    │                   ProductCost, MaterialLine, ProductMeasurement,
    │                   SizeRange, ProductPaymentRule
    ├── services.py     precio/cotización/pedido/transiciones/costos/descuento
    ├── panel.py        panel staff (staff_required)
    ├── views.py        catálogo, smart fit, quote, carrito, checkout, pedido
    ├── assistant.py    asistente guiado determinista
    ├── forms.py        SmartFitForm, CheckoutForm, CostForm
    ├── urls.py         rutas públicas + panel
    └── test_*.py       11 archivos de tests
```

## 3. Tabla YA EXISTE / FUNCIONA PARCIAL / FALTA / NO TOCAR

| Estado | Componente | Detalle |
|---|---|---|
| ✅ YA EXISTE | Catálogo | 8 productos activos con precios, materiales, fichas; 1 retirado histórico |
| ✅ YA EXISTE | Smart Fit | DogProfile métrico (kg/cm), validación de rangos, kg↔lb cm↔in, 5 perfiles/sesión |
| ✅ YA EXISTE | Smart Quote | Cotización SIEMPRE en servidor, provisional, tope UNIT_PRICE_CAP=$850, MAX_QUANTITY=10 |
| ✅ YA EXISTE | Carrito | Multiproducto, líneas=Quote, dedupe, actualizar cantidad, quitar, checkout |
| ✅ YA EXISTE | Pedido | Order con snapshot, 4 estados independientes (pedido/pago/producción/envío), OrderLine |
| ✅ YA EXISTE | Panel staff | staff_required, lista/filtros/búsqueda, ficha taller, costos, reglas de pago |
| ✅ YA EXISTE | Descuento BTC | 15% solo productos elegibles, PENDIENTE hasta verificación manual |
| ✅ YA EXISTE | Costos internos | ProductCost + MaterialLine, estimado vs real, margen; PRIVADO |
| ✅ YA EXISTE | Asistente | Determinista, solo catálogo + textos fijos, declara desconocido |
| ✅ YA EXISTE | Tests | 11 archivos test_* (carrito, panel, pagos, costos, spec comercial, flujo) |
| ⚠️ PARCIAL | Pagos | Solo métodos DEMO (paypal_demo/card_demo nunca pagan) + bitcoin manual. Sin PSP |
| ⚠️ PARCIAL | Precio por talla | Regla comercial NO definida → toda cotización es provisional |
| ⚠️ PARCIAL | Envío | Sin tarifa/zona/operador; shipping=None, tracking manual |
| ⚠️ PARCIAL | Seguridad | CSRF presente; pero DEBUG=True, ALLOWED_HOSTS=[], sin rate-limit, sin HTTPS |
| ⚠️ PARCIAL | Cuenta cliente | Sin auth de comprador; seguimiento vía UUID en URL |
| ❌ FALTA | PSP real / sandbox webhooks / idempotencia / conciliación | |
| ❌ FALTA | Logística contratada (tarifas, zonas, 3PL, devoluciones) | |
| ❌ FALTA | Analítica real con fuente/denominador | |
| ❌ FALTA | IA conectada a datos con grounding/permisos | |
| ❌ FALTA | Multivendedor / RBAC inter-tenant | |
| ❌ FALTA | Despliegue producción (gunicorn presente pero sin config hardening) | |
| 🔒 NO TOCAR | Reglas de precio/pago/descuento | Sin aprobación explícita |
| 🔒 NO TOCAR | Estados de pedido y semántica de transición | |
| 🔒 NO TOCAR | Catálogo y fotos originales | Fallback honesto, nunca imágenes generadas como fotos |
| 🔒 NO TOCAR | main | Read-only hasta fork+PR autorizado |

## 4. Riesgos y bloqueos concretos
1. **P0 — GitHub sin credenciales.** `github_identity_status` → `credentialState: unavailable`. No puedo crear fork/rama/PR. Pendiente: operador conecta GitHub (Settings → Agents → Tools).
2. **P0 — settings de desarrollo en producción** (DEBUG=True, ALLOWED_HOSTS=[], SECRET_KEY por defecto).
3. **P1 — Sin runtime Django en el sandbox.** Los 11 tests NO se re-ejecutaron; cualquier PR de código debe declarar "NO PROBADO" hasta levantar el entorno.
4. **P1 — Ortografía "Weiner/Weiner Kingdom".** El código usa "weiner-kingdom" en SECRET_KEY default; el nombre aprobado es "Wiener Kingdom". Resolver en PR de textos.
5. **P2 — Imágenes.** Algunas fotos (cable-knit-jumper-1.jpg 297KB, christmas-dog 306KB, wedding-dog 342KB) son grandes; revisar peso/Core Web Vitals sin perder origen.

## 5. Dependencias y permisos
- Necesario: conexión GitHub del operador + autorización de fork + PR draft.
- Runtime para tests: Python 3.12 + Django 5.2 local (no disponible en sandbox actual).
- No conectar PSP/cuentas/slack/discord/canva/gworkspace hasta autorización de alcances.

## 6. Próxima acción
Preparar PR **docs-only** en borrador (archivos nuevos en docs/proposal/), aplicable como patch cuando se otorgue escritura/fork.