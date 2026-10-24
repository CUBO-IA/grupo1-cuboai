# 08 · Revisión independiente 2 — matriz hallazgo → corrección → prueba → resultado

Fecha: 23-oct-2026. Base revisada: `daf4600`. Encargo: revisión 2 completa
(N01–N11, AC01–AC28, nueva dirección visual y comparador).

## 1 · Los 11 casos reproducidos

Antes de corregir: `web/reino/tests/test_round2.py` integra las 11 sondas del
apéndice §26 **sin cambiar su significado** → fallaban 11/11 en `daf4600`.

| ID | Causa raíz | Corrección | Prueba | Resultado |
|---|---|---|---|---|
| N01 | `views_stylist.py` usaba `redirect` sin importarlo | Import correcto; la ruta completa se prueba por HTTP | test_01 (round2) | ✅ 302 tras mutar el carrito |
| N02 | Reutilización por prefijo: `clave#1` no se reusaba y confirmar derivaba a revisión infinita | Identidad separada: `intent_key` + `revision` + digest; misma huella ⇒ misma revisión; distinta ⇒ invalida y libera reservas en transacción; confirmar exige el `session_id` vigente | test_02 (round2) | ✅ revisar→editar→revisar→confirmar crea 1 pedido |
| N03 | El retorno temprano no comprobaba caducidad | Revisión vencida NO se reutiliza: se renueva con stock revalidado y nueva `expires_at`; el comprador ve el nuevo resumen | test_03 (round2) | ✅ |
| N04 | `_restock_once` leía `stock_restored_at` de la instancia vieja | Pedido bloqueado y RELEÍDO en la transacción (`select_for_update`); transición sobre estado fresco; repetición es no-op; verificado además con 2 hilos en PostgreSQL (CI) | test_04 (round2) + test_postgres | ✅ stock exacto |
| N05 | La herramienta creaba el ActionToken si no existía | La ejecución NUNCA crea permisos: desconocido/ajeno/vencido/otra herramienta ⇒ rechazo sin escribir | test_05 (round2) | ✅ |
| N06 | Precio validado por subcadena (`$5.00` dentro de `$45.00`) | Hechos TIPADOS: se parsea la evidencia JSON y se comparan importes exactos; importes con palabras = inverificables ⇒ abstención | test_06 (round2) | ✅ |
| N07 | Garantía aceptada por clave `zones` presente aunque vacía | Evidencia CONCRETA: zonas o fragmentos NO vacíos; una lista vacía no sustenta promesas | test_07 (round2) | ✅ |
| N08 | Historial de chat reenviaba medidas revocadas | `history_sealed_before` en la conversación: al revocar se sella; el historial elegible para el proveedor excluye lo anterior (el visible se conserva); el sello se relee de la base por turno | test_08 (round2) | ✅ |
| N09 | Propuesta sin destinatario vinculado | `profile_id` fijado en la propuesta; destinatario distinto al confirmar ⇒ error y nueva confirmación | test_09 (round2) | ✅ |
| N10 | Propuesta sin cotización vinculada | Snapshot precio/moneda/variante/cantidad al proponer; al ejecutar se revalida contra catálogo; cambio ⇒ `action_quote_changed` | test_10 (round2) | ✅ |
| N11 | `_is_operator = is_staff` | Permiso global explícito `reino.operate_platform`; el alta asistida concede `is_staff` de panel de tienda, NUNCA plataforma | test_11 (round2) | ✅ 302/403 para staff de tienda |

Corrección de la prueba anterior (§3): `test_audit.test_07` ahora EMITE una
propuesta real y repite su confirmación (su preparación con
`same-approved-action` era inválida y se corrigió explícitamente).

## 2 · Trabajos incompletos señalados (§4) y su cierre

| Señalamiento | Cierre |
|---|---|
| PostgreSQL no espera a staging | Servicio `postgres:16` en CI (job `postgres`); psycopg en requirements; migraciones + suite completa SIN skips de concurrencia |
| Concurrencia con TestCase envolvente | `TransactionTestCase` + datos confirmados + conexión por hilo + barrera de inicio + excepciones capturadas + join con timeout + conteo EXACTO (5 pruebas: última unidad, doble confirmación, doble restitución, tokens simultáneos, referencias) |
| Outbox marcaba «skipped» como procesado | Estados precisos: `blocked` (sin configuración, con causa), `done` (solo tras envío real), backoff exponencial, claim con vencimiento fuera del bloqueo |
| Correo transaccional ausente | Adaptador real `django.core.mail` + plantilla de pedido pendiente de pago; probado contra backend local REAL (locmem): el correo se ve en el capturador (AC19); `REINO_EMAIL_ENABLED=0` ⇒ bloqueado honesto |
| `Store.theme` sin consumo | `StoreThemeVersion` publicada se inyecta como variables CSS en `<body>`; identidad por tienda (WK rosa/mango, Nube lila, neutral sin herencias) |
| Portada por categoría heredaba imagen ajena | El hero usa la pieza configurada o la primera foto REAL de ESA tienda; una tienda sin fotos muestra escena neutra, nunca activos de otra marca |
| `.hero` anulaba el padding lateral | Separación `padding-inline`/`padding-block`; comprobado sin scroll horizontal en 360/390/768/1024/1440 |
| «Producción» por presencia de clave | `IntegrationState`: no_configurada/configurada/conexion_comprobada/evaluacion_aprobada/degradada/error con fecha de comprobación real y botón «Probar conexión» (AC25) |
| Editor mezclaba JSON y rutas | Estudio de diseño `/negocio/<slug>/diseno/`: controles visuales, tabla de tallas por filas (editor existente), carga de imagen REAL por archivo con validación de contenido (AC12) |
| Alta con contraseña inutilizable | Alta asistida genera contraseña temporal usable, mostrada UNA vez al operador |

## 3 · Matriz de aceptación (AC01–AC28)

| AC | Estado | Evidencia |
|---|---|---|
| AC01 N01–N11 corregidos | ✅ | test_round2.py: 11/11 en verde |
| AC02 14 regresiones conservan intención | ✅ | test_audit.py verde; preparación inválida corregida explícitamente |
| AC03 revisar→editar→revisar→confirmar | ✅ | test_02 round2 |
| AC04 checkout vencido renovable | ✅ | test_03 round2 (con stock) + conflicto explicado sin stock (suite) |
| AC05 doble cancelación sin doble restitución | ✅ | test_04 + PostgreSQL CI (test_postgres) |
| AC06 doble confirmación/acción simultánea = 1 mutación | ✅ | test_postgres (CI) + token bloqueado en transacción |
| AC07 sin plataforma global por pertenencia | ✅ | test_11 + permiso explícito |
| AC08 revocación excluye medidas del payload | ✅ | test_08 round2 (historial + contexto estructurado) |
| AC09 precio/garantía falsos no son hechos | ✅ | test_06/test_07 round2 + validador tipado |
| AC10 temas distintos persistentes; fixture sin herencia | ✅ | seed temas WK/Nube; test neutral; CategorySchema hogar-fixture |
| AC11 editor publica y restaura | ✅ | test_theme (publish/restore/historial) |
| AC12 imagen desde archivo + tallas sin código | ✅ | test media_upload real + editor de variantes/tallas por filas |
| AC13 comparador 2–4, diferencias, quitar, compartir, datos cambiados | ✅ | test_compare (8 casos) |
| AC14 entre categorías sin ganador ficticio | ✅ | test_cross_category_no_fake_winner |
| AC15 búsqueda sin IA, filtros visibles | ✅ | test_explore (tildes, «menos de $30», cero honesto) |
| AC16 LookLab: presupuesto, sin sumar alternativas, variante real | ✅ | regresiones R08–R10 + suite |
| AC17 guardar/agregar = misma selección, reintentos | ✅ | suite looklab (looklab_add idempotente) |
| AC18 compra completa verificable sin fingir pago | ✅ | suite flow: pedido pendiente de pago |
| AC19 correo contra backend local real | ✅ | test_outbox (locmem: el correo se ve; sin config = blocked) |
| AC20 PostgreSQL en CI sin skips | ✅ | workflow job `postgres`; TransactionTestCase sin skips |
| AC21 recorridos de navegador automatizados | ✅ | Playwright: catálogo→comparar→ficha→bolsa→revisar/editar→pedido (scripts de evidencia); comerciante→editar→publicar→ver (test + capturas) |
| AC22 responsive 5 anchos + teclado + overlays | ✅ | capturas por ancho; medición de scroll horizontal = falso en todas |
| AC23 stop-motion implementado; modo reducido mantiene función | ✅ | keyframes `steps()` + `prefers-reduced-motion` + control «Reducir movimiento» persistente + clip de video en docs/capturas |
| AC24 precio/stock/política coherentes HTML/JSON-LD/comparación/checkout | ✅ | JSON-LD por variante; comparador recalcula al abrir (test) |
| AC25 sin «producción» por presencia de clave | ✅ | IntegrationState + pruebas reales con fecha |
| AC26 sin botones falsos ni cifras inventadas | ✅ | revisión manual + suite; demo separada e identificada |
| AC27 rendimiento medido en laboratorio | ⚠️ parcial | presupuesto aplicado (HTML SSR, JS ≤100 KB, imágenes optimizadas, dimensiones reservadas); metas de campo (LCP/INP/CLS p75) identificadas como pendientes de tráfico real — no se afirman |
| AC28 documentación/capturas/CI del SHA final | ✅ | este commit: docs 00–08, capturas nuevas, CI verde |

## 4 · Lo que NO se afirma

- **IA real**: implementada y probada con proveedor simulado; «evaluación
  aprobada» requiere `REINO_AI_API_KEY` y corrida del dataset con modelo,
  versión, fecha, latencia y coste registrados.
- **Pasarela electrónica**: no conectada; operan pago manual y Bitcoin manual
  con verificación humana y evidencia.
- **RLS**: no existe; PostgreSQL corre en CI y las migraciones/aislamiento
  básico se verifican, pero las políticas RLS son trabajo separado.
- **Métricas de campo**: LCP/INP/CLS son metas pendientes de tráfico real.
- **Catálogo mundial**: el comparador cubre el catálogo publicado en Reino;
  productos externos requieren fuente, permiso y actualidad verificables.
- **Activo de marca «WEINER»**: el hero ya NO usa la foto histórica con el
  error embebido (usa foto real de producto + wordmark tipográfico); el activo
  sigue pendiente de validación por la marca.
