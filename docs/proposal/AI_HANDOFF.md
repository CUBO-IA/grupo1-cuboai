# AI Hand-off v1 · Contexto para cualquier modelo posterior

## Product truth
Wiener Kingdom es una tienda Django (ropa para dachshunds). Fuente: CUBO-IA/grupo1-cuboai. NO reescribir el núcleo sin aprobación. El plan ambicioso (marketplace + SaaS + IA + logística distribuida) es **futuro**, no una realidad existente.

## Today
Este paquete contiene documentos y demo aislada creados externamente. No se subieron al repositorio por falta de permiso GitHub push. No hay PR remoto, despliegue real, ni IA conectada.

## Existing known endpoints
`/`, `/productos/`, `/producto/<slug>/`, `/smart-fit/`, `/guide/`, `/cart/`, `/cart/checkout/`, `/order/<uuid>/`, `/panel/`.

## Business constraints
- 8 productos activos en catálogo fuente; precios base, cotización final pendiente.
- Bitcoin con descuento manual elegible 15%; sin gateway real.
- Staff confirma pagos; no producir sin verificación.
- Django + SQLite local; hardening pendiente para producción.

## Next recommended action
Conseguir GitHub write o fork, abrir PR solo de `docs/proposal/` y `proposals/wiener-kingdom-next/`. Luego probar integración de una pantalla cada vez en rama separada.

## Model contract
Todo cambio requiere listar archivos leídos, modificados, pruebas realmente ejecutadas, riesgos y aprobación requerida. No inventar ejecución, métricas o conexiones. Cada modelo debe mantener este archivo actualizado.


### Referencia visual unificada - revisión final
- Identidad oficial provisional: `docs/proposal/assets/marca_oficial_canva.png` (lámina de Canva seleccionada por el equipo).
- Imagen editorial de Smart Fit: `docs/proposal/assets/smart_fit_editorial.jpg`.
- No reutilizar los antiguos SVG de dachshund/caricaturas del overlay.
- La app debe usar las fotografías reales del catálogo original cuando estén disponibles y contar con fallback honesto. Nunca presentar imágenes generadas como fotografías del producto.
- No modificar el backend Django original sin pull request aprobado.
