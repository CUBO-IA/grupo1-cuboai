# PROMPT DEEPSEEK PRO — WIENER KINGDOM / PROTOCOLO BUILD-REVIEW-HANDOFF

## OBJETIVO EN UNA FRASE
Transformar progresivamente la tienda **Wiener Kingdom** (ropa premium para dachshunds) en la experiencia de ecommerce más cuidada y en una base modular capaz de escalar en el futuro, SIN DESTRUIR EL CÓDIGO NI LAS DECISIONES COMERCIALES DEL EQUIPO.

## CONTEXTO VERIFICADO (FUENTE DE VERDAD)
Repositorio: https://github.com/CUBO-IA/grupo1-cuboai
Clon: https://github.com/CUBO-IA/grupo1-cuboai.git
Rama base: `main`
Framework: Django 5.2 / Python 3.12+, código existente en `web/`.
Funciones existentes: productos dachshund, catálogo de ocho artículos activos, Smart Fit (medidas), Smart Quote con precio base/provisional, carrito, checkout, pedidos persistentes, panel privado de staff, estados diferenciados de pago-producción-envío, costos, descuento Bitcoin del 15% sobre productos elegibles sujeto a VERIFICACIÓN MANUAL.
**No existe pasarela real activa.** PayPal y tarjeta en la web son DEMO. El asistente es determinista, no un modelo IA. `DEBUG=True` / SQLite son settings de desarrollo, no producción.

Repos de inspiración, SIN COPIAR código ni recursos sin revisar licencia:
- https://github.com/mariomarroquin3/dataMiner (agentes separados con traza, verificación de hechos, output estructurado y UX de alta calidad).
- https://github.com/CUBO-IA/boxlang-second-brain (desarrollo por fases, evidencia, aislamiento, tests, permisos y documentación).
No afirmes las razones oficiales del premio de un hackathon sin evidencia del jurado.

## VISIÓN Y MARCA
Nombre aprobado para la propuesta: **Wiener Kingdom**. Advertencia: plantillas originales usan `Weiner Kingdom` y la forma correcta se debe acordar con el equipo en PR.
Oferta de hoy: moda y accesorios de dachshund. Visión lejana: marketplace, SaaS para vendedores, IA de soporte y ventas, pagos internacionales, fabricación distribuida, logística regional, paneles colaborativos y simulador de negocio.
Marca premium original, navy #101E36, carmine #AF3635, burgundy #842F34, steel blue #366A91, silver #C5CBD5, ivory #FAF8F6. Logo conceptual corona geométrica + silueta dachshund. No copiar marcas ni personajes.

## REGLA INNEGOCIABLE DE GIT
NO trabajar directamente en `main`. NO modificar lo que construyeron tus compañeros sin PR y aprobación. NO hacer merge ni force-push. Inspeccionar repo y estado antes de crear ramas.
Ramas recomendadas:
- `proposal/wk-atlas-and-architecture` para docs y preview aislada;
- `feature/wk-visual-refresh` para integración CSS/templates;
- `feature/wk-staging-hardening` para seguridad;
- `feature/wk-payments-sandbox` para PSP sandbox;
- `experiment/wk-innovation-lab` para funciones avanzadas.
Primero PR docs-only en borrador con archivos nuevos; después PRs de código separados con tests. Si no hay permisos push, crear cambios locales y patch o PR desde fork propio con permiso, sin inventar publicación.

## INTERPRETACIÓN DEL ATLAS
Debes cubrir 37 capítulos de dirección, producto, construcción, negocio, ejecución y referencia, respondiendo 187 preguntas con contexto específico de Wiener Kingdom. Utiliza `docs/proposal/MASTER_BUSINESS_ATLAS.md` y `PROJECT_WEBSITE_REQUIREMENTS.md` cuando estén disponibles. La estructura global puede ser mucho más ambiciosa, pero cada función debe tener fase MVP/Beta/Lab y una prueba de valor. Diferencia hechos, hipótesis y propuestas. Siempre que veas supuestos no demostrados, no los conviertas en cifras verificadas.

## ARQUITECTURA PREFERIDA
**NO REESCRIBIR DJANGO POR NEXT.JS.** Mejorar Django en etapas. Mantener URLs, formularios CSRF, clases, estados, migraciones y suite existente. SQL/Postgres, Celery/Redis, frontend SPA y servicios externos son módulos OPCIONALES y posteriores, solo si el problema lo justifica.
Para la web mejorada, empezar por plantillas Django + CSS/JS accesible, componentes, formulario Smart Fit legible, fichas premium, carrito y checkout transparente. Demostrar con capturas móvil/desktop y pruebas de regresión.

## VENTA Y LOGÍSTICA
Prohibido fingir pagos: checkout no debe auto-marcar pedidos pagados. PSP solo sandbox y tras verificar jurisdicción y contratos. Bitcoin descuento 15% de productos elegibles sin envío debe permanecer según especificación existente salvo aprobación. Producción solo con pago verificado. No inventar tarifarios de envío, disponibilidad por país, costo de fabricación o política de devoluciones.
Investigar e implementar progresivamente: stock, fabricantes bajo demanda auditados, 3PL, delivery nacional, zonas/pickup, aduanas/Incoterms, idempotencia, reembolsos, seguridad, customer support y analítica real. Dividir cada componente en interfaz, backend, legal/operaciones, pruebas y costos.

## FEATURES DE VISIÓN AVANZADA
Design-to-Delivery, Smart Returns/Smart Fit, Product Passport, Live Shopping Rooms, AI Concierge, Seller Mission Control, Decision Theater (modelador de margen), Twin Cart (multiusuario), Visual Match (búsqueda por foto), Fabrication Mesh, XR Product Showroom y Agent Handoff. Todas en prototipos aislados y con KPI; no mezclar experimentos con venta real.

## ORGANIZACIÓN DE AGENTES
Separar roles: context archivist, product manager, Django architect, frontend UX, backend, QA-security, commerce/payments, data analyst, operations, legal-review checklist, release integrator. Coordinador asigna, no programa todo. Agente de QA revisa al constructor, pruebas negativas de permisos, logs y presupuesto. No instalar skills/MCP ni conectar cuentas sin autorización. No exponer secretos.

## OBJETIVO DE USAR AL MÁXIMO MI SESIÓN DEEPSEEK PRO
Priorizar decisiones costosas intelectualmente ahora, no crear contenido repetitivo ni comandos sin verificar. Operar en **sprints de alta densidad** y registrar al final de CADA sprint `AI_HANDOFF.md` con contexto, archivos, commits, pruebas, problemas, decisiones y 3 acciones siguientes. Así otro modelo puede continuar sin volver a leer el historial entero.

### SPRINT 0 — LECTURA CRÍTICA Y MAPA (PRIMERO)
1. Lee árbol actual, README, `docs/`, Django `views.py`, `services.py`, `models.py`, `panel.py`, `catalog.py`, templates, pruebas y `settings.py`.
2. Contrasta con los referentes y documenta qué aprender sin copiar.
3. Entrega tabla `YA EXISTE / FUNCIONA PARCIAL / FALTA / NO TOCAR`.
4. Registra riesgos concretos y costos, dependencias, permisos GitHub.
5. No modifiques código hasta que el mapa esté listo.

### SPRINT 1 — PLAN LISTO PARA CONSTRUIR
Elabora PRD, contratos de UI, design tokens, sitemap real, wireframes, módulos priorizados, datos, checklist de seguridad, mínimos de producción, matriz de agentes y roadmap 90 días. Incluye arquitectura Mermaid y 20 issues listos para GitHub. Revisión y acuerdo del alcance.

### SPRINT 2 — EXPERIENCIA ORIGINAL
En rama feature nueva implementa una pantalla de alto valor por PR: Home premium, catálogo, detalles, Smart Fit, carrito, checkout, panel. Testea antes/después. Sin romper endpoints, tests ni documentos existentes. No publiques producción.

### SPRINT 3 — PUNTA A PUNTA
Pruebas reales de integración en sandbox (sin dinero): medidas → cotización → carrito → checkout → pedido → aprobación staff → producción simulada → seguimiento. Validar web en 375/768/1440 px y accesibilidad. Problemas detectados + fix con evidencia.

### SPRINT 4 — INNOVACIONES Y OPERACIÓN
Prototipo separado de panel colaborativo, agent handoff con respuestas fundamentadas, seguimiento, servicio al cliente y simulador de márgenes. Presupuesto, métricas y pruebas. No llamar real ninguna función mock.

## FORMATO OBLIGATORIO DE CADA RESPUESTA (CONSUMO EFICIENTE)
Devuelve primero:
1. Resultado hecho (máximo 8 líneas).
2. Tabla de archivos cambiados y por qué.
3. Evidencia de tests COMPROBADA.
4. Riesgos/bloqueos.
5. Siguientes 3 pasos.
6. Contenido listo en archivos del repositorio; **NO copies documentos completos al chat** salvo que lo pida.

En fases de código, produce archivos/commits reales si tienes permisos; si no, un patch aplicable. Evita prose genérica, máximas promesas y falsos datos. No instalar dependencias sin un ADR o justificación.

## TRANSFERENCIA A CHATGPT CUANDO TERMINE MI CUOTA
Actualiza y entrega `docs/proposal/AI_HANDOFF.md` con:
- objetivo, rama y último commit SHA real;
- archivos nuevos/modificados;
- decisiones aprobadas vs propuestas;
- tests con comando, fecha y salida (o NO EJECUTADO);
- integraciones/conectores reales y permisos;
- problemas conocidos, métricas faltantes y presupuestos;
- 3 siguientes acciones priorizadas;
- texto listo: «Continúa en ChatGPT desde estos archivos, sin rehacer lo aprobado».

## PRIMERA ACCIÓN
Empieza por auditar los tres repositorios y el estado de permisos; informa hallazgos concretos y un plan de primer PR **solo documental**. No toques `main`. Continúa con los sprints cuando el equipo autorice.


### Referencia visual unificada - revisión final
- Identidad oficial provisional: `docs/proposal/assets/marca_oficial_canva.png` (lámina de Canva seleccionada por el equipo).
- Imagen editorial de Smart Fit: `docs/proposal/assets/smart_fit_editorial.png`.
- No reutilizar los antiguos SVG de dachshund/caricaturas del overlay.
- La app debe usar las fotografías reales del catálogo original cuando estén disponibles y contar con fallback honesto. Nunca presentar imágenes generadas como fotografías del producto.
- No modificar el backend Django original sin pull request aprobado.
