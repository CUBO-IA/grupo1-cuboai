# Smart Fit — medidas, perfiles y talla de referencia

## Qué recoge
- Nombre del perro (**opcional**) y raza.
- Peso con unidad (kg o lb).
- Largo del lomo y contorno del pecho (cm o in).
- Contorno del cuello: opcional por defecto; **obligatorio solo para las prendas que lo requieran** (configurable).
- Todo se guarda en kg y cm. Los rangos de plausibilidad son provisionales (detectan errores de captura, no tallas).

## Perfiles reutilizables
- Cada perfil tiene un identificador UUID. `/smart-fit/<uuid>/editar/` permite corregir las medidas.
- La sesión del navegador recuerda hasta 5 perfiles ("Saved dogs") para reutilizarlos con otra prenda.
- Los pedidos guardan **su propia copia** de las medidas: editar el perfil después no cambia un pedido ya confirmado.
- No hay cuentas de cliente: quien tiene el enlace UUID puede ver y editar el perfil.

## Medidas por prenda
- Configuración en el panel: `/panel/measurements/` (solo personal).
- Estado inicial: **ninguna prenda exige el cuello** y todo figura como "no validado con confección".
- Si una prenda lo exige y el perfil no lo tiene, el sistema pide la medida antes de cotizar.

## Talla de referencia
- La tabla de 3 grupos de perros (pequeños, medianos, grandes; cuello, pecho y largo de espalda en cm) viene de la guía maestra y es **editable**.
- La talla se calcula **solo desde las medidas**, nunca por raza.
- Resultados posibles: una fila ("matched"), varias filas ("between sizes") o fuera de tabla; en los dos últimos casos se indica revisión manual.
- Es informativa: **no cambia precios ni cotizaciones**. La tabla no está validada con confección y algunas filas se solapan.
- El pedido guarda la talla de referencia vigente al confirmarse.

## Pendiente de validar
1. Qué prendas requieren el cuello y otras medidas del patrón.
2. Tabla de tallas definitiva y qué hacer en solapes.
3. Regla de ajuste de precio por talla (no implementada) y límite de US$850.
4. Variación del consumo de materiales por talla.
5. Medición por fotografía: no implementada, requiere un procedimiento validado.
