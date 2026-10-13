# Wiener Kingdom — MVP (CUBO_AI Challenge 2026)

Tienda Django para prendas de dachshund con medidas del perro (Smart Fit), cotización en el servidor (Smart Quote), checkout, pedidos persistentes y panel privado.

La aplicación está en [`web/`](web/). Documentación adicional en [`docs/`](docs/).

## Requisitos
- Python 3.12 o superior (probado con 3.12.13 en Windows 10)
- Django 5.2 (ver `web/requirements.txt`)

## Instalación y ejecución (Windows, PowerShell)

```powershell
cd web
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

- Sitio: http://127.0.0.1:8000/
- Panel privado: http://127.0.0.1:8000/panel/login/ (usuario creado con `createsuperuser`; debe ser `is_staff`)
- Pruebas: `.venv\Scripts\python.exe manage.py test`
- Migraciones nuevas: `manage.py makemigrations` y luego `manage.py migrate`

`db.sqlite3`, `.venv/` y `staticfiles/` no se versionan.

## Variables de entorno

| Variable | Obligatoria | Uso |
|---|---|---|
| `DJANGO_SECRET_KEY` | Solo en producción | Clave de firma de sesiones y CSRF. Si falta se usa un valor **solo de desarrollo**. |

No hay otras variables, credenciales ni claves de terceros. Para publicar hay que fijar además `DEBUG=False` y `ALLOWED_HOSTS` (hoy están en `config/settings.py` para desarrollo).

## Arquitectura mínima

```
Navegador ──► config/urls.py ──► tienda/urls.py
                                   ├─ views.py     catálogo (PRODUCTOS), Smart Fit, cotización, checkout, pedido, asistente
                                   ├─ panel.py     panel privado (solo staff)
                                   ├─ services.py  precio base, cotización, pedido, transiciones, costos
                                   ├─ assistant.py asistente guiado determinista
                                   ├─ forms.py     validación de medidas, checkout y costos
                                   └─ models.py    DogProfile, Quote, Order, OrderEvent
                                SQLite (db.sqlite3)
```

```
DogProfile 1 ──< Quote 1 ──0..1 Order 1 ──< OrderEvent
```

- El catálogo vive en el diccionario `PRODUCTOS` (`tienda/views.py`); las cotizaciones lo referencian por su clave.
- Las URLs de perfil, cotización y pedido usan UUID.
- El precio lo calcula siempre el servidor; el navegador solo elige producto.
- El pedido guarda un `snapshot` y cuatro estados independientes (pedido, pago, producción, envío).

## Rutas

| Ruta | Descripción |
|---|---|
| `/`, `/productos/`, `/producto/<slug>/` | Inicio, catálogo y fichas |
| `/guide/` | Asistente guiado |
| `/smart-fit/` | Medidas del perro |
| `/quote/<uuid>/`, `/quote/<uuid>/checkout/` | Cotización y checkout |
| `/order/<uuid>/` | Pedido y seguimiento del cliente |
| `/panel/`, `/panel/orders/<uuid>/` | Panel privado |

## Documentación
- [Guía técnica](docs/guia-tecnica.md)
- [Guion de demo](docs/guion-demo.md)
- [Checklist del MVP, IA y limitaciones](docs/mvp-checklist-y-limitaciones.md)
- [Task 2: catálogo y datos](docs/task-02-catalogo-datos.md)
- [Task 12: ensayo y alcance congelado](docs/task-12-ensayo-y-alcance.md)
- [Especificación comercial y su implementación](docs/especificacion-comercial.md)
- [Borrador de políticas (no publicado)](docs/politicas-borrador.md)
