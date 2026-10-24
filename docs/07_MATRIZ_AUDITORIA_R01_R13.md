# 07 · Matriz de corrección de la auditoría del PR #3

Fecha: 23-oct-2026. Auditoría recibida contra el commit `95df61f`.
Este documento cruza cada hallazgo con su corrección, su prueba y su resultado.
Las 14 regresiones independientes se integraron SIN cambiar su significado en
`web/reino/tests/test_audit.py`; los casos adicionales viven en el dataset
versionado `web/reino/tests/eval_dataset.json` (81 casos) y en
`test_merchant_ops.py` / `test_eval_dataset.py`.

## R01–R13: hallazgo → causa → corrección → prueba → resultado

### R01 · Identidad de checkout compartida entre tiendas
- **Causa:** una sola clave `reino_idem` para toda la sesión; el servicio buscaba
  solo por clave, sin validar carrito/tienda.
- **Corrección:** clave por tienda en la vista (`reino_idem_<slug>`); el servicio
  acota la búsqueda a `cart` exacto + `is_current`; una clave de otro ámbito nunca
  recupera el resumen ajeno.
- **Prueba:** `test_audit.py::test_12_scope_idempotency_to_current_cart` + `IDM-*`.
- **Resultado:** ✅ pasa; dos tiendas, dos pestañas, dos intentos nunca comparten.

### R02 · «Volver a editar» conservaba envío y pago anteriores
- **Causa:** misma clave devolvía siempre la sesión previa sin comparar contenido.
- **Corrección:** `CheckoutSession.summary_hash` (SHA-256 del contenido aprobado).
  Mismo contenido ⇒ misma sesión; contenido distinto ⇒ sesión NUEVA vigente
  (`<clave>#<n>`), la anterior queda `is_current=False` y sus reservas se liberan
  atómicamente. Confirmar exige el `session_id` revisado: si cambió, se fuerza
  una revisión nueva. Confirmación revalida `is_current`, vencimiento y versión
  del carrito.
- **Prueba:** `test_10_edit_delivery_requires_new_current_summary` + `IDM-06/07`.
- **Resultado:** ✅ pasa; editar modalidad/pago produce el resumen vigente.

### R03 · Mismo SKU para dos destinatarios por encima del stock
- **Causa:** verificación por línea, sin sumar demanda por variante.
- **Corrección:** demanda AGREGADA por variante en `prepare_checkout` y
  `confirm_checkout`; bloqueo `select_for_update` en orden estable; referencia
  de pedido con fila de tienda bloqueada + restricción única `(store, reference)`.
- **Prueba:** `test_09_same_sku_two_recipients_respects_total_stock` + `AGG-01..04`.
- **Resultado:** ✅ conflicto comprensible (409 lógico), nunca reserva inválida.

### R04 · Cancelar un pedido sin pagar no devolvía inventario
- **Causa:** sin ciclo de vida del stock.
- **Corrección:** `apply_transition` restituye al cancelar (o vencer/fallar pago)
  pedidos NO despachados, exactamente una vez (`stock_restored_at`); registra
  `OrderEvent` con actor y motivo. Lo despachado requiere proceso de devolución.
  Pedido cancelado no admite preparación ni despacho; solo reembolso.
- **Prueba:** `test_08_cancel_unpaid_order_releases_stock_once` + `IDM-08`.
- **Resultado:** ✅ pasa; reintentar la cancelación no suma stock dos veces.

### R05 · Descuento Bitcoin ampliado indebidamente
- **Causa:** 15 % sobre todo el subtotal, sin elegibilidad por producto.
- **Corrección:** campo `Product.bitcoin_discount_eligible` (por defecto NO);
  el seed MIGRA la regla histórica `tienda.ProductPaymentRule` (0017: solo
  `cable-knit-jumper` y `bamboo-drying-robe` participan); `cart_summary` calcula
  por línea elegible y lo conserva en el snapshot del checkout y del pedido.
- **Prueba:** `test_14_bitcoin_discount_preserves_historical_eligibility` + `DSC-01..08`.
- **Resultado:** ✅ pasa; cesta mixta descuenta solo líneas participantes.

### R06 · Tarifa de retiro aceptada como entrega a domicilio
- **Causa:** la vista solo buscaba zona por nombre; el navegador mandaba.
- **Corrección:** `validate_shipping()` en el servicio: tienda + zona activa +
  modalidad coherente obligatorias; la vista además filtra zonas por modalidad.
  Una combinación incoherente se rechaza con error de campo.
- **Prueba:** `test_13_delivery_cannot_use_pickup_zone_for_free_shipping` + `ZON-01..06`.
- **Resultado:** ✅ pasa; no hay envío gratuito accidental.

### R07 · Revocar medidas no impedía que volvieran al asesor
- **Causa:** `latest_measurement()` no verificaba finalidad/consentimiento.
- **Corrección:** lectura única autorizada `authorized_measurement()` (tienda +
  titular + perfil + finalidad + estado vigente); la usan contexto del modelo,
  herramientas, recomendador y storefront. «Borrar memoria» elimina medidas,
  preferencias, resúmenes y conversaciones de la sesión; los pedidos conservan
  solo lo necesario.
- **Prueba:** `test_01_revoked_measurements_must_not_enter_model_context` + `MEM-01..08`.
- **Resultado:** ✅ pasa; tras revocar, nada reutiliza esas medidas.

### R08 · LookLab presentaba otra talla como compatible
- **Causa:** fit a nivel producto + emparejamiento por subcadena + sustitución
  automática por «la primera variante con stock».
- **Corrección:** unidad comprable real (producto+variante+regla+precio);
  `label_matches()` de coincidencia EXACTA (`Talla S` → `S`); si la talla
  compatible está agotada, la pieza sale de la selección y aparece como
  «Tu talla está agotada»; sin medidas, talla pendiente con elección explícita
  antes de agregar.
- **Prueba:** `test_03_no_other_size_when_compatible_size_sold_out` + `FIT-*`.
- **Resultado:** ✅ pasa; ninguna tarjeta M dice «compatible» con evidencia de S.

### R09 · Medidas antiguas prevalecían sobre las de esta visita
- **Corrección:** precedencia explícita en `_resolve_measurement()`: datos del
  intento actual → persistentes autorizadas → insuficientes. El borrador se
  reinicia en cada envío de medidas: «no tengo las medidas» no arrastra datos
  viejos. Smart Fit ofrece «Calcular sin guardar» (evaluación temporal).
- **Prueba:** `test_04_new_temporary_measurements_override_old_saved_measurements`.
- **Resultado:** ✅ pasa; «solo esta vez» no sobrescribe el perfil.

### R10 · El presupuesto del conjunto no limitaba
- **Corrección:** tope acumulado en la revelación sobre el precio de la variante
  efectivamente seleccionada (principal + complementos); lo que no cabe queda
  excluido con motivo, nunca «cumplido» de mentira.
- **Prueba:** `test_02_total_budget_must_limit_entire_look` + `BUD-01..08`.
- **Resultado:** ✅ pasa; el conjunto nunca supera el límite acordado.

### R11 · El modelo podía modificar el carrito sin autorización y repetirla
- **Corrección:** propuesta y ejecución separadas. El modelo genera una
  propuesta (`ActionToken`: alcance tienda+sesión, 15 min, UN solo uso,
  idempotente); el comprador confirma con el botón de la propuesta
  (`/asesor/accion/`). El orquestador NUNCA ejecuta herramientas de escritura.
- **Prueba:** `test_05_model_cannot_add_cart_without_buyer_authorization`,
  `test_07_duplicate_ai_action_must_not_double_quantity` + `AIA-01..04`.
- **Resultado:** ✅ pasa; consultar materiales no escribe; repetir no duplica.

### R12 · Afirmaciones inventadas en el texto libre
- **Corrección:** `_validate_answer()` verifica el texto contra la evidencia del
  turno: precios `$x`, porcentajes y promesas (garantía/«llega hoy») sin soporte
  en herramientas reemplazan la respuesta por una abstención honesta; sin
  evidencia no hay tarjetas. Las políticas citadas provienen de documentos
  publicados de la tienda.
- **Prueba:** `test_06_unbacked_model_prices_and_promises_are_rejected` + `TXT-01..08`.
- **Resultado:** ✅ pasa.

### R13 · Membresía sin permisos por acción
- **Corrección:** capacidades explícitas (`orders`, `payments`, `fulfilment`,
  `catalog`, `inventory`, `settings`, `team`) por rol
  (owner > staff > logistics), verificadas en VISTA (decorador
  `require_capability`) y en SERVICIO (`apply_transition(member=…)`). Confirmar
  cobro o reembolsar exige evidencia (nota); el reembolso registra importe,
  medio y motivo.
- **Prueba:** `test_11_logistics_role_cannot_mark_payment_paid` + `TRN-01..10` +
  `test_merchant_ops.py::test_staff_no_puede_editar_catalogo_ni_configuracion`.
- **Resultado:** ✅ pasa; logística opera entregas, nunca cobros.

## Hallazgos de interfaz (§4 de la auditoría)

| Hallazgo | Corrección | Evidencia |
|---|---|---|
| Cabecera recortada en móvil | Logo compacto, tagline oculta, acciones dentro del viewport, `.rk-hide-sm` con regla real | capturas 360/390 |
| Contenido pegado al borde | `padding-inline` (container) y `padding-block` (section) separados | capturas 360/390 |
| Título navy sobre navy | `.reveal h1/h2` en marfil | captura revelación |
| Códigos técnicos visibles | Razones traducidas (`reason_label`), «motor v1» fuera del recorrido | captura revelación |
| Todos los productos premarcados | Pieza principal marcada; complementos SIN premarcar; alternativas aparte | captura revelación |
| Total que no sigue la selección | Subtotal reactivo en JS (espejo; el backend recalcula siempre) | captura revelación |
| Guardar ignoraba la selección | Un solo formulario: Agregar y Guardar usan las mismas casillas | captura revelación |
| Conjunto poco coherente | 1 principal + complementos de función distinta; alternativas no se suman | captura revelación |
| Asesor mostraba infraestructura | «El asesor con IA no está disponible. Podés usar la selección guiada.» | captura asesor |
| Precio de ficha no ligado a variante | Precio reactivo por variante (radio/select) | captura ficha |
| «Sin perfil activo» protagonista | Chip solo con perfil; aviso demo aparte | capturas home |
| Iconos ambiguos | SVG consistentes (carrito, cuenta, menú, asesor) | capturas |
| Capturas antiguas | Regeneradas contra el commit final, 5 anchos | docs/capturas/ |

## Alcance P0 completado en esta corrección

- **Editor de catálogo operativo** (`/negocio/<slug>/catalogo/`): crear borrador,
  editar, publicar/archivar, variantes, precio especial, stock con motivo
  (`StockAdjustment` auditable), tabla de tallas versionada, imágenes. Pruebas:
  `test_merchant_ops.py::CatalogEditorTests` (7 casos).
- **Alta asistida** (`/plataforma/`): comercio en borrador + propietario + zona
  de retiro + política borrador + checklist de activación verificado
  (`OnboardingTests`).
- **Vistas operativas mínimas:** clientes (derivados de pedidos reales),
  finanzas (conciliación con evidencia), logística (tablero por estados).
- **Configuración editable:** identidad, zonas, políticas (misma fuente para
  ayuda y asesor), equipo con roles; la tienda nunca se queda sin propietario.
- **Operación (§9):** settings por entorno con cargador `.env` real, HTTPS y
  hosts obligatorios en staging/prod (fail-closed), PostgreSQL por `DATABASE_URL`,
  consumidor de outbox idempotente (`process_outbox`), seed no destructivo por
  defecto y `--reset` protegido, máquina de estados coherente (cancelado no se
  prepara/despacha), CI en GitHub Actions (suite + migraciones).

## Lo que NO se afirma (honesto)

- **IA real:** implementada y probada con proveedor simulado; **pendiente de
  `REINO_AI_API_KEY`**. La evaluación con proveedor real debe registrarse con
  modelo/versión/fecha/latencia/coste (la parte determinista —81 casos— corre
  en CI).
- **PostgreSQL/RLS:** configuración y pruebas de concurrencia escritas
  (`test_postgres.py`, saltan sin Postgres); ejecutarlas en staging es puerta
  de salida pendiente — este sandbox no tiene binarios de PostgreSQL.
- **Pasarela electrónica:** sin conectar; operan pago manual y Bitcoin manual
  con verificación humana y evidencia.
- **Tarifa $3.50 San Salvador:** sigue siendo hipótesis pendiente del negocio.
- **RLS:** no se afirma como existente; requiere políticas y roles reales en
  PostgreSQL (fuera del alcance de esta corrección).
- **Activo de marca (§6.2):** la fotografía real del hero muestra «WEINER
  KINGDOM» mientras la marca escrita es «Wiener Kingdom». Es la foto histórica
  del negocio: NO se alteró ni se inventó otra; requiere validación del activo
  por la marca antes del lanzamiento.
