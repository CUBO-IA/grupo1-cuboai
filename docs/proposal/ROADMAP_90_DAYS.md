# Roadmap 90 días · Wiener Kingdom

El objetivo no es crear un marketplace de miles de vendedores antes de lograr una compra confiable de prendas para dachshunds.

## Días 1–15 · Baseline y decisiones

- Ejecutar localmente test suite Django y registrar resultado reproducible.
- Revisar reglas comerciales con equipo: talla, precio provisional, $850, 15% BTC, costo real, envío, devoluciones.
- Unificar spelling de marca previo acuerdo.
- Probar diseño visual en 5 móviles y 10 usuarios.
- Bloquear `main` contra cambios no revisados cuando el equipo lo apruebe.

## Días 16–30 · Diseño en Django

- Crear CSS tokens y vistas nuevas gradualmente, sin romper URLs.
- Asegurar accesibilidad, estados vacíos, errores, fotos, Smart Fit, Smart Quote.
- Analizar abandono de pasos sin recopilar información sensible.
- Validar que cotizaciones siguen en servidor y nunca auto-confirman pago.

## Días 31–60 · Operación y seguridad

- Hardening y staging, backups, monitoreo, rate-limit del login.
- Elegir proveedor de pagos **según jurisdicción y entidad legal**, primero sandbox.
- Workflow de pedidos y soporte. Correo transaccional solo tras consentimiento y pruebas.
- Cotización de al menos 2 transportistas/3 talleres para producción local.

## Días 61–90 · Piloto + datos

- Piloto con pedidos y usuarios autorizados, sin promesas globales.
- Dashboard de ventas con importes separados: GMV, ingresos, margen, costo, devoluciones.
- Asistente limitado con respuestas verificables, escalamiento humano.
- Decidir si expansiones como multi-vendedor o fabricación regional merecen inversión.

## Gates

No lanzar pago real sin PSP real, legal, documentación, prueba de reembolso, webhooks verificados, conciliación, seguridad, soporte y aprobación humana.
