"""Operación (G6): salud del servicio sin datos sensibles."""

from django.db import connection
from django.http import JsonResponse


def health(request):
    """200 si la app y su base responden; 503 si no. Sin secretos ni datos."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        db = "ok"
    except Exception:
        db = "error"
    status = 200 if db == "ok" else 503
    return JsonResponse({"status": db, "service": "reino-commerce"}, status=status)
