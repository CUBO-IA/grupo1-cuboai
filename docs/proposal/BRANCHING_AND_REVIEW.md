# Protocolo de ramas y revisión

**Estado de acceso al 17/10/2026:** la cuenta GitHub conectada (`dede2812`) tiene `pull=true`, `push=false` en `CUBO-IA/grupo1-cuboai`. Por ello esta entrega **no realizó ninguna escritura en remoto, no creó PR y no modificó `main`**.

## Ramas planeadas

| Rama | Alcance | Gate |
|---|---|---|
| `proposal/wk-atlas-and-architecture` | Documentación, benchmark, requirements, Atlas y propuesta de UI | Equipo aprueba visión y prioridades |
| `feature/wk-visual-refresh` | Cambios incrementales en `web/templates` y `web/static`, sin cambiar flujos | Revisión UX y tests Django |
| `feature/wk-staging-hardening` | Seguridad, variables, infraestructura de staging | QA y aprobación de despliegue |
| `feature/wk-payments-sandbox` | Adaptador PSP sandbox, webhooks firmados, conciliación | QA seguridad y negociación comercial |
| `feature/wk-analytics-support` | Métricas de pedidos, tickets, panel colaborativo | Protección de datos y evidencia |
| `experiment/wk-innovation-lab` | AR/3D, carrito compartido, búsqueda visual, simulaciones | Mantener separado de checkout estable |

## Rama de esta entrega

La carpeta `repo-overlay/` contiene archivos nuevos; **no** reemplaza los existentes. Los compañeros pueden copiarlos a un clon en una rama creada desde el `main` actual y abrir PR en borrador. Las futuras integraciones deberán aparecer en PRs separados y más pequeños.

## Aplicación segura por un colaborador con permiso de escritura

```powershell
git clone https://github.com/CUBO-IA/grupo1-cuboai.git
cd grupo1-cuboai
git switch main
git pull --ff-only origin main
git switch -c proposal/wk-atlas-and-architecture
# Copia el CONTENIDO de repo-overlay a esta carpeta, conservando las rutas existentes.
git status
git add docs/proposal proposals/wiener-kingdom-next
git diff --cached --stat
git commit -m "docs: propose Wiener Kingdom business atlas and isolated experience lab"
git push -u origin proposal/wk-atlas-and-architecture
# En GitHub, crear PR draft hacia main. No hacer merge sin revisión.
```

Si GitHub deniega push, pedir al administrador acceso de escritura o trabajar desde un fork propio y PR hacia el repo de la organización.

## Revisión del PR

- Ningún archivo preexistente borrado o cambiado en la rama de propuesta.
- Sin secretos, datos de clientes, referencias a otros proyectos privados ni assets sin licencia.
- Preview marcado como conceptual.
- Para PRs de Django: ejecutar `python manage.py check`, `python manage.py test`, revisar migraciones y snapshot UX.
- Revisión por al menos una persona distinta de quien escribió el cambio.
