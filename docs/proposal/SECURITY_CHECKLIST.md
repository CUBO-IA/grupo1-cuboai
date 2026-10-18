# SECURITY_CHECKLIST — Wiener Kingdom (staging hardening)

> Estado de la auditoría: DEBUG=True, ALLOWED_HOSTS=[], SECRET_KEY por defecto,
> sin rate-limiting, sin HTTPS. CSRF y staff_required ya presentes.

## 1. Checklist mínimo de producción (P0 — antes de cobrar)
| # | Control | Estado actual | Acción |
|---|---|---|---|
| S-01 | DEBUG=False | ❌ True | fijar por entorno |
| S-02 | ALLOWED_HOSTS | ❌ [] | dominio(s) exactos |
| S-03 | SECRET_KEY externo | ⚠️ default en código | DJANGO_SECRET_KEY de env, fuera del repo |
| S-04 | HTTPS + cookies seguras | ❌ | proxy TLS, SECURE_SSL_REDIRECT, CSRF/SESSION secure |
| S-05 | Rate limiting login | ❌ | límite en /panel/login/ |
| S-06 | Cabeceras seguridad | ❌ | HSTS, X-Content-Type-Options, etc. |
| S-07 | Backups + restauración probada | ❌ | cron + test de restore |
| S-08 | Observabilidad + logs | ⚠️ parcial | logs de errores y auditoría de transiciones |
| S-09 | Respuesta a incidentes | ❌ | runbook básico |
| S-10 | Secretos fuera del repo | ⚠️ | confirmar sin credenciales versionadas |

## 2. Controles ya presentes (no romper)
- CSRF middleware activo (CsrfViewMiddleware).
- `staff_required` en panel.py (403 para no-staff).
- Cotización siempre en servidor; precio nunca desde el navegador.
- SQLite `transaction_mode=IMMEDIATE` + timeout 20 (mitiga "database is locked").
- OrderEvent registra transiciones con autor.

## 3. Checklist de negocio/verificación (no automático)
- FR-06: checkout NUNCA auto-marca pagado.
- FR-07: BTC 15% solo elegible + verificación manual (discount_status).
- FR-09: producción no inicia sin pago verificado.
- FR-10: seguimiento sin exponer costos internos.
- Idempotencia: doble webhook no cobra dos veces (futuro PSP).
- Concurrencia: reserva de stock sin sobreventa (futuro inventario).

## 4. Aislamiento de agentes
- Workspaces separados, least privilege, sin secrets compartidos.
- NØVA y carpeta personal fuera del repo público.
- No instalar skills/MCP ni conectar cuentas sin autorización.