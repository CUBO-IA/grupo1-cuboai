# 04 · Comercio y operación (F3, F7, F8)

## Pedido, inventario y dinero (implementado)

- **Dinero:** `Decimal`, política única `ROUND_HALF_UP` a centavos (`reino/money.py`).
  Envío separado de mercancía; nunca «total final» con envío desconocido («Envío: por
  calcular»). No se suman monedas distintas (una moneda por tienda).
- **Reserva:** agregar al carrito NO aparta stock; `prepare_checkout` crea reserva de
  10 min en transacción con `select_for_update` ordenado. Dos compras de la última unidad:
  una sola reserva válida (A17, probado también con 2 hilos).
- **Idempotencia:** clave por intento (checkout + pedido, únicas en DB). Doble clic y
  reintentos devuelven el pedido existente (A18 verificado). Cambio de carrito invalida
  el resumen previo. Checkout vencido no confirma.
- **Estados separados** (Order): pedido `placed/confirmed/cancelled/closed` · pago
  `pending/requires_action/paid/failed/expired/refunded/...` · preparación
  `not_started/preparing/ready/cancelled` · entrega `unassigned/scheduled/shipped/
  delivered/incident/returned`. Máquina de transiciones validada en panel con actor
  registrado (`OrderEvent` con usuario); una transición inválida se rechaza (test).
- **Pago manual autorizado:** el pedido queda PENDIENTE de verificación; un comprobante
  es evidencia para revisar, nunca pago automático (microcopy honesto en checkout y
  confirmación: «Crear pedido pendiente de pago»).
- **Bitcoin 15 % preservado:** descuento sobre mercancía, pendiente de verificación;
  prueba numérica A22-núcleo: 2 × $63 = $126 → descuento $18.90, total $107.10
  (test_commerce). La elegibilidad por producto del flujo legacy sigue intacta.
  Acumulación con otras promociones: desactivada provisionalmente (no existe otra
  promoción); cambiar la política requiere decisión de la propietaria.
- **Pasarelas electrónicas:** NO conectadas (sin cuenta sandbox elegible confirmada;
  ver §27 del diseño). Nunca se afirma «pago electrónico completado».

## Delivery (P0)

Matriz de zonas por tienda (`ShippingZone`): retiro $0 y zonas locales con tarifa.
La tarifa de San Salvador ($3.50) es **hipótesis de demostración pendiente de aprobación
del negocio** (marcada en seed y aquí). Sin zona elegida no hay envío ficticio gratis
(A27, test). Sin tracking en tiempo real; estados manuales auditados.

## Panel del comerciante (M03–M10 mínimo)

- Acceso: `is_staff` + membresía del tenant; staff de otra tienda → 403 (A26 verificado).
- M03: «Esto necesita tu atención» (pagos pendientes, stock bajo) antes que KPIs;
  sin pedidos pagados → «Sin datos suficientes», nunca porcentajes inventados (A28).
- M04: lista de catálogo con variantes y stock (editor/alta manual: P1; el alta P0 es
  por seed/migración controlada).
- M05: pedidos por estado; detalle con líneas inmutables, 4 dimensiones de estado,
  transiciones validadas, línea temporal con actor. Reembolso ≠ cancelación (estados
  separados; acción de reembolso parcial con montos: P1).
- M10: integraciones con estado REAL (Sin configurar / Prueba / Producción / Error) y
  sin mostrar claves. IA reporta su estado según `REINO_AI_API_KEY`.
- M01 `/para-negocios/`: propuesta de valor + tarifas MARCADAS como hipótesis del piloto;
  «Solicitar acceso al piloto» por correo. M02 (alta guiada) queda P1: el alta real P0 es
  por invitación + seed controlado.
- P02 `/plataforma/`: lista de comercios/tiendas con estados (solo superusuario).

## Onboarding publicable (checklist real de Wiener Kingdom)

✓ catálogo con productos válidos · ✓ identidad y contacto · ✓ políticas publicadas
(ayuda) · ✓ modalidad de entrega (retiro + zona demo) · ✓ mecanismo real de recepción
del pedido (panel + correo del negocio). Pago electrónico: no requerido para operar
manualmente, flujo aprobado por el negocio (histórico).

## Comisiones de plataforma

P0: sin cálculo automático de comisiones (la tarifa SaaS es hipótesis §19; ninguna
suscripción se cobra en la demo). `CommissionEntry` y payouts: P1/P2 planificados.
