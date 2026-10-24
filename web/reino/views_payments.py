"""HTTP de cobros (§11.4): webhook autenticado + consulta de estado.

El retorno del navegador NUNCA confirma un pago: sólo la notificación
verificada o la consulta autenticada lo hacen (A45/A46/A47).
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services_payments as pay


@csrf_exempt  # la autenticidad la da la FIRMA del proveedor, no el CSRF
@require_POST
def payment_webhook(request, provider):
    """Recibe notificaciones: verifica firma, pedido, referencia, importe y
    moneda ANTES de tocar estados; duplicadas son no-op (200 siempre que se
    procesan, para que el proveedor no reintente en loop)."""
    try:
        parsed = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "cuerpo inválido"}, status=400)
    try:
        attempt, err = pay.verify_and_apply_notification(
            provider, dict(request.headers), request.body, parsed)
    except Exception:
        return JsonResponse({"ok": False, "error": "proveedor desconocido"}, status=404)
    if err:
        # Firma/monto inválidos: NO cambian el estado financiero (A45).
        return JsonResponse({"ok": False, "error": err}, status=422)
    state = str(parsed.get("state") or "")
    if state:
        pay.apply_provider_state(attempt, state,
                                 provider_state=str(parsed.get("provider_state") or ""),
                                 event_id=str(parsed.get("event_id") or ""))
    return JsonResponse({"ok": True, "state": attempt.state})
