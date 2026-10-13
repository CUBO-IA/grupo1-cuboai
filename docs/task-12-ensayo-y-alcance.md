# Task 12 — Ensayo de demo y congelación del alcance

## Ensayo realizado

**Entorno:** clon limpio del remoto (`50c8a5f`) en `D:\dev\tmp\wk-clean-install`, venv nuevo, Python 3.12.13, Windows 10, servidor `runserver` local.

| Paso | Resultado |
|---|---|
| Clon sin archivos prohibidos (`venv`, `sqlite`, `staticfiles`, `__pycache__`, `.env`) | OK (52 archivos versionados) |
| `pip install -r requirements.txt`, `check`, `migrate` (0001–0006) | OK |
| `manage.py test` desde el clon | OK (80 pruebas) |
| `createsuperuser` | OK |
| Páginas públicas y recursos estáticos (HTTP) | 200 en `/`, catálogo, 4 fichas, `/guide/`, `/smart-fit/`, login, CSS e imágenes |
| Smart Fit: formulario vacío | 5 errores de campo obligatorio; cuello opcional |
| Smart Fit: peso 500 kg | Error con rango esperado en kg y lb; datos conservados |
| Smart Fit: registro válido | Persistido y mostrado en kg/cm |
| Cotización Wedding Dog | $650.00, marcada provisional, ajuste por talla "pendiente" |
| Checkout: correo inválido | Error claro; datos conservados |
| Checkout: envíos simultáneos | Ver defecto 1 (corregido) |
| Pedidos | 5 pedidos para 5 cotizaciones, sin duplicados |
| Panel: transiciones inválidas | "Production must be completed before shipping", "payment reference is required" |
| Panel: ciclo completo de estados | confirmado → pagado (con referencia) → producción → completado → enviado → entregado |
| Costos | Real $190.25 sobre $650 → margen $459.75 (70.7%), etiquetado "actual" |
| Página del cliente | Sin referencia de pago, costos, notas ni nombres de staff |
| Responsive 375 px | Sin desbordes horizontales en 9 páginas (comprobación de geometría) |

## Defectos encontrados y corregidos en el ensayo

1. **500 por "database is locked"** al enviar el checkout dos veces a la vez (SQLite). No creaba pedidos duplicados, pero la segunda petición fallaba. Corrección: `transaction_mode=IMMEDIATE` y `timeout=20` en `config/settings.py`. Verificado con 4 envíos simultáneos en 3 cotizaciones: todos redirigieron y no hubo duplicados.
2. **Texto contradictorio** en la página del cliente: con pago registrado decía "Paid — no payment has been collected". Corrección en `order.html`; prueba añadida.

## Cómo reproducir el ensayo

Ver README (instalación y ejecución) y `docs/guion-demo.md`.

## No verificado

- Aspecto visual (colores, tipografía, estética): las capturas de pantalla del panel del navegador no estuvieron disponibles; solo se verificó contenido y geometría.
- Navegadores distintos del integrado, dispositivos reales, accesibilidad.
- Despliegue en producción, HTTPS, carga.

## Errores pendientes y limitaciones

- Cotizaciones y pedidos con **precio provisional** (sin regla de tallas).
- Sin pasarela de pago; pago registrado manualmente.
- Sin límite de intentos de login; `DEBUG=True`; sin configuración de producción.
- Acceso del cliente por URL con UUID, sin cuenta ni verificación.
- Sin correos de confirmación.
- Rangos de validación de medidas provisionales.
- Transiciones de estado: supuestos técnicos sin aprobación del negocio.
- El panel lista los 25 pedidos más recientes (sin paginación).

## Alcance congelado

**Incluido:** catálogo de 4 productos, asistente guiado determinista, Smart Fit, Smart Quote provisional, checkout, pedidos persistentes, panel privado con estados y costos, seguimiento para el cliente.

**Fuera de alcance (no implementar sin nueva autorización):**
- Precio por talla/material y tope de $850
- Descuento Bitcoin
- Pagos reales y notificaciones por correo
- IA generativa
- Cuentas de cliente, paginación del panel, despliegue en producción
