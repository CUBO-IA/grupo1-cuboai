# Guía técnica — Wiener Kingdom MVP (estado Task 7)

## Ejecución local (Windows)

Desde la carpeta `web/`:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser   # usuario del panel (is_staff)
.venv\Scripts\python.exe manage.py runserver
.venv\Scripts\python.exe manage.py test
```

`db.sqlite3`, `.venv/` y `staticfiles/` están en `.gitignore`. No hay secretos en el repositorio: `DJANGO_SECRET_KEY` se lee del entorno (con un valor de desarrollo por defecto).

## Flujo y rutas

| Paso | Ruta | Vista |
|---|---|---|
| Inicio / catálogo / ficha | `/`, `/productos/`, `/producto/<slug>/` | `views.inicio`, `productos`, `detalle` |
| Smart Fit (medidas) | `/smart-fit/` → `/smart-fit/<uuid>/` | `views.smart_fit`, `smart_fit_resultado` |
| Cotización | `POST /smart-fit/<uuid>/cotizar/` → `/quote/<uuid>/` | `smart_quote_crear`, `smart_quote` |
| Checkout | `/quote/<uuid>/checkout/` → `/order/<uuid>/` | `checkout`, `order_detail` |
| Panel privado | `/panel/login/`, `/panel/`, `/panel/orders/<uuid>/` | `tienda/panel.py` |

## Modelos

```
DogProfile 1 ──< Quote 1 ──0..1 Order 1 ──< OrderEvent
```

- Todas las URLs usan `public_id` (UUID); los ids numéricos no se exponen.
- Importes: `DecimalField`. Medidas: kg y cm.
- `Order` guarda un `snapshot` JSON (producto, precio, medidas) y cuatro estados independientes: `status`, `payment_status`, `production_status`, `shipping_status`.
- `OrderEvent` registra cada cambio de estado hecho desde el panel.

## Reglas de negocio implementadas

- **Precio:** siempre se calcula en el servidor desde `PRODUCTOS` (`services.get_base_price`). Cualquier precio enviado por el navegador se ignora.
- **Cotización:** provisional (solo precio base). El ajuste por talla **no existe** porque la regla comercial no está definida.
- **Pedido:** idempotente por cotización (un pedido por cotización, transacción + restricción única).
- **Pago:** no hay pasarela. Marcar un pedido como pagado es un registro manual de staff con referencia obligatoria.
- **Costos:** el panel muestra una estimación basada en el objetivo de $175, etiquetada como no verificada.

## Seguridad actual

- CSRF activo en todos los formularios POST.
- Panel: login de Django, solo `is_staff` activo; el resto recibe 403 o redirección al login.
- Sin límite de intentos de login, sin HTTPS ni cabeceras de producción configuradas, `DEBUG=True`: **no apto para producción** sin esos ajustes.

## Pruebas

`manage.py test` ejecuta las pruebas de catálogo, Smart Fit, cotización, checkout, panel y flujo completo (`tienda/test_*.py`, `tests.py`).

## Pendiente (decisiones del negocio)

Fórmula de precio por talla, tope de $850, descuento Bitcoin, costos reales, regla de si se puede producir sin pago o con precio provisional, productos que requieren cuello.
