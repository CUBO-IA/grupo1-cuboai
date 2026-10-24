# 00 · Auditoría inicial (F0)

Fecha: 2026-10-22 · Ejecutada por Fluso en sandbox remoto (linux/arm64, Python 3.11, Django 5.2.18).

## Repositorio, ramas y PR verificados

| Hecho comprobado | Valor |
|---|---|
| Origen | `CUBO-IA/grupo1-cuboai` (público, accesible vía API) |
| Fork autorizado | `dede2812/grupo1-cuboai` (público, escritura vía MCP GitHub) |
| `main` | commit `68f50327de` |
| PR #1 (abierto, draft) | `proposal/wk-atlas-and-architecture` @ `7168f7f5b8` — **solo docs**: 11 documentos de planificación en `docs/proposal/` (PRD, arquitectura, auditoría, marca, backlog). Integrados a esta rama como referencia. |
| PR #2 (abierto, draft) | `feature/homepage-premium` @ `fe3c83ab60` — homepage premium: `views.inicio` con 4 destacados del catálogo, sección destacados en `inicio.html`, CSS. **Integrado como base de esta rama.** |
| Rama de este trabajo | `feature/fluso-kingdom-mvp` (nace de `feature/homepage-premium`) |

Decisión registrada: construir sobre `feature/homepage-premium` (incluye `main` + PR #2) por ser
el trabajo de código más reciente; el contenido documental de PR #1 se incorpora en `docs/proposal/`.
Ninguno de los dos PR estaba fusionado; ambos quedan abiertos para revisión del equipo.

## Qué se encontró (inventario real)

- Proyecto Django 5 en `web/` con una sola app `tienda` (~6,900 líneas), SQLite.
- Catálogo de 8 productos como **dict en código** (`tienda/catalog.py`), fotos reales en `static/tienda/img/`.
- Modelos existentes: DogProfile, Cart, Quote, Order, OrderEvent, OrderLine, ProductCost,
  MaterialLine, ProductMeasurement, SizeRange, ProductPaymentRule.
- Flujos operativos: Smart Fit (medidas → talla de referencia), Smart Quote (cotización provisional),
  carrito, checkout con revisión, pedido con estados separados (pago/producción/envío),
  descuento Bitcoin 15 % pendiente de verificación, panel de staff (pedidos, pagos, medidas, costos),
  asistente **determinista por reglas** (`tienda/assistant.py`, sin IA generativa).
- 289 pruebas existentes, **todas en verde** (21.6 s) al clonar — evidencia F0.
- Migraciones 0001–0019 aplican limpio en base nueva.
- Interfaz histórica en inglés; diseño base (PR #2 añade homepage premium).

## Qué se ejecutó

| Acción | Resultado |
|---|---|
| `pip install "Django>=5.0,<6.0"` en venv nuevo | OK (5.2.18) |
| `manage.py migrate` en base vacía | OK, 19 migraciones |
| `manage.py test` (suite histórica) | **289 tests OK** |
| Lectura completa de modelos, vistas, servicios, urls, plantillas base | OK |

## Demo / manual / real (estado heredado)

- Pagos: **manual + Bitcoin manual** (verificación del equipo); PayPal/tarjeta figuran como demo no disponible. Ninguna pasarela electrónica real conectada.
- Envío: sin matriz de zonas; "por confirmar" honesto en desgloses.
- IA: **inexistente** (asistente por reglas). El requisito P0 de IA real no estaba cubierto.
- Multi-tienda: inexistente (una sola tienda, sin tenant).
- Memoria/consentimiento: perfiles de perro por sesión, sin modelo de consentimiento.

## Riesgos reales identificados

1. Catálogo en código (no en DB) → sin multi-tienda ni inventario por variante. *(Resuelto en F2: catálogo normalizado en `reino`.)*
2. Precio por talla provisional (regla comercial pendiente del negocio). **Se preserva como está**: las cotizaciones siguen siendo provisionales.
3. SQLite no evidencia concurrencia real → las pruebas de bloqueo deben re-ejecutarse en PostgreSQL en staging (ver 05).
4. El asistente por reglas no cumple la puerta de aceptación de IA real (§2 del diseño). *(Resuelto en F6 con adaptador + orquestador; ver 03.)*
5. Sin RLS/PostgreSQL aún: aislamiento por capa de servicio + pruebas A13/A26 (ver 02).

## Estado de PR #2 confirmado

Integrado: homepage premium conservada y absorbida por el nuevo diseño Royal Editorial
(la home nueva usa sus 4 destacados desde el catálogo en DB). Sus archivos originales
(`tienda/views.py`, `templates/tienda/inicio.html`, `static/tienda/css/style.css`) quedan intactos
y sus flujos legacy operan sin cambios.
