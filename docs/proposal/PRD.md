# PRD — Wiener Kingdom (incremento boutique + base modular)

> Estado: PROPUESTA para revisión del equipo. Distingue HECHO (existe) / PROPUESTA / HIPÓTESIS.

## 1. Objetivo
Convertir la tienda Django existente en la experiencia ecommerce premium para dachshunds más cuidada, SIN reescribir Django ni romper decisiones comerciales (precios, descuento BTC, estados de pedido, pagos manuales).

## 2. Alcance del incremento (MVP iterativo)
**Conservar:** Django 5.2, 8 productos activos, Smart Fit, Smart Quote, carrito, checkout, pedidos, panel, tests, migraciones, semántica de estados.
**Añadir en este incremento:** design tokens, responsive 375/768/1440, accesibilidad WCAG 2.2 AA, fichas editoriales, estados de carga/error/vacío, transparencia de precio provisional, QA.
**Fase aparte:** pagos sandbox + hardening + PSP (requiere decisión legal).
**Fuera del MVP:** pasarela real, multivendedor abierto, custodia BTC, fabricación global, AR/VR, LLM conectado.

## 3. Personas y recorridos
- **Comprador (dueño de dachshund):** descubrir → medir (Smart Fit) → cotizar (Smart Quote) → carrito → checkout → seguir pedido.
- **Staff (operador):** aprobar pago manual → confirmar talla → costos → producción → envío → tracking.
- **Coordinator (wk-director):** orquestar agentes, verificar con pruebas, reportar a NØVA.

## 4. Requisitos funcionales priorizados (MoSCoW)
**MUST**
- FR-01 Preservar URLs y tests actuales verdes.
- FR-02 Catálogo de 8 activos con fichas y fotos originales (fallback honesto).
- FR-03 Smart Fit valida y guarda medidas (móvil).
- FR-04 Cotización SIEMPRE en servidor; precio provisional no manipulable.
- FR-05 Carrito actualiza cantidades y evita duplicados.
- FR-06 Checkout muestra total y estado real; NUNCA auto-marca pagado.
- FR-07 BTC 15% solo elegible + verificación manual.
- FR-08 Staff registra referencia y transiciones (OrderEvent).
- FR-09 Producción no inicia sin pago verificado.
- FR-10 Seguimiento sin exponer costos internos.

**SHOULD**
- FR-11 Vista mobile-first + teclado (375px).
- FR-12 UI separa muestras/estimaciones de datos reales.
- FR-13 Asistente determinista no inventa datos externos.
- FR-14 Contratos de eventos para analítica futura (fuente + denominador).

**COULD**
- FR-15 Búsqueda/filtros por categoría.
- FR-16 Wishlist/guardar perfiles (ya hay 5/sesión).

**WON'T NOW**
- PSP real, multivendedor, custodia BTC, AR/VR, LLM conectado, tokens.

## 5. Requisitos no funcionales
- Django 5.2 / Python 3.12+; migraciones reversibles; tests verdes.
- Seguridad: DEBUG off, ALLOWED_HOSTS, HTTPS, cookies seguras, CSRF, rate-limit, secretos externos, backups.
- Accesibilidad WCAG 2.2 AA (teclado, foco, contraste, reduced motion).
- Performance: LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 (medición real).
- Ninguna captura de tarjeta en frontend.

## 6. Definition of Done
Criterios de aceptación + tests + seguridad + accesibilidad + documentación + observabilidad + revisión independiente + staging. Si no se ejecutaron tests, el PR declara "NO PROBADO".

## 7. Fuera de alcance (explícito)
No reemplazar Django por Next.js. No fingir pagos. No cambiar precios/descuento/estados sin ticket aprobado. No publicar producción.