# 02 · Arquitectura y datos (F2)

## Arquitectura elegida

**Monolito modular Django** (confirmado sobre la base existente). Páginas renderizadas en
servidor; CSS propio con tokens (`reino.css`); JavaScript ligero sin framework
(`reino.js`, ~4 KB): menú accesible, galería, selección LookLab y chat asíncrono con
cancelación. No se introdujo HTMX/Alpine/React (decisión §8 del diseño).

```
Cliente (tienda y asesor) ─┐
                           ├─► Django (sesión + resolución de tienda en servidor)
Comerciante (panel) ───────┘        │
                                    ├─► servicios de comercio (fit/recommend/commerce/memory)
                                    ├─► orquestador de IA ─► proveedor LLM (config por entorno)
                                    │         └─► herramientas autorizadas ─► catálogo/políticas
                                    └─► PostgreSQL (staging/prod) · SQLite solo vista local
                                          └─► OutboxEvent (trabajo diferido recuperable)
```

## Apps y límites de responsabilidad

| App/paquete | Responsabilidad | Límites |
|---|---|---|
| `tienda` (histórica) | Smart Fit legacy, Smart Quote (S11), carrito/pedido legacy, panel de costos | Intacta; sus 289 tests en verde |
| `reino.models` | Merchant/Store, catálogo DB, variantes, FitRule, carrito/checkout/pedido nuevo, reservas, perfiles, medidas, consentimientos, looks, conocimiento, conversaciones, eventos, outbox, zonas | Todo cuelga de `store` (tenant) |
| `reino.tenancy` | Resolución de tienda por ruta + sesión | Fail-closed: sin tenant válido, 404 |
| `reino.services_fit` | Evaluación de talla por regla versionada | Medida desconocida ≠ compatible |
| `reino.services_recommend` | Elegibilidad → score → razones → bundles | Lo desconocido nunca cuenta como cumplido |
| `reino.services_commerce` | Carrito, checkout, pedido, reservas, transiciones, idempotencia | Servidor reconstruye importes |
| `reino.services_memory` | Consentimientos, preferencias, borrado de memoria | Revocar elimina derivados |
| `reino.ai` | Adaptador LLM, herramientas, orquestador, fallback | El modelo nunca decide permisos |

## Modelo de datos (tablas reales creadas en `reino`)

Merchant 1—n Store · Store 1—n Product 1—n Variant · Product 1—n FitRule (versionada) ·
Product 1—n ProductMedia · Store 1—n Cart 1—n CartItem → Variant · Cart 1—n CheckoutSession
1—n StockReservation → Variant · Store 1—n Order 1—n OrderItem (snapshot) y OrderEvent ·
Store 1—n RecipientProfile 1—n Measurement · Consent (store+session+finalidad+versión) ·
Preference → Consent · MemorySummary · Look · KnowledgeDocument · AIConversation 1—n
AIMessage · RecommendationEvent · OutboxEvent · ShippingZone · MerchantMember (user+merchant
único, rol).

Reglas protectoras implementadas:
- `unique_together`: (store, slug) producto; (product, sku) variante; (product, version)
  FitRule; (cart, variant, recipient) línea; (user, merchant) membresía.
- `idempotency_key` único en CheckoutSession y Order (doble clic = misma operación, A18).
- Referencias de pedido no secuenciales: `public_id` UUID + `access_token` UUID para
  invitados (A25); `reference` visible tipo `WK-000001` no autentica.
- Snapshots: OrderItem conserva título/SKU/precio; editar catálogo no altera pedidos.
- Stock nunca negativo: descuento dentro de `select_for_update` en orden estable de filas;
  disponibles = stock − reservas activas vigentes.

## Aislamiento (multi-tenant)

- La tienda se deriva de la ruta `/s/<slug>/` validada en servidor; nunca del modelo ni del cliente.
- Toda consulta de servicio filtra por `store` resuelto; perfiles además por `session_key`.
- Pruebas: A13 (productos/perfiles homónimos no cruzan), A26 (staff ajeno → 403),
  carritos separados por tienda, pedidos no cruzan.
- **Pendiente staging:** PostgreSQL RLS como defensa adicional antes de exposición a
  comercios externos; rol de aplicación sin bypass (ver 05, limitaciones).

## Índices creados (implícitos por constraints + db_index)

`(store, slug)` único · `(product, sku)` único · `session_key` en Cart/RecipientProfile/
AIConversation · `reference` en Order · `request_id` en RecommendationEvent · UUIDs únicos.

## Migración de la base existente

Esquema **aditivo**: `reino.0001_initial` crea tablas nuevas sin tocar `tienda_*`.
El catálogo histórico se siembra con `python manage.py seed_demo` (creación controlada y
repetible: borra solo datos `reino` y recrea). Los pedidos/cotizaciones históricos de
`tienda` no se tocan; el flujo legacy sigue escribiendo en sus tablas.
No se recreó ningún producto, pedido o identificador existente.

## Concurrencia

- Reservas: `prepare_checkout` bloquea variantes con `select_for_update()` en orden de pk,
  valida stock − reservas vigentes y crea reserva de 10 minutos (configurable
  `REINO_RESERVATION_MINUTES`). A17 probado en SQLite con 2 hilos (test_transactional) —
  **debe re-ejecutarse en PostgreSQL en staging** (SQLite serializa escrituras; evidencia
  parcial, declarada).
- `transaction_mode=IMMEDIATE, timeout=20` (config heredada) evita falsos "database is locked".
- Doble clic/reintento: clave idempotente en sesión + constraint único → mismo pedido.
- Webhooks de pago: no aplica P0 (sin pasarela); el diseño de estados/outbox queda listo (F8).
