# AGENT_MATRIX — Roles y permisos Wiener Kingdom

> Organización mínima y necesaria dentro de los permisos disponibles. Least privilege.
> Coordinador asigna y verifica; NO programa todo. QA revisa al constructor.

## 1. Matriz de roles
| Rol | Responsabilidad | Permisos (mínimo) | Denegaciones |
|---|---|---|---|
| **wk-director** (coordinador) | Orquesta, asigna, verifica con pruebas, reporta a NØVA | Leer repo, asignar tareas, leer outputs de agentes | No push/merge, no secrets, no programar todo |
| **wk-archivist** | Contexto fuente de verdad, requisitos contradictorios, memoria de decisiones | Leer docs + repo | No escribir código |
| **wk-product** | PRD, issues, backlog, alcance | Leer repo, escribir docs de producto | No tocar código |
| **wk-django** | Backend Django, tests, migraciones | Leer/escribir rama feature, correr tests | No tocar main, no cambiar pagos/precios |
| **wk-ux** | Templates, CSS, accesibilidad, marca | Leer/escribir templates/static en rama | No tocar lógica backend |
| **wk-quality** (QA/security) | Revisión independiente, pruebas negativas, bloqueo de merge | Leer todo, correr tests, reportar | No aprobar su propio código |
| **wk-commerce** | Estados de pago manual, adaptadores PSP sandbox, investigación de proveedores | Leer, prototipar en sandbox | No mover dinero real, no auto-paid |
| **wk-analytics** | Definiciones de KPI con denominador, contratos de eventos | Leer, escribir specs de eventos | No presentar mock como real |
| **wk-release** | CI, changelog, staging readiness | Leer, configurar CI en rama | No deploy a producción sin aprobación |

## 2. Separación por workspace
- Cada agente: workspace separado, `agentDir` propio, sandbox.
- Revisores (wk-quality, wk-archivist): solo lectura.
- Sin credenciales compartidas; sin filesystem irrestricto.
- No conectar Slack/Discord/Canva/Google Workspace/PSP hasta autorizar alcances.

## 3. Flujo de trabajo
```
Issue → contexto (archivist) → plan (product) → rama (django/ux)
  → código + tests → QA/security → draft PR → aprobación compañeros
  → staging → deploy (solo autorizado)
```

## 4. Reglas de coordinación
1. wk-quality revisa al constructor (pruebas negativas de permisos, logs, presupuesto).
2. Ningún agente instala skills/MCP ni conecta cuentas sin autorización.
3. No exponer secretos; NØVA y carpeta personal quedan fuera del repo.
4. Reporte agregado a NØVA con evidencia (no declarar terminado sin pruebas).