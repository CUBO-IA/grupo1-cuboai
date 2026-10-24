"""Estados de integraciones basados en COMPROBACIONES (AC25, §14).

Una clave presente solo significa «configurada». «Conexión comprobada»
requiere una prueba real ejecutada con fecha; «evaluación aprobada» requiere
el dataset con proveedor real; nunca se muestran secretos.
"""

from django.conf import settings
from django.utils import timezone

from .models import IntegrationState

State = IntegrationState.State


def get_state(key):
    row = IntegrationState.objects.filter(key=key).first()
    if row:
        return row
    return IntegrationState(key=key, state=_default_state(key),
                            detail=_default_detail(key))


def _default_state(key):
    if key == "ai":
        return State.CONFIGURED if settings.REINO_AI.get("API_KEY") else State.NOT_CONFIGURED
    if key == "email":
        return State.CONFIGURED if settings.REINO_EMAIL_ENABLED else State.NOT_CONFIGURED
    if key == "postgres":
        engine = settings.DATABASES["default"]["ENGINE"]
        return State.CONFIGURED if engine.endswith("postgresql") else State.NOT_CONFIGURED
    return State.NOT_CONFIGURED


def _default_detail(key):
    if key == "ai":
        if settings.REINO_AI.get("API_KEY"):
            return "Clave configurada. Falta comprobar la conexión y aprobar la evaluación."
        return "Sin clave del proveedor: el asesor usa la selección guiada por reglas."
    if key == "email":
        if settings.REINO_EMAIL_ENABLED:
            return f"Backend: {settings.EMAIL_BACKEND}. Falta una prueba de envío."
        return "Correo no habilitado: los eventos quedan bloqueados con estado preciso."
    if key == "postgres":
        engine = settings.DATABASES["default"]["ENGINE"]
        if engine.endswith("postgresql"):
            return "Conectado a PostgreSQL."
        return "SQLite activo: PostgreSQL pendiente de entorno (CI lo ejecuta como servicio)."
    return ""


def record_check(key, ok, detail=""):
    """Persiste el resultado de una comprobación REAL (botón «Probar»)."""
    row, _ = IntegrationState.objects.get_or_create(key=key)
    row.state = State.CONNECTION_OK if ok else State.ERROR
    row.detail = detail[:200]
    row.checked_at = timezone.now()
    row.save(update_fields=["state", "detail", "checked_at", "updated_at"])
    return row


def probe_ai():
    """Prueba REAL de conexión con el proveedor (llamada mínima)."""
    from .ai import adapter
    if not settings.REINO_AI.get("API_KEY"):
        return record_check("ai", False, "Sin clave: no hay conexión que probar.")
    try:
        ok, detail = adapter.probe()
    except Exception as exc:
        return record_check("ai", False, f"Error de conexión: {exc}"[:200])
    return record_check("ai", ok, detail)


def probe_email():
    """Prueba de envío al propio capturador/configuración (sin destinatario externo)."""
    from django.core.mail import send_mail
    if not settings.REINO_EMAIL_ENABLED:
        return record_check("email", False, "Correo no habilitado (REINO_EMAIL_ENABLED=0).")
    try:
        sent = send_mail("Prueba de conexión · Reino Commerce",
                         "Prueba interna del backend transaccional.",
                         settings.DEFAULT_FROM_EMAIL,
                         [settings.DEFAULT_FROM_EMAIL], fail_silently=False)
    except Exception as exc:
        return record_check("email", False, f"Error del backend: {exc}"[:200])
    return record_check("email", sent == 1,
                        "Envío de prueba aceptado por el backend." if sent
                        else "El backend no confirmó el envío.")


def all_states():
    return [get_state(key) for key in ("ai", "email", "payments", "postgres")]
