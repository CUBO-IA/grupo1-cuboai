# Wiener Kingdom — Project / Website Requirements v2

## 1. Project Context

Wiener Kingdom es una tienda Django existente de confección/accesorios para dachshunds. Backend en `web/config`, aplicación en `web/tienda`; catálogo, Smart Fit, Smart Quote provisional, carrito, pedidos, pagos con registro manual y panel staff. La visión estratégica de largo plazo es convertir el motor en una plataforma modular comercial, sin destruir el trabajo previo.

## 2. Objective

**Fase actual:** crear una experiencia boutique de ecommerce sobresaliente para productos de dachshunds, conservar el flujo de pedidos y preparar la base para tecnología avanzada (analítica, soporte IA, proveedores y fábrica secundaria, pagos internacionales bajo contratos). **No se pretende competir en capacidad logística con Amazon desde un MVP**: se compite en experiencia, especialización y confianza.

## 3. MVP Scope

**Mantener existente:** Django, catálogo de 8 productos activos, Smart Fit, cotizaciones, carrito y checkout actuales, panel, tests y migraciones. **Primera iteración propuesta:** design tokens, responsive, semántica accesible, catálogo editorial, estados de carga y error, transparencias de precio provisional, registro de cambios, QA. **Fase aparte:** pagos sandbox y hardening. **Fuera del MVP:** payment gateway real, marketplace abierto a terceros, custodia BTC, fabricación global, AR/VR, copagos, LLM conectado.

## 4. Functional Requirements

| ID | Requisito | Evidencia de aceptación |
|---|---|---|
| FR-01 | Preservar URL de inicio y catálogo | GET 200 + tests actuales |
| FR-02 | Mostrar 8 productos activos y fichas originales | Catálogo fuente consistente |
| FR-03 | Smart Fit valida y guarda medidas | Tests actuales + UX móvil |
| FR-04 | Cotizar solo en servidor, precio base provisional | No manipulable desde frontend |
| FR-05 | Carrito actualiza cantidades y evita duplicados | Suite carrito y concurrencia |
| FR-06 | Checkout muestra total y estado real sin fingir pago | Estado unpaid tras formulario |
| FR-07 | Bitcoin 15% solo si producto elegible y verificación | Test de descuento y estado |
| FR-08 | Operador staff registra referencia y transiciones | Permisos + OrderEvents |
| FR-09 | Producción no comienza sin pago verificado | Rechazo de transición inválida |
| FR-10 | Historial de seguimiento sin costos internos | Test privacidad por pedido |
| FR-11 | Vista nueva mobile-first y teclado | Checklist WCAG + viewport 375px |
| FR-12 | UI separa muestras/estimaciones de datos reales | Etiquetas visibles |
| FR-13 | Asistente determinista no promete datos externos | Tests de respuestas no fundamentadas |
| FR-14 | Analítica futura define fuente y denominador | Contratos de eventos |
| FR-15 | Pagos futuros requieren sandbox, webhook firmado e idempotencia | Tests de doble webhook |
| FR-16 | Soporte futuro permite escalar a humano con contexto permitido | Test privacidad y handoff |
| FR-17 | Fabricación secundaria futura valida cotización, QC, SLA y capacidad | Contratos y simulación separada |
| FR-18 | Multiusuario futuro aísla pedidos por vendedor | RBAC y tests inter-tenant |
| FR-19 | Prototipo no afecta operaciones de Django | Sin imports/rutas nuevas |
| FR-20 | Identidad unifica spelling solo tras aprobación | Revisión de textos |

## 5. Non-Functional Requirements

- Django 5.2 y Python 3.12+ compatibles con versión del repositorio.
- Seguridad de login, CSRF, DEBUG off y ALLOWED_HOSTS configurado en producción, HTTPS, secretos externos, rate-limiting, privacidad, backups.
- Ninguna captura o dato de tarjeta es almacenada por el frontend.
- Accesibilidad WCAG 2.2 AA como meta verificable; teclado, foco, reduced motion, contrastes.
- Performance: LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 en usuarios reales donde sea posible.
- Compatibilidad: móviles desde 375px y desktop, Chrome/Firefox/Safari tras pruebas.
- Fiabilidad: Django tests existentes deben permanecer verdes; migraciones reversibles, backups probados.
- Telemetría y consentimiento para analítica, nunca captura de secretos.
- Aislamiento de agentes personales y datos fuera del repo público.

## 6. Expected Initial GitHub Structure

Mantener **sin tocar** el árbol existente. Añadir únicamente:

```text
CUBO-IA/grupo1-cuboai/
├── README.md                      (EXISTENTE — no modificar)
├── web/                           (EXISTENTE — no modificar en la propuesta)
│   ├── config/
│   ├── tienda/
│   └── templates/
├── docs/                          (EXISTENTE)
│   └── proposal/                  (NUEVO)
│       ├── MASTER_BUSINESS_ATLAS.md
│       ├── REPOSITORY_AUDIT.md
│       ├── BRAND_SYSTEM.md
│       ├── BRANCHING_AND_REVIEW.md
│       ├── BENCHMARK_AND_LESSONS.md
│       ├── PROJECT_WEBSITE_REQUIREMENTS.md
│       └── ...
└── proposals/
    └── wiener-kingdom-next/      (NUEVO, demo aislada)
        ├── index.html
        ├── assets/
        └── README.md
```

## 7. Work Flow

Idea → revisión documental → issue → plan y estimación → rama → diseño → desarrollo con tests → QA independiente → PR draft → aprobación por compañeros → merge manual → staging → nueva prueba → producción autorizada. Nunca push directo a main.

## 8. Instructions for the Agent

Leer repositorio antes de proponer refactor. No cambiar Django por Next.js. No cambiar precios finales, descuento, permisos, rutas o estados sin ticket aprobado. Separar prototipos y código integrado. No ejecutar herramientas externas o publicar datos sin permiso. Entregar diff, tests y riesgos. Analizar propuestas de dataMiner y Second Brain como inspiración metodológica, sin reutilizar código sin licencia.

## 9. Expected Output

Atlas, brand guide, demo visual con carrito/órdenes **simulados**, arquitectura de transición, documentación para desarrollador, suite que sigue pasando sobre repo real, PR draft con evidencias una vez autorizada escritura, y prompt para DeepSeek Pro que permita pasar luego a ChatGPT mediante archivos de contexto.

## 10. Success Conditions

- Ningún cambio en `main` sin revisión; cero archivos preexistentes borrados.
- Test Django exitoso después de integración; si no se ejecuta, el PR debe declarar **NO PROBADO**.
- Smart Fit y Smart Quote inalterados salvo aprobación explícita.
- Demo móvil con carrito, productos y orden de prueba; datos etiquetados como simulados.
- Checkout real no confirma pagos inexistentes.
- No mezclar credenciales ni espacio personal con repo colaborativo.
- Decisiones, PRD, arquitectura y handoff fáciles de retomar por otro modelo.


### Referencia visual unificada - revisión final
- Identidad oficial provisional: `docs/proposal/assets/marca_oficial_canva.png` (lámina de Canva seleccionada por el equipo).
- Imagen editorial de Smart Fit: `docs/proposal/assets/smart_fit_editorial.png`.
- No reutilizar los antiguos SVG de dachshund/caricaturas del overlay.
- La app debe usar las fotografías reales del catálogo original cuando estén disponibles y contar con fallback honesto. Nunca presentar imágenes generadas como fotografías del producto.
- No modificar el backend Django original sin pull request aprobado.
