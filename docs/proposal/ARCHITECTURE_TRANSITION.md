# Arquitectura incremental — respetar Django

```mermaid
flowchart LR
 Buyer[Comprador] --> UI[Plantillas Django / CSS y JS]
 Staff[Equipo] --> Panel[Panel staff Django]
 UI --> Views[Views / forms]
 Panel --> Services[services.py]
 Views --> Services
 Services --> Models[Order / Quote / DogProfile / Costs]
 Models --> DB[(SQLite desarrollo -> PostgreSQL si se aprueba)]
 Services -. futuro .-> Payment[PSP sandbox adapter]
 Services -. futuro .-> Logistics[Envíos]
 Services -. futuro .-> Analytics[Eventos y Pulse]
 AI[OpenClaw desarrollo, separado] -. PR revisado .-> Repo[GitHub]
 Repo -. preview .-> Staging[Servidor de staging]
```

## Razones para NO reescribir el núcleo

Conservar validaciones, reglas de cálculo, estados de producción/pago y suite extensa del equipo. La interfaz puede evolucionar sin sustituir contratos ni migraciones existentes.

## Evolución recomendada

1. Diseño visual y accesibilidad en plantillas actuales.
2. Aislamiento config dev/staging/prod y logs.
3. Integraciones a través de adapters independientes.
4. Postgres + colas tras necesidad, no por moda.
5. API y SPA/PWA opcionales cuando los nuevos clientes y métricas lo justifiquen.

## Compatibilidad Vercel

Vercel puede alojar demos estáticas y frontends elegibles. **No asumir que desplegar el HTML demo en Vercel convierte Django en aplicación productiva**. El backend Django, BD persistente, jobs, medios y sesiones requieren arquitectura y hosting adecuados, que podría ser distinto o complementario. El plan Hobby no debe usarse para ventas comerciales si sus condiciones lo excluyen.
