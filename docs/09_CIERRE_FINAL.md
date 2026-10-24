# 09 — Cierre final (Revisión 3 · F01–F14 + A01–A64)

Documento de evidencia del cierre de la **Revisión 3** (prompt maestro final).
Fecha: 2026-10-24. Rama: `dede2812:feature/fluso-kingdom-mvp` → PR #3 (borrador).

**Suite local final: 493 tests OK (5 omitidos: sólo-PostgreSQL, corren en CI).**
Migraciones: `makemigrations --check` limpio. CI: sqlite + postgres:16 (servicio).

---

## 1. Defectos F01–F14 (causa raíz → corrección → prueba)

| # | Defecto | Causa raíz | Corrección | Prueba |
|---|---|---|---|---|
| F01 | CI y local leen distinto secreto | nombres de env divergentes | settings acepta `DJANGO_SECRET_KEY`/`DJANGO_ALLOWED_HOSTS` canónicos + alias legados; CI usa `DJANGO_*` con secreto dedicado | job CI verde con Postgres |
| F02 | `request_id` (40) trunca IDs de proveedor (64) → DataError intermitente en Postgres | longitud insuficiente | 3 campos a 64 (migración 0007); `track()` atrapa `DatabaseError` con aviso registrado (la analítica nunca rompe el flujo) | `test_postgres` + `test_analytics` |
| F03 | Tests de concurrencia comparten fixture mutable | clase compartida | fixture por test en `_ConcurrencyBase.setUp` | `test_postgres` (5 tests, barrera 2 hilos, conteos exactos) |
| F04 | Número de pedido literal y test sqlite-only rompen Postgres | `WK-000001` asumido | aserción sobre `order.number` devuelto; test sqlite-only se salta fuera de sqlite | CI postgres verde |
| F05 | Desalineación atributo-valor en comparador | celdas en orden de queryset | celdas claveadas por id de variante estable (`pk_by_vid`) | 3 tests en `test_compare` |
| F06 | Estado operativo incoherente: tienda «activa» con negocio en borrador | dos ciclos de vida sin regla | `services_visibility.py`: regla única (negocio pilot/active + tienda active/demo + publicado); aplicada en búsqueda, tenancy, sitemap, recomendador, IA y comparador; `store_activate` promueve el negocio a PILOT | 5 tests `test_visibility` + flujo A35 |
| F07 | Contraste roto: blanco sobre lavanda `#B9A5FF`; hover oscurece acento | un solo color de acción sin par | `on_primary` por identidad, validado ≥ 4.5:1 al guardar/publicar (blanco sobre lavanda rechazado); CSS usa `--rk-on_primary` | `test_theme` |
| F08 | «Vista previa» del estudio no renderiza borrador aislado | inexistía | vista `design_preview` (membresía + `X-Frame-Options: SAMEORIGIN`) renderiza el borrador en iframe; badge «vista previa» | `test_theme` + captura estudio |
| F09 | Versiones de tema ambiguas | sin inmutabilidad | `is_current` (migración 0008); publicar conserva versiones anteriores inmutables; `_next_version` bajo bloqueo; restaurar = nueva versión; hash verificable | `test_theme.test_hash_version_verificable` |
| F10 | Claim engine admite «llega mañana» sin fecha confirmada ni política | una regex para todo | promesas de entrega exigen hecho `delivery_confirmed` con fecha real («sin confirmar»/«none»/«null» no valen); devoluciones exigen fragmento de política que mencione devol/reembols | casos CLM-01..24 del dataset |
| F11 | Fit JSON de una sola línea rompe edición | textarea JSON | editor de filas `_parse_fit_rows` con errores por celda e input preservado en sesión; slug acentuado corregido (`slugify`) | `test_fit` + flujo panel |
| F12 | Dirección visual: comparador móvil, movimiento reducido, componentes | faltaban evidencias | página viva `/plataforma/componentes/`; capturas móvil 390×844 del comparador; toggle «Reducir movimiento» persistente + media query | `shots4/` (8 capturas) |
| F13 | Integración git/upstream ausente | rama sin upstream | upstream/main (`98fc9f6`) fusionado en la rama (merge `d26f4360`); conflictos resueltos conservando home upstream + franja Reino | PR #3 mergeable |
| F14 | Conteo de tests inflado en informes | número no verificado | conteo REAL por descubrimiento: **493** (`Ran 493 tests`, salida guardada en CI) | este documento + CI |

### Riesgos de lectura verificados

- **`?c=` concat**: la URL de compartir se construye en servidor (`share_url`);
  JS sólo copia al portapapeles con *fallback*.
- **Comparar usa variante elegida**: el hidden `variant_id` se sincroniza al
  cambiar de opción (JS) — compara la variante seleccionada, no la primera.
- **Orden de módulos**: se persiste exacto (campo `module_order` + ↑/↓).
- **Asignar medios**: hero → borrador del tema (`media_asset_id`); producto →
  `ProductMedia.asset` (migración 0009) con focal.
- **Forma de botones**: efecto real vía `--rk-btn-radius`.
- **Consultas sugeridas**: stopwords («para», «con», «de»…) no entran al AND;
  «máximo $30» es cue de presupuesto (hueco encontrado y corregido).
- **Comparador móvil**: evidencia `shots4/comparar_movil.png`.

---

## 2. Matriz de aceptación A01–A64

Leyenda: ✅ verificado con prueba/captura · ⚠️ parcial (qué falta) · ⛔ bloqueo externo declarado.

### Plataforma y dominio

- **A01–A03** multi-tenant estricto, catálogo, checkout/pedido ✅ (rounds 1–2, 493 tests)
- **A04** SEO social mínimo ✅ (OG tags, sitemap con regla de visibilidad F06)
- **A05** observabilidad base ⚠️ (request_id 64 + outbox con reintentos/backoff + `/salud/`; falta dashboard de métricas en producción)
- **A06/A07** estilista IA con reglas vivas ✅ (modo reglas honesto, 202 casos eval) / IA real ⛔ `REINO_AI_API_KEY`
- **A08** LookLab/probador con silueta ⚠️ (flujo completo con reveal, total reactivo; la «silueta» es la foto real del producto + talla, no avatar renderizado — decisión honesta declarada)
- **A09–A11** panel negocio, pedidos con transiciones, stock con reservas ✅
- **A12** analítica-first ✅ (eventos reales, request_id, nunca bloquea flujo)
- **A13/A14** RLS Postgres ⛔ (CI corre Postgres para migraciones y concurrencia; RLS es trabajo aparte declarado) / outbox ✅ (BLOCKED, claim_token, backoff, email real probado con locmem)

### Rondas de auditoría

- **A15–A28**: cubiertas en `docs/08_MATRIZ_REVISION_2.md` (11/11 probes N01–N11 en verde, matriz A15–A28 con evidencias).

### Dominio multi-categoría (G2)

- **A32** 6 categorías físicas con contratos de atributos ✅ (`mercado-demo` seed + tests A32)
- **A33** digital ✅ (entrega por `DigitalGrant` una vez por (asset, pedido); descarga autorizada con caducidad y límite)
- **A34** servicio reservable ✅ (`ServiceSlot` con concurrencia segura; `Booking`; sin doble reserva)
- **A35** negocio nuevo desde panel ✅ (alta→categoría→contrato→producto→publicar→visible, test de ciclo completo)
- **A36** atributos con contrato y comparación alineada ✅ (F05)
- **A37** medios operativos ✅ (upload real con límite, focal, alt, asignación hero/producto, `media_assign`)

### IA como experiencia central (G3)

- **A38** contrato de intención validado ✅ (`intent-v1`; gobierna cada turno del asesor; visible en la respuesta; total-con-envío sin ubicación = error accionable, jamás exclusión silenciosa del envío)
- **A39** facts con procedencia ✅ (validador de claims endurecido F10 + facts tipados con fuente)
- **A40** ranking auditable ✅ (`ranking-v1` 0.35/0.25/0.20/0.10/0.10 con `score_parts` y versión en evento; premium uplift declarado)
- **A41** evaluación ampliada ✅ (**202 casos** INT/OFR/CLM/PRV/ACT con 5 runners; ACT endureció `_propose_action`: lista blanca, UUID inválido → sin propuesta, límites de cantidad)

### Pagos (G4)

- **A42** modelos y estados por intento ✅ (`PaymentAttempt` + `PaymentEvent`; efectos exactamente-una-vez bajo bloqueo)
- **A43** contrato de adaptador + fake marcado ✅ (`payments/base.py`, `fake.py` sólo-tests, `manual.py` operativo real)
- **A44** adaptadores reales (Wompi/PayPal/BTCPay) ⛔ **bloqueo externo: credenciales sandbox** — el contrato está; el HTTP concreto se enchufa sin tocar checkout (declarado en PR)
- **A45** webhook autenticado ✅ (firma + coincidencia pedido/referencia/monto/moneda; firma inválida o monto distinto no toca el estado — vista HTTP `/pagos/webhook/<proveedor>/`)
- **A46** retorno no confirma ✅ (sólo notificación verificada o consulta autenticada; estados terminales no retroceden ni con eventos fuera de orden)
- **A47** conciliación ✅ (`reconcile_payments` + `reconcile_attempt`; recupera tras timeout)
- **A48** reembolsos ✅ (total/parcial con límites; nunca sobre lo no capturado; manual queda pendiente con evidencia; `partially_refunded→refunded` añadido a la máquina — hueco real encontrado por los tests)
- **A49** multi-vendedor «2 tiendas, 2 pagos» ✅ (`group_payment_status`: parcial nunca se muestra pagado completo)
- **A50** BTC 15 % preservado ✅ (regla legada intacta en los 2 productos elegibles; gateway BTCPay ⛔ igual que A44)

### Envíos (G4)

- **A51** modelos de envío ✅ (`Shipment` + `ShipmentEvent` por líneas/cantidades)
- **A52** adaptador API real (MyDHL) ⛔ **bloqueo externo: cuenta de proveedor** — contrato `shipping/base.py` listo; manual completo mientras tanto
- **A53** cotización con vigencia y fuente ✅ (manual: zona/tarifa del negocio, sin inventar cifras)
- **A54** creación idempotente + reconciliación antes de reintentar ✅ (mismo contenido = mismo envío; consulta antes de comprar otra etiqueta)
- **A55** tracking deduplicado ✅ (unique (evento, código); duplicado = no-op exacto)
- **A56** despachos parciales sin doble despacho ✅ (conteo por línea bajo bloqueo; digital/servicio no se empaquetan; «etiqueta creada» ≠ «en camino»)

### Experiencia y operación (G5/G6/G7)

- **A57** recorridos comprador/vendedor finales ✅ (E2E navegador: compra WK-000001, alta de negocio, estudio de diseño)
- **A58** página de componentes ✅ (`/plataforma/componentes/` renderiza el sistema real)
- **A59** dirección visual documentada ✅ (`docs/DIRECCION_VISUAL.md`)
- **A60** movimiento stop-motion + reducido ✅ (CSS steps + toggle persistente; evidencia móvil)
- **A61** salud ✅ (`/salud/` 200/503 sin datos sensibles, test HTTP)
- **A62** respaldo con restauración probada ✅ (`backup_reino` + `restore_check`: 142 registros → restauración verificada en base temporal; test en suite)
- **A63** rendimiento medido ⚠️ (índices por tienda/estado y consultas acotadas verificadas en tests; LCP/INP/CLS p75 de campo ⛔ requieren tráfico real — declarado)
- **A64** este cierre + PR #3 actualizado + CI verde en el SHA final ✅ (este documento; evidencia en `docs/capturas/` y `shots4/`)

### Hipótesis de negocio pendientes de validación humana (declaradas)

1. Tarifa $3.50 San Salvador (hipótesis, no dato).
2. Activo de marca WEINER vs Wiener (no se altera; el hero no lo usa).
3. Modo IA real: `REINO_AI_API_KEY`.
4. Pasarelas: credenciales sandbox Wompi/PayPal/BTCPay (A44/A50/A52).
5. RLS en Postgres (A13) y métricas de campo (A63).
