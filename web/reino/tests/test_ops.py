"""G6 · Operación: salud HTTP + respaldo con restauración real."""

import json
import os
import subprocess
import sys
import tempfile

from django.test import Client, TestCase, TransactionTestCase
from django.core.management import call_command


class HealthTests(TestCase):
    def test_salud_200_sin_datos_sensibles(self):
        r = Client().get("/salud/")
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertEqual(body["status"], "ok")
        self.assertNotIn("secret", json.dumps(body).lower())


class BackupTests(TestCase):
    def test_respaldo_y_restauracion_verificada(self):
        """El respaldo se genera y un PROCESO aparte lo restaura en una base
        temporal (como lo haría la operación real, aislado de los tests)."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[2]  # repo/web
        venv_py = root.parent / "venv" / "bin" / "python"
        py = venv_py if venv_py.exists() else sys.executable
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, REINO_SQLITE_PATH=os.path.join(tmp, "src.sqlite3"))
            r1 = subprocess.run(
                [str(py), "manage.py", "migrate", "--run-syncdb"],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(r1.returncode, 0, r1.stderr[-400:])
            r2 = subprocess.run(
                [str(py), "manage.py", "backup_reino", "--out", tmp],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(r2.returncode, 0, r2.stderr[-400:])
            backup = next(f for f in os.listdir(tmp) if f.startswith("reino_backup"))
            r3 = subprocess.run(
                [str(py), "manage.py", "restore_check", os.path.join(tmp, backup)],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(r3.returncode, 0, r3.stderr[-400:])
            self.assertIn("Restauración verificada", r3.stdout)
