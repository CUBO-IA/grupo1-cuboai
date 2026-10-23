# Wiener Kingdom · Reino Commerce

Boutique digital de moda y accesorios para dachshunds sobre **Reino Commerce**,
plataforma multi-tienda con LookLab (selección guiada por medidas y ocasión),
Royal Stylist (asesor con IA real y herramientas controladas) y Royal Passport
(perfiles y memoria con consentimiento).

- **Tienda 1:** Wiener Kingdom (catálogo real histórico) — `/s/wiener-kingdom/`
- **Tienda 2:** Estudio Nube Demo (papelería ficticia de demostración, sin cobros) — `/s/estudio-nube/`
- **Directorio:** `/tiendas/` · **Para negocios:** `/para-negocios/`
- **Flujos históricos preservados** (Smart Fit, Smart Quote «hecho a medida», panel de costos): `/productos/`, `/smart-fit/`, `/quote/…`, `/panel/…`

## Arranque (probado en Python 3.11 + Django 5.2)

```bash
cd web
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --reset  # 2 tiendas + catálogos + usuario de panel
python manage.py test             # 372 pruebas (289 históricas + 83 de plataforma)
python manage.py runserver        # http://127.0.0.1:8000/  (franja hacia la boutique)
```

Panel del comerciante: `http://127.0.0.1:8000/negocio/wiener-kingdom/`
usuario **`demo_staff` / `demo1234`** — credencial de DEMOSTRACIÓN, cámbiala fuera de local.

## IA real (Royal Stylist)

El asesor funciona en dos modos **etiquetados honestamente**:

- `rules` (por defecto): selección por reglas sobre el catálogo real. La UI lo indica.
- `ai`: modelo real con 11 herramientas controladas. Requiere variables de entorno
  (ver `.env.example`): `REINO_AI_API_KEY`, opcionalmente `REINO_AI_BASE_URL`,
  `REINO_AI_MODEL` (defecto `gpt-4o-mini`), `REINO_AI_TIMEOUT`.

Sin clave, el asesor informa «El asesor con IA no está disponible. Podés usar la
selección guiada» y la tienda opera completa. Las escrituras del asesor (agregar
al carrito) son propuestas que el comprador confirma con un permiso de un solo uso.

## Corrección de la auditoría (23-oct-2026)

El PR recibió una auditoría independiente con 13 hallazgos bloqueantes (R01–R13):
todos corregidos y probados (14 regresiones integradas sin cambiar su significado
+ dataset de evaluación de 81 casos + pruebas de panel/operación). Matriz completa
hallazgo→corrección→prueba→resultado en `docs/07_MATRIZ_AUDITORIA_R01_R13.md`.

## Pagos (estado honesto)

Pago **manual coordinado** y **Bitcoin manual con 15 % de descuento** al verificar el pago.
No hay pasarela electrónica conectada; todo pedido nace «pendiente de pago» y el equipo
lo verifica en el panel (transición registrada con usuario y nota).

## Documentación

| Doc | Contenido |
|---|---|
| `docs/00_AUDITORIA_INICIAL.md` | Estado real del repo, PRs, qué se ejecutó |
| `docs/01_PRODUCTO_Y_DISENO.md` | Visión, pantallas, tokens, adaptaciones al diseño |
| `docs/02_ARQUITECTURA_Y_DATOS.md` | Módulos, modelo de datos, aislamiento, concurrencia |
| `docs/03_IA_MEMORIA_Y_RECOMENDACIONES.md` | Orquestador, herramientas, RAG, consentimiento, motor |
| `docs/04_COMERCIO_Y_OPERACION.md` | Pagos, delivery, panel, comisiones |
| `docs/05_CALIDAD_Y_DESPLIEGUE.md` | Matriz de pruebas A01–A32, accesibilidad, arranque |
| `docs/06_NEGOCIO_Y_DEMO.md` | Hipótesis económicas, guion de demo 5 min, limitaciones |
| `docs/REFERENCIAS_Y_DECISIONES.md` | Fuentes, licencias de fuentes, decisiones registradas |
| `docs/STATUS.md` | Estado por módulo con evidencia y próximos pasos |
| `docs/proposal/` | Planificación previa del equipo (PR #1) |

## Estructura

```
web/
├── config/            # settings (env-driven) + urls (reino primero, legacy intacta)
├── tienda/            # app histórica: Smart Fit/Quote, carrito legacy, panel de costos
├── reino/             # plataforma multi-tienda (P0)
│   ├── models.py          # Merchant/Store, catálogo DB, pedidos, memoria, IA, outbox
│   ├── tenancy.py         # resolución de tienda/sesión (fail-closed)
│   ├── services_fit.py    # Smart Fit por regla versionada
│   ├── services_recommend.py  # motor v1 (elegibilidad→score→razones→bundle)
│   ├── services_commerce.py   # carrito/checkout/pedido/reservas/idempotencia
│   ├── services_memory.py     # consentimientos y borrado de memoria
│   ├── ai/                # adaptador LLM + herramientas + orquestador + fallback
│   ├── views_*.py         # storefront, looklab, stylist, cuenta, panel, plataforma
│   ├── management/commands/seed_demo.py
│   └── tests/             # 47 pruebas de aceptación (matriz A)
├── templates/reino/   # Royal Editorial (es, voseo)
└── static/reino/      # tokens CSS, fuentes OFL vendoradas, js ligero, imágenes demo
```

El Salvador · 2026
