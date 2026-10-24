"""Verificación de restauración (G6): carga un respaldo en una base SQLite
TEMPORAL y cuenta registros — prueba real de que el respaldo sirve."""

import json
import os
import sqlite3
import tempfile

from django.core import serializers
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Valida un respaldo restaurándolo en una base temporal."

    def add_arguments(self, parser):
        parser.add_argument("backup_path")

    def handle(self, *args, **opts):
        path = opts["backup_path"]
        if not os.path.exists(path):
            raise CommandError(f"No existe {path}")
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        from django.conf import settings
        from django.db import connection
        old_name = settings.DATABASES["default"]["NAME"]
        old_env = os.environ.get("REINO_SQLITE_PATH")
        try:
            os.environ["REINO_SQLITE_PATH"] = tmp.name
            settings.DATABASES["default"]["NAME"] = tmp.name
            connection.close()  # reabre ya contra la base temporal
            call_command("migrate", run_syncdb=True, verbosity=0)
            call_command("loaddata", path, verbosity=0)
            from django.apps import apps
            restored = sum(model.objects.count()
                           for model in apps.get_app_config("reino").get_models())
            self.stdout.write(self.style.SUCCESS(
                f"Restauración verificada: {restored} registros cargados en base temporal."))
        finally:
            settings.DATABASES["default"]["NAME"] = old_name
            if old_env is None:
                os.environ.pop("REINO_SQLITE_PATH", None)
            else:
                os.environ["REINO_SQLITE_PATH"] = old_env
            connection.close()  # la siguiente consulta reabre la base real
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
