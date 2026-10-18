# BENCHMARK_AND_LESSONS — Referentes (sin copiar código)

> Propósito: extraer lecciones metodológicas verificables de dos repos de referencia,
> para aplicarlas a Wiener Kingdom SIN reutilizar código ni recursos sin revisar licencia.

## 1. dataMiner (mariomarroquin3/dataMiner)
**Qué es:** equipo multiagente (BoxLang AI) para analizar datos desconocidos: subir archivo → anonimización → diagnóstico → perfilado → SQL → ML → verificación → informe HTML.

**Lecciones aplicables a Wiener Kingdom:**
| Lección | Aplicación en WK |
|---|---|
| **Hechos separados de interpretaciones.** Cada "hecho" lleva su SQL/consulta y se re-ejecuta para marcar ✓/✗. | En el panel de analítica futura: cada KPI con fuente, período y query; nunca mock como real. |
| **Verificación automática de afirmaciones.** No confiar en la respuesta del agente; re-ejecutar la evidencia. | QA/security re-ejecuta tests y revisa transiciones de pedido, no solo lee el código. |
| **Output estructurado nativo + fallback a parseo.** Declara qué formato se usó. | Handoffs y reportes con esquema fijo y declaración de formato. |
| **Modo compacto vs completo con las MISMAS tools.** Menos llamadas, mismo resultado. | Agentes WK con least privilege; no inflar el equipo de agentes sin caso de uso. |
| **Ningún agente conoce el dataset de antemano.** | Agentes con workspace separado y sin secretos compartidos. |
| **Traza de todo lo que hizo el equipo, visible en UI.** | OrderEvent + log de auditoría; trazabilidad de acciones de agentes. |
| **Tabla honesta "qué está probado y qué no".** | El atlas y los handoffs deben distinguir PROBADO / PARCIAL / NO PROBADO. |

**No copiar:** el pipeline BoxLang, los .bat, la lógica de anonimización. Solo la disciplina de evidencia.

## 2. boxlang-second-brain (CUBO-IA/boxlang-second-brain)
**Qué es:** módulo reutilizable Pure BoxLang (cuentas, espacios, sesiones, permisos, biblioteca privada) con desarrollo por fases, evidencia de cada fase y aceptación sintética autorizada.

**Lecciones aplicables:**
| Lección | Aplicación en WK |
|---|---|
| **Fases con alcance acotado y "Verificada en su alcance".** No acreditar lo no probado. | Sprints WK con Definition of Done explícito y "NO PROBADO" si no se ejecutó. |
| **Tests deterministas separados de la aceptación real de proveedor.** | Tests Django separados de pruebas PSP reales (sandbox) y de llamadas IA reales. |
| **Aceptación sintética autorizada con proveedor real, con coste medido.** | Solo PSP sandbox; cualquier llamada real requiere autorización y presupuesto. |
| **Opt-in facturable para IA (BUDGET_DAILY_USD, ledger persistido).** | Agentes IA con presupuesto diario y ledger; nunca gasto silencioso. |
| **Origen exacto (APP_ORIGIN) + cookies Secure + no publicar directo a Internet.** | Hardening de producción WK: HTTPS, ALLOWED_HOSTS, cookies seguras. |
| **Migraciones versionadas e idempotentes.** | Migraciones Django reversibles y probadas antes de staging. |
| **No guardar claves en archivos versionados.** | Secretos fuera del repo; NØVA y credenciales nunca al repo público. |

**No copiar:** el código BoxLang/Next.js, la estructura de cuenta/biblioteca. Solo la disciplina de fases y evidencia.

## 3. Decisión metodológica para WK
Adoptar de ambos: **fases con alcance acotado, hechos verificables, tests deterministas, permisos por agente, presupuesto explícito y handoff estructurado.** No adoptar: reescritura de stack (Django se conserva), ni agentes sin caso de uso.