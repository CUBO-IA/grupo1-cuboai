"""Conciliación programada (§11.4.9): intentos vivos consultados contra el
proveedor; si el proceso muere entre pasos, la siguiente corrida lo retoma
(claim por estado; efectos idempotentes)."""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from reino import services_payments as pay
from reino.models import PaymentAttempt


class Command(BaseCommand):
    help = "Concilia intentos de pago vivos contra sus proveedores."

    def handle(self, *args, **options):
        alive = PaymentAttempt.objects.exclude(
            state__in=("captured", "failed", "cancelled", "expired",
                       "refunded", "disputed", "partially_refunded"))
        n_ok = n_err = 0
        for attempt in alive:
            try:
                _, err = pay.reconcile_attempt(attempt)
            except Exception as exc:  # un intento rojo no frena a los demás
                self.stderr.write(f"{attempt.public_id}: {exc}")
                n_err += 1
                continue
            n_err += bool(err)
            n_ok += not err
        self.stdout.write(self.style.SUCCESS(
            f"Conciliación: {n_ok} consultados, {n_err} con error."))
