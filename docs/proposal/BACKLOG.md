# BACKLOG — 20 issues listos para GitHub

> Estado: borrador. A crear en GitHub cuando exista fork/permiso de escritura.
> Etiquetas: docs / feat / chore / security / test / p1 / p2.

## Docs (PR docs-only primero)
1. **docs-only: REPOSITORY_AUDIT + ARCHITECTURE + AGENT_MATRIX** — añadir docs/proposal/ (archivos nuevos). No toca web/.
2. **docs-only: BRAND_SYSTEM + UI_CONTRACTS** — tokens y contratos; resolver conflicto de paleta.
3. **docs: BRANCHING_AND_REVIEW** — reglas de ramas/PR y Definition of Done.
4. **docs: BENCHMARK_AND_LESSONS** — lecciones de referentes (sin copiar código).

## Visual refresh (feature/wk-visual-refresh)
5. **feat: design tokens CSS** — variables --wk-* en style.css sin tocar lógica.
6. **feat: home premium responsive** — hero con foto real + Smart Fit destacado.
7. **feat: catálogo editorial grid** — ProductCards con fallback honesto de imagen.
8. **feat: ficha producto premium** — materiales + precio provisional etiquetado.
9. **feat: Smart Fit form accesible móvil** — errores claros, teclado.
10. **feat: checkout transparente** — total real, estado unpaid, BTC demo etiquetado.
11. **feat: estados vacío/error/loading** — skeleton, mensajes específicos.
12. **feat: accesibilidad WCAG 2.2 AA** — foco, contraste, reduced-motion, aria.

## Hardening (feature/wk-staging-hardening)
13. **security: DEBUG=False + ALLOWED_HOSTS + secretos externos** — settings por entorno.
14. **security: HTTPS + cookies seguras + cabeceras** — proxy TLS, HSTS.
15. **security: rate limiting en /panel/login/** — anti fuerza bruta.
16. **security: backups + restauración probada** — cron + test restore.

## Pagos sandbox (feature/wk-payments-sandbox, tras decisión legal)
17. **feat: PSP sandbox + webhooks firmados + idempotencia** — doble webhook no cobra dos veces.
18. **feat: conciliación y estados de pago** — sin auto-paid; verificación manual preservada.

## Tests/QA
19. **test: re-ejecutar suite Django** — registrar salida real o declarar NO PROBADO.
20. **test: pruebas negativas de permisos** — panel solo staff, costos no públicos, BTC solo elegible.

## Notas de aceptación
Cada issue incluye: criterio de aceptación + rama + test/evidencia + revisor. Los de pagos NO se ejecutan sin decisión legal y sandbox autorizado.