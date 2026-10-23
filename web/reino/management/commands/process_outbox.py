"""Consumidor del outbox: trabajos diferidos recuperables (auditoría §9.4).

Cada evento se procesa UNA vez (idempotente por fila), con reintentos
acotados y resultado observable en la propia fila. Sin sistema transaccional
configurado, el correo queda registrado como «omitido: no configurado» —
nunca se simula un envío.

Uso:  python manage.py process_outbox [--loop SEGUNDOS]
"""

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from reino.models import OutboxEvent

MAX_RETRIES = 3


class Command(BaseCommand):
    help = "Procesa eventos diferidos del outbox (correo, métricas) de forma idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--loop", type=int, default=0,
                            help="Reejecutar cada N segundos (0 = una sola pasada).")

    def handle(self, *args, **options):
        while True:
            done, failed, skipped = self._pass()
            self.stdout.write(f"outbox: {done} procesados, {failed} fallidos, {skipped} omitidos")
            if not options["loop"]:
                return
            time.sleep(options["loop"])

    def _pass(self):
        from django.db import transaction
        done = failed = skipped = 0
        ids = list(OutboxEvent.objects.filter(
            status=OutboxEvent.Status.PENDING).order_by("pk").values_list("pk", flat=True))
        for pk in ids:
            with transaction.atomic():  # bloqueo por fila: dos workers no repiten
                event = OutboxEvent.objects.select_for_update(skip_locked=True).filter(
                    pk=pk, status=OutboxEvent.Status.PENDING).first()
                if event is None:
                    continue  # otro worker lo tomó (idempotencia de la cola)
                try:
                    result = self._dispatch(event)
                except Exception as exc:  # fallo aislado por evento; no detiene la cola
                    event.retries += 1
                    event.status = (OutboxEvent.Status.FAILED
                                    if event.retries >= MAX_RETRIES else OutboxEvent.Status.PENDING)
                    event.payload["last_error"] = str(exc)[:200]
                    event.save(update_fields=["retries", "status", "payload"])
                    failed += 1
                    continue
                if result == "skipped":
                    skipped += 1
                else:
                    done += 1
                event.status = OutboxEvent.Status.DONE
                event.processed_at = timezone.now()
                event.payload["result"] = result
                event.save(update_fields=["status", "processed_at", "payload"])
        return done, failed, skipped

    def _dispatch(self, event):
        if event.type == "order_confirmation_email":
            # Sin sistema transaccional: se registra el resultado honesto.
            # Cuando exista proveedor, acá va el envío real con plantilla.
            return "skipped: correo transaccional no configurado"
        if event.type == "metric":
            # Métricas de embudo: se conservan en el payload (agregación por
            # consulta); un worker externo puede consumirlas después.
            return "recorded"
        return "skipped: tipo desconocido"
