# BRANCHING_AND_REVIEW — Reglas de ramas y revisión

> Read-only en main hasta fork + PR draft autorizado. Nunca merge, force-push ni borrado de trabajo de compañeros.

## 1. Ramas
| Rama | Propósito | Contenido |
|---|---|---|
| `main` | protegida | inalterada salvo PR aprobado |
| `proposal/wk-atlas-and-architecture` | docs + preview aislado | solo archivos nuevos |
| `feature/wk-visual-refresh` | CSS/templates | sin lógica de pagos/precios |
| `feature/wk-staging-hardening` | seguridad | settings, headers, rate-limit |
| `feature/wk-payments-sandbox` | PSP sandbox | tras decisión legal |
| `feature/wk-shipping` | logística | tarifas, zonas, tracking |
| `experiment/wk-innovation-lab` | funciones avanzadas | aislado, con KPI |

## 2. Reglas de PR
1. PR docs-only en borrador PRIMERO (archivos nuevos, sin tocar web/).
2. Después PRs de código SEPARADOS con tests, uno por rama.
3. Nunca mezclar docs + backend + seguridad + innovación en un mismo PR.
4. Cada PR declara: archivos cambiados, tests ejecutados (comando + salida) o "NO PROBADO", riesgos.
5. Aprobación de compañeros antes de merge; sin merge propio.

## 3. Definition of Done
Criterios de aceptación + tests + seguridad + accesibilidad + documentación + observabilidad + revisión independiente + staging.

## 4. Denegaciones duras
- No push a producción, no merge, no force-push.
- No borrar trabajo de compañeros.
- No subir credenciales ni información personal de NØVA.
- No auto-marcar pagos; no PSP real sin autorización.