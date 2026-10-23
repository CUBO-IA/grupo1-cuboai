# 03 · IA, memoria y recomendaciones (F5–F6)

## Royal Stylist: IA real con herramientas controladas

**Estado: implementado, pendiente de conexión** (puerta de aceptación §2: falta la clave del
proveedor). La tienda y la compra visual funcionan; el asesor informa su modo real.

### Arquitectura (`reino/ai/`)

| Archivo | Rol |
|---|---|
| `adapter.py` | Cliente OpenAI-compatible por `urllib` (sin dependencias nuevas). Config por entorno: `REINO_AI_API_KEY`, `BASE_URL`, `MODEL`, `TIMEOUT`. Timeout y errores tipados (`ProviderError`, `ProviderUnavailable`). La clave nunca en repo ni navegador. |
| `schemas.py` | Prompt de sistema con reglas inquebrantables + 11 especificaciones de herramientas (function-calling JSON). |
| `tools.py` | Implementación servidor de las 11 herramientas. El contexto (tienda, sesión, perfil permitido) lo inyecta el servidor. |
| `orchestrator.py` | Bucle ≤4 rondas de herramientas; historial acotado (12 mensajes); validación de salida; persistencia por `request_id`. |
| `fallback.py` | Modo por reglas **etiquetado** (contingencia honesta, no cumple IA real). |

### Herramientas (§11) — implementadas

`search_products`, `get_product_details`, `check_inventory`, `calculate_smart_fit`,
`recommend_products`, `get_store_policies` (RAG), `get_shipping_options`,
`get_customer_preferences`, `add_item_to_cart`, `get_cart`, `get_order_status`.

**No existen** herramientas para fijar precios, confirmar cobros, reembolsar, enviar
marketing ni SQL libre (`test_ai.py` lo verifica: `tool_not_allowed`).

### Validación anti-invención (A11)

Las tarjetas de producto se construyen **solo desde resultados de herramientas** con IDs
reales de la tienda; el texto del modelo jamás crea URLs, imágenes, precios ni botones.
Un `product_id` inventado no se hidrata (`get_product_details` devuelve lista vacía,
fail-closed). `get_order_status` solo ve pedidos de la sesión propietaria.

### Modo degradado honesto (A15)

Sin clave o con proveedor caído: responde el motor por reglas y la UI lo etiqueta
(«implementado pendiente de conexión» / «La IA no está disponible en este momento»).
Nunca se simula streaming ni respuestas preescritas como si fueran del modelo.
Prueba: `test_a15_ia_caida_modo_reglas_etiquetado`.

### Evaluación de proveedor (pendiente de clave)

Arnes preparado para la batería de 80 conversaciones del diseño: el orquestador acepta
cualquier proveedor compatible con chat.completions + tools; `test_ai.py` ejecuta el
flujo completo con un proveedor falso scriptado (patrón reutilizable para la batería).
Umbrales del diseño: 0 escrituras no autorizadas, 0 exposiciones cruzadas, ≥95 %
respuestas fundamentadas. **No ejecutado contra modelo real: falta `REINO_AI_API_KEY`.**

## Motor de recomendaciones (§13) — implementado

`services_recommend.py`, versión `ENGINE_VERSION = "v1"`:

- **Paso A** `normalize_intent`: ocasión, estilo, presupuesto (products/total), perfil.
- **Paso B** candidatos: publicados de la tienda, ocasión primero.
- **Paso C** filtros duros: stock > 0, presupuesto por pieza, talla incompatible excluye;
  lo desconocido NO excluye pero se etiqueta (`FIT_UNKNOWN`, separado de confirmados).
- **Paso D** score = 100 × (0.35 I + 0.22 F + 0.16 Q + 0.10 D + 0.10 P + 0.07 V) con
  renormalización por evidencia faltante; D es honestamente `None` en P0 (sin fechas
  confirmables) y se declara `DELIVERY_UNKNOWN`.
- **Paso E** hasta 3 opciones con códigos: `MATCH_OCCASION`, `MATCH_STYLE`,
  `FIT_RANGE_CONFIRMED`, `FIT_NEEDS_REVIEW`, `FIT_UNKNOWN`, `BUDGET_TOTAL_OK`,
  `DELIVERY_UNKNOWN`, `QUALITY_COMPLETE`, `EDITORIAL_FEATURED`.
- **Paso F** `compose_bundle`: complementos con ocasión/estilo compartida registrada,
  sin duplicar función (categoría), presupuesto acumulado estricto, stock obligatorio.
- **Trazabilidad:** cada corrida persiste `RecommendationEvent` (intención, candidatos,
  exclusiones con motivo, razones, versión). El LLM solo puede narrar esos códigos.

## Memoria y RAG (§12) — implementado P0

- **Estructurada:** `Measurement` (cm normalizados + valor/unidad originales + fecha +
  origen); medidas nuevas versionan, no pisan.
- **Consentimiento:** `Consent` por tienda+sesión+finalidad+versión; no premarcado;
  revocar borra preferencias derivadas (A14 verificado). Precedencia §12: instrucción
  actual > dato explícito > preferencia guardada > resumen.
- **Borrado de memoria:** `delete_profile_memory` elimina preferencias, resúmenes y foto;
  no toca pedidos (otra base de conservación) ni documentos públicos. Restauración de
  backups: pendiente operativa (A31 documentado en 05).
- **RAG léxico P0:** `KnowledgeDocument` por tienda con tema, audiencia, versión, aprobación
  y vigencia; la herramienta `get_store_policies` devuelve solo fragmentos publicados y
  vigentes de ESA tienda. Sin vector store (el diseño lo permite: «no es necesario un
  vector store para que exista generación aumentada con recuperación»). Embeddings = P1.
- **Seguridad de recuperación:** los documentos son datos sin autoridad; el prompt de
  sistema lo fija y `test_a11`/política de herramientas impiden ampliación de permisos (A12).

## Coste de IA

Sin llamadas reales aún: coste medido = $0. Fórmula para el piloto (del diseño):
tokens entrada × tarifa + salida × tarifa por llamada; registrar por conversación.
El adaptador ya devuelve usage cuando el proveedor lo incluye (campo reservado).

## Correcciones de la auditoría (23-oct-2026)

- **R07 · Memoria autorizada:** lectura única `authorized_measurement()` con
  finalidad y estado vigente; la usan contexto del modelo, herramientas,
  recomendador y storefront. Revocar impide TODO uso futuro; «Borrar memoria»
  elimina medidas, preferencias, resúmenes y conversación de la sesión.
- **R11 · Acciones por propuesta:** el modelo NUNCA ejecuta escrituras;
  propone (`ActionToken`: un solo uso, alcance tienda+sesión, 15 min,
  idempotente) y el comprador confirma en `/asesor/accion/`.
- **R12 · Texto verificado:** `_validate_answer()` contrasta precios,
  porcentajes y promesas del texto libre contra la evidencia del turno; sin
  soporte, la respuesta se reemplaza por abstención honesta.
- **Evaluación:** dataset versionado `reino/tests/eval_dataset.json` con
  **81 casos identificables** (FIT/BUD/DSC/IDM/ZON/MEM/TRN/TXT/AGG/AIA). La
  parte determinista corre en CI (`test_eval_dataset.py`); la evaluación con
  proveedor real queda pendiente de `REINO_AI_API_KEY` y debe registrar
  modelo/versión/fecha/latencia/coste.
