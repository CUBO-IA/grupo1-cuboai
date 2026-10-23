# STATUS · Wiener Kingdom / Reino Commerce

Actualizado: 2026-10-23 (segunda ronda: corrección de la auditoría del PR #3) ·
Rama: `feature/fluso-kingdom-mvp` · Base: `feature/homepage-premium` (`fe3c83ab60`)

## Estado por módulo

Estados permitidos: diseñado · implementado sin ejecutar · verificado en local · verificado en staging · bloqueado · futuro.

| Módulo | Estado | Evidencia |
|---|---|---|
| F0 Auditoría | **verificado en local** | docs/00; 289 tests base en verde al clonar |
| F2 Datos y aislamiento | **verificado en local** | migraciones `reino.0001-0002` + seed_demo; tests A13/A26 |
| F3 Núcleo de compra | **verificado en local** | R01–R06 corregidos; tests de auditoría + dataset AGG/IDM/ZON/DSC |
| F4 Tienda visual | **verificado en local** | capturas nuevas del commit final en 5 anchos (`docs/capturas/`) |
| F5 Recomendador + LookLab | **verificado en local** | R08–R10 corregidos; `FIT-*`/`BUD-*` del dataset; reveal E2E |
| F6 IA + memoria | **implementado y probado con proveedor falso; BLOQUEADO para modelo real** | R07/R11/R12 corregidos; tests A10–A16 + TXT/AIA; falta `REINO_AI_API_KEY` |
| F7 Panel comerciante | **verificado en local** (incluye editor de catálogo P0) | R13 corregido; `test_merchant_ops.py` (12 casos) |
| Alta asistida de comercio | **verificado en local** | `OnboardingTests`; checklist de activación verificado |
| F8 Integraciones (pasarela/logística) | **bloqueado** | sin cuenta sandbox elegible; pago manual+BTC manual operan con evidencia |
| F9 Calidad | **verificado en local** | **372 tests OK**; CI configurada; accesibilidad de teclado: ver evidencia |
| F10 Handoff | **verificado en local** | README + docs/00–07 + PR actualizado |

## Pruebas

- `python manage.py test` → **372 OK** (289 históricas + 83 reino) · ~25 s.
- Regresiones de la auditoría: 14/14 en `reino/tests/test_audit.py` (integradas
  sin cambiar su significado; fallaban en el commit `95df61f`).
- Dataset de evaluación versionado: `reino/tests/eval_dataset.json` — **81 casos
  identificables** (fit, presupuesto, descuento, idempotencia, zonas, memoria,
  roles/transiciones, validación de texto, stock agregado, acciones IA). La parte
  determinista corre en `test_eval_dataset.py` (en CI). La evaluación con
  proveedor REAL queda como comprobación explícita pendiente de clave.
- `makemigrations --check --dry-run`: sin cambios pendientes. `manage.py check`: 0 issues.
- Concurrencia PostgreSQL: `test_postgres.py` escrita (salta sin Postgres);
  este sandbox no tiene binarios de PostgreSQL → pendiente staging (bloqueo 3).
- CI: `.github/workflows/ci.yml` (suite completa + chequeo de migraciones).

## Corrección de la auditoría (23-oct-2026)

Matriz completa hallazgo→corrección→prueba→resultado: `docs/07_MATRIZ_AUDITORIA_R01_R13.md`.
13/13 hallazgos bloqueantes corregidos con sus 14 regresiones integradas; hallazgos
de interfaz corregidos con capturas NUEVAS del commit final en 360/390/768/1024/1440 px.

## Bloqueos concretos

1. **IA real (puerta de aceptación §2):** falta `REINO_AI_API_KEY`. Con clave, el
   asesor pasa a modo `ai` sin cambios de código; registrar la evaluación con
   modelo/versión/fecha/latencia/coste (sin secretos).
2. **Pasarela de pagos:** elegibilidad de cuenta (El Salvador) sin confirmar →
   operar pago manual + Bitcoin manual (ambos implementados y honestos).
3. **PostgreSQL/RLS en staging:** ejecutar `test_postgres.py` con conexiones
   reales; RLS requiere políticas y roles reales (no se afirma como existente).
4. **Tarifa San Salvador $3.50:** hipótesis pendiente de aprobación del negocio.

## Próximos pasos

1. Configurar `REINO_AI_API_KEY` en staging y ejecutar la evaluación real.
2. Levantar staging con PostgreSQL y correr `test_postgres.py` + restauración de backup.
3. Medición Web Vitals de campo en staging (los objetivos LCP/INP/CLS están en docs/05).
4. P1: CSV, reembolso parcial con montos, embeddings RAG, lookbook editorial,
   compra asistida por agentes externos (autorización delegada).

## Continuidad

Para reanudar: `cd web && python manage.py test` debe dar 372 OK;
`python manage.py seed_demo --reset` recrea los datos demo (destructivo, protegido);
`python manage.py process_outbox` drena trabajos diferidos. Este archivo refleja el
último commit de la rama. No contiene claves ni datos personales.
