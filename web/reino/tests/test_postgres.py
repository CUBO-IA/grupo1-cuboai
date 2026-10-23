"""Pruebas de concurrencia REALES contra PostgreSQL (auditoría §9.3).

Corren SOLO con una base PostgreSQL configurada (DATABASE_URL/POSTGRES_*);
en SQLite se saltan explícitamente. En staging son OBLIGATORIAS: la prueba
A17 en SQLite con 2 hilos no evidencia el comportamiento con conexiones
reales (bloqueos de fila, serialización por tienda, unicidad de referencia).
"""

import threading
from unittest import skipUnless

from django.conf import settings
from django.db import connection

from reino import services_commerce as c
from reino.tests import ReinoTestCase

IS_POSTGRES = settings.DATABASES["default"]["ENGINE"].endswith("postgresql")


@skipUnless(IS_POSTGRES, "concurrencia real: requiere PostgreSQL (staging)")
class PostgresConcurrencyTests(ReinoTestCase):
    def test_ultima_unidad_dos_compradores_concurrentes(self):
        """Dos confirmaciones concurrentes por la última unidad: una gana,
        la otra recibe StockConflict; el stock jamás queda negativo."""
        v = self._variant()
        v.stock = 1
        v.save()
        results = {}

        def buyer(name):
            try:
                cart = c.get_open_cart(self.store_a, f"pg-{name}", create=True)
                c.add_item(cart, v, 1)
                ch = c.prepare_checkout(cart, "manual", idempotency_key=f"pg-{name}")
                order = c.confirm_checkout(ch, {"name": name, "email": f"{name}@e.invalid"},
                                           ch.idempotency_key)
                results[name] = ("order", order.reference)
            except c.StockConflict:
                results[name] = ("conflict", None)
            finally:
                connection.close()

        threads = [threading.Thread(target=buyer, args=(n,)) for n in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        outcomes = sorted(r[0] for r in results.values())
        self.assertEqual(outcomes, ["conflict", "order"])
        v.refresh_from_db()
        self.assertEqual(v.stock, 0)

    def test_referencias_unicas_bajo_concurrencia(self):
        """N pedidos concurrentes de la misma tienda: referencias únicas."""
        v = self._variant()
        v.stock = 20
        v.save()
        results, lock = [], threading.Lock()

        def buyer(i):
            try:
                cart = c.get_open_cart(self.store_a, f"pg-ref-{i}", create=True)
                c.add_item(cart, v, 1)
                ch = c.prepare_checkout(cart, "manual", idempotency_key=f"pg-ref-{i}")
                order = c.confirm_checkout(ch, {"name": "R", "email": "r@e.invalid"},
                                           ch.idempotency_key)
                with lock:
                    results.append(order.reference)
            finally:
                connection.close()

        threads = [threading.Thread(target=buyer, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), len(set(results)))

    def _variant(self):
        return self.product.variants.get(option_label="Talla M")
