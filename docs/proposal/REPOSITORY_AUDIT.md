# Auditoría de punto de partida — Wiener Kingdom

**Base:** [`CUBO-IA/grupo1-cuboai`](https://github.com/CUBO-IA/grupo1-cuboai), `main`, inspección de árbol, README, `web/tienda/catalog.py`, `web/templates/tienda`, `web/config/settings.py` y documentos de requisitos (17 oct 2026). **No se ha ejecutado la suite del equipo desde un clon completo**, porque el entorno de esta preparación no accede al servidor GitHub por Git TCP/HTTPS; las pruebas citadas son reportes previos del propio repositorio.

## Lo que ya construyó el equipo (no borrarlo)

- Backend **Django 5.2 / Python** con `web/config` y `web/tienda` y SQLite de desarrollo.
- **Catálogo:** ocho productos activos en `catalog.py` y un producto histórico retirado. El README inicial y checklist antiguos hablan de 4: usar código actual como criterio, pero validar con el equipo.
- **Smart Fit:** registra medidas del perro, formatos y validaciones.
- **Smart Quote:** calcula el precio base en el servidor; ajustes por talla todavía no definidos.
- **Carrito y checkout:** persistencia de pedidos, restricciones de duplicados y validación del lado servidor.
- **Panel privado:** requiere usuarios staff, controla estado de pedidos, pagos manuales, fabricación, envío y costos.
- **Descuento Bitcoin:** 15% de subtotal en artículos elegibles sujeto a verificación manual; no hay gateway real y PayPal/tarjeta son opciones de DEMO.
- **Asistente actual:** determinista por reglas de catálogo, **no** IA de modelo de lenguaje.
- **Pruebas:** abundantes `test_*.py` y migraciones; la propia documentación reporta 80 y 96 según estado de tareas. No confundir esas cifras históricas con el estado actual.

## Hallazgos y riesgos concretos

1. **Marca escrita de dos formas:** las plantillas y README usan `Weiner Kingdom` mientras el equipo ahora solicita **Wiener Kingdom**. Normalizar solo en un PR de marca aprobado.
2. **Producción:** `DEBUG=True` y `ALLOWED_HOSTS=[]`; usar solo desarrollo hasta hardening y pruebas.
3. **Acceso a pedido:** URL UUID funciona como acceso por enlace; requiere análisis de privacidad, expiración o autenticación según uso real.
4. **Checkout:** precio provisional hasta aprobación; no mostrarlo como compra definitivamente pagada.
5. **IVA, entrega, política de reembolsos:** procedimientos faltantes, no inventarlos.
6. **SQLite:** bien para MVP local, revisar Postgres y concurrencia antes de volumen real.
7. **Refactor masivo:** sería un retroceso; preservar nombres de rutas y comportamientos probados.

## Recomendación técnica

**Continuar en Django** y desarrollar una *capa de experiencia* premium sobre templates + CSS/JS, seguido por endurecimiento de seguridad, integraciones sandbox, analítica y módulos aislados. No cambiar a Next.js solo por moda; podría ser útil en un frontend desacoplado en otra fase, si lo justifica la carga.

## Evidencia y enlaces

- [Repositorio principal](https://github.com/CUBO-IA/grupo1-cuboai)
- [Guía técnica](https://github.com/CUBO-IA/grupo1-cuboai/blob/main/docs/guia-tecnica.md)
- [Especificación comercial](https://github.com/CUBO-IA/grupo1-cuboai/blob/main/docs/especificacion-comercial.md)
- [MVP y límites](https://github.com/CUBO-IA/grupo1-cuboai/blob/main/docs/mvp-checklist-y-limitaciones.md)
- [Pagos](https://github.com/CUBO-IA/grupo1-cuboai/blob/main/docs/pagos.md)
- [Catálogo fuente](https://github.com/CUBO-IA/grupo1-cuboai/blob/main/web/tienda/catalog.py)
