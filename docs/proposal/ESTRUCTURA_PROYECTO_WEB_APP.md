# Estructura propuesta para el proyecto / web / aplicación

## Estado del repositorio existente

**Fuente de verdad:** `CUBO-IA/grupo1-cuboai`, rama `main`, aplicación **Django** en `web/`. No se eliminan, mueven ni sobrescriben sus archivos.

```text
CUBO-IA/grupo1-cuboai/
├── README.md                                  # EXISTENTE, NO TOCAR
├── docs/                                      # EXISTENTE, NO TOCAR
│   └── proposal/                              # NUEVO (esta propuesta)
│       ├── MASTER_BUSINESS_ATLAS.md
│       ├── BRAND_SYSTEM.md
│       ├── ASSETS_VISUALES_Y_USO.md
│       ├── PROJECT_WEBSITE_REQUIREMENTS.md
│       ├── REPOSITORY_AUDIT.md
│       ├── BENCHMARK_AND_LESSONS.md
│       ├── ROADMAP_90_DAYS.md
│       ├── ARCHITECTURE_TRANSITION.md
│       ├── BRANCHING_AND_REVIEW.md
│       ├── AI_HANDOFF.md
│       ├── DEEPSEEK_PRO_MASTER_PROMPT.md
│       ├── OPENCLAW_TEAM_PROMPT.md
│       ├── ESTRUCTURA_PROYECTO_WEB_APP.md
│       ├── Wiener_Kingdom_ESTADO_Y_RUTA_FINAL.pdf
│       └── assets/
│           ├── marca_oficial_canva.png
│           ├── smart_fit_editorial.png
│           ├── arte_editorial_atlas.png
│           └── estado_visual_complementario.png
├── web/                                       # EXISTENTE - DJANGO REAL
│   ├── config/
│   ├── tienda/
│   ├── templates/
│   └── static/
└── proposals/                                 # NUEVO (aislado, no reemplaza Django)
    └── wiener-kingdom-next/
        ├── index.html                        # DEMO comercial independiente
        ├── README.md
        └── assets/                           # Logo aprobado, hero y fallbacks
```

## Desarrollo futuro sin romper lo existente

1. PR 0 `proposal/wk-atlas-and-architecture`: agregar la estructura precedente (sin tocar `web/`).
2. PR 1 `feature/wk-brand-ui`: cambiar solo templates CSS y assets de marca mediante revisión del equipo, sin tocar servicios/pagos.
3. PR 2 `feature/wk-smart-fit-ux`: validar experiencia de medidas, sin modificar fórmula de precios no aprobada.
4. PR 3 `feature/wk-checkout-hardening`: seguridad, pruebas, validación y seguimiento.
5. PR 4 `feature/wk-payments-sandbox`: procesadores legalmente elegibles en modo de prueba y conciliación.
6. PR 5 `feature/wk-delivery-and-ops`: tarifas, despacho, tracking y devoluciones.
7. PR 6 `feature/wk-pulse-analytics`: métricas verificadas, nunca inventadas.
8. PR 7 `feature/wk-concierge-ai`: IA con RAG, evaluaciones, permisos mínimos y escalamiento humano.
9. PRs experimentales posteriores: carrito colaborativo, fabricación regional y experiencias inmersivas si métricas lo justifican.

**No migrar a Next.js por impulso.** Conservar Django mientras el equipo y la base de datos actuales funcionen; evaluar frontend desacoplado solo con contratos, presupuesto y pruebas.

## Orquestación de herramientas

- **OpenClaw** gestiona agentes de desarrollo, genera planes y archivos, coordina QA; no aloja la tienda.
- **GitHub** es la fuente de verdad de código, cambios, reviews y CI; un PR es obligatorio para integrar.
- **Vercel** puede servir previews estáticas / frontends compatibles; no sustituye el hosting Django+PostgreSQL. Hobby no es para la tienda comercial.
- **Canva** guarda el diseño de identidad editada; el PNG de referencia se copia a `assets`.
- **Google Workspace** guarda entrevistas/presupuestos; **Slack** trabajo interno; **Discord** testers/comunidad bajo autorización.
- **🧭 NØVA** es tu coordinador personal y NO se publica en la org CUBO-IA.
