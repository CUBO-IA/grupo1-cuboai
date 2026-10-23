# ARCHITECTURE — Wiener Kingdom (Django conservado, transición por etapas)

> Regla: NO reescribir Django por Next.js. Mejorar en etapas, preservando URLs, formularios CSRF, clases, estados, migraciones y suite.

## 1. Arquitectura actual (verificada)
```mermaid
flowchart LR
  subgraph Navegador
    U[Cliente]
  end
  subgraph Django ["web/ (Django 5.2)"]
    CF[config/urls.py] --> TU[tienda/urls.py]
    TU --> V[views.py · catálogo, smart fit, quote, carrito, checkout, pedido]
    TU --> P[panel.py · staff]
    V --> S[services.py · precio/cotización/pedido/transiciones/costos/descuento]
    V --> A[assistant.py · determinista]
    V --> F[forms.py · validación]
    S --> M[models.py]
    M --> DB[(SQLite dev)]
    V --> C[catalog.py · PRODUCTOS 8 activos]
    A --> C
  end
  U --> CF
```

## 2. Modelo de datos (resumen)
```mermaid
erDiagram
  DOGPROFILE ||--o{ QUOTE : "1..n"
  QUOTE ||--o| ORDER : "0..1"
  QUOTE }o--o| CART : "línea"
  CART ||--o| ORDER : "0..1"
  ORDER ||--o{ ORDERLINE : "líneas"
  ORDER ||--o{ ORDEREVENT : "historial"
  PRODUCTCOST ||--o{ MATERIALLINE : "desglose"
  PRODUCTPAYMENTRULE |o--|| PRODUCTOS : "regla BTC por slug"
```

## 3. Arquitectura objetivo (fases, módulos opcionales posteriores)
```mermaid
flowchart TB
  subgraph Capa1["Capa web/cliente"]
    T[Django templates + CSS/JS accesible]
  end
  subgraph Capa2["Capa comercio/backend"]
    DJ[Django: fuente de verdad]
    SV[services: catálogo, pagos, pedidos, inventario, soporte]
  end
  subgraph Capa3["Capa datos (posterior)"]
    PG[(PostgreSQL)]
    CR[(Celery/Redis · colas)]
  end
  subgraph Capa4["Integraciones (posterior, sandbox)"]
    PSP[PSP sandbox]
    BTC[Bitcoin on-chain/Lightning]
    LOG[Logística/3PL]
    MKT[Marketing/email]
  end
  subgraph Capa5["Agentes (OpenClaw)"]
    DIR[wk-director coordinador]
  end
  T --> DJ
  DJ --> SV
  SV --> PG
  SV --> CR
  SV --> PSP
  SV --> BTC
  SV --> LOG
  SV --> MKT
  DIR -. orquesta, no reemplaza backend .-> DJ
```

## 4. Principios de transición
1. **Primero templates + CSS/JS accesible**, sin tocar lógica de pagos.
2. **Precio siempre en servidor** (services.py); el navegador solo elige producto/cantidad.
3. **Estados independientes** de pago/producción/envío se conservan.
4. **Módulos opcionales** (Postgres, Celery/Redis, SPA, servicios externos) solo si el problema lo justifica y hay ADR.
5. **Agentes OpenClaw** coordinan desarrollo en workspaces separados; NO reemplazan el backend de negocio.

## 5. Sitemap real (rutas verificadas en tienda/urls.py)
```
/                          inicio
/productos/                catálogo
/producto/<slug>/          ficha
/smart-fit/                medidas
/guide/                    asistente guiado
/smart-fit/<uuid>/         resultado medidas
/smart-fit/<uuid>/editar/  editar perfil
/smart-fit/<uuid>/cotizar/ crear cotización
/quote/<uuid>/             cotización
/quote/<uuid>/cantidad/    ajustar cantidad
/quote/<uuid>/checkout/    checkout directo
/quote/<uuid>/to-cart/     a carrito
/cart/ · /cart/add/ · /cart/checkout/
/cart/line/<uuid>/ · /cart/line/<uuid>/remove/
/order/<uuid>/             seguimiento cliente
/panel/login/ · /panel/logout/
/panel/ · /panel/orders/<uuid>/ · /panel/orders/<uuid>/sheet/
/panel/payments/ · /panel/measurements/ · /panel/costs/ · /panel/costs/<slug>/
```

## 6. Ramas recomendadas (para cuando exista fork autorizado)
- `proposal/wk-atlas-and-architecture` — docs + preview aislado (PR docs-only primero)
- `feature/wk-visual-refresh` — CSS/templates sin tocar pagos
- `feature/wk-staging-hardening` — seguridad
- `feature/wk-payments-sandbox` — PSP sandbox (tras decisión legal)
- `experiment/wk-innovation-lab` — funciones avanzadas aisladas