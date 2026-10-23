# STATUS · Wiener Kingdom / Reino Commerce

Actualizado: 2026-10-23 (sandbox Fluso) · Rama: `feature/fluso-kingdom-mvp` · Base: `feature/homepage-premium` (`fe3c83ab60`)

## Estado por módulo

Estados permitidos: diseñado · implementado sin ejecutar · verificado en local · verificado en staging · bloqueado · futuro.

| Módulo | Estado | Evidencia |
|---|---|---|
| F0 Auditoría | **verificado en local** | docs/00; 289 tests base en verde al clonar |
| F2 Datos y aislamiento | **verificado en local** | migración `reino.0001` + seed_demo; tests A13/A26 |
| F3 Núcleo de compra | **verificado en local** | tests A17/A18/A22/A24/A25/A27/A29 + E2E HTTP |
| F4 Tienda visual | **verificado en local** | 26 capturas reales (`docs/capturas/`), recorrido móvil/desktop |
| F5 Recomendador + LookLab | **verificado en local** | tests motor (ocasión, presupuesto, fit, bundle); reveal E2E |
| F6 IA + memoria | **implementado y probado con proveedor falso; BLOQUEADO para modelo real** | tests A10/A11/A14/A15/A16 con fake; falta `REINO_AI_API_KEY` |
| F7 Panel comerciante | **verificado en local** (mínimo P0) | tests A26/A28; capturas |
| F8 Integraciones (pasarela/logística) | **bloqueado** | sin cuenta sandbox elegible; pago manual+BTC manual operan |
| F9 Calidad | **verificado en local** | 336 tests OK; accesibilidad/perf: ver pendientes |
| F10 Handoff | **verificado en local** | README + docs + PR |

## Pruebas

- `python manage.py test` → **336 OK** (289 históricas + 47 reino) · 22 s.
- Cobertura de la matriz A01–A32: tabla completa en `docs/05_CALIDAD_Y_DESPLIEGUE.md`.
- Capturas reales (Playwright, sandbox): `docs/capturas/` — 26 imágenes desktop 1440 + móvil 390,
  incluido flujo LookLab completo hasta la revelación.

## Bloqueos concretos

1. **IA real (puerta de aceptación §2):** falta `REINO_AI_API_KEY` (u otro proveedor
   compatible: `REINO_AI_BASE_URL`). Con clave, el asesor pasa a modo `ai` sin cambios de
   código. La batería de evaluación (80 casos) está preparada como patrón en
   `reino/tests/test_ai.py`.
2. **Pasarela de pagos:** elegibilidad de cuenta (El Salvador) sin confirmar → operar con
   pago manual + Bitcoin manual (ambos implementados y honestos).
3. **PostgreSQL/RLS en staging:** A17 debe re-ejecutarse allí; SQLite local no evidencia
   concurrencia completa.
4. **Tarifa San Salvador $3.50:** hipótesis pendiente de aprobación del negocio.

## Próximos pasos

1. Configurar `REINO_AI_API_KEY` en staging y ejecutar la batería de evaluación.
2. Ensayo de restauración de backup reaplicando revocaciones (A31).
3. Auditoría manual de accesibilidad (teclado/lector) y medición Web Vitals en staging.
4. P1: editor de catálogo, CSV, reembolso parcial con montos, embeddings RAG, lookbook.

## Continuidad

Para reanudar: `cd web && python manage.py test` debe dar 336 OK; `seed_demo` recrea los
datos demo; este archivo refleja el último commit de la rama. No contiene claves ni datos
personales.
