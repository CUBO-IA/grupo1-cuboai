"""Pruebas de concurrencia REALES contra PostgreSQL (revisión 2, §4 y §18).

Corren SOLO con PostgreSQL configurado (DATABASE_URL/POSTGRES_*); en SQLite
se saltan explícitamente y en CI el job de PostgreSQL las ejecuta SIN skip
(AC20).

Diseño corregido tras la revisión:
- `TransactionTestCase`: los datos de la fixture quedan CONFIRMADOS; las
  conexiones de los hilos los ven (un TestCase envuelto en transacción los
  ocultaría).
- Conexión separada por hilo, barrera de inicio, excepciones CAPTURADAS y
  reportadas, `join` con TIMEOUT y conteo EXACTO de resultados: un hilo que
  muere en silencio nunca da un falso verde.
"""

import threading
from unittest import skipUnless

from django.conf import settings
from django.db import connection, connections
from django.test import TransactionTestCase

from reino import services_commerce as c
from reino.ai import orchestrator
from reino.ai.tools import ToolContext, run_tool
from reino.models import Order
from reino.tests import ReinoTestCase

IS_POSTGRES = settings.DATABASES["default"]["ENGINE"].endswith("postgresql")


class _ConcurrencyBase(TransactionTestCase):
    """Fixture confirmada (misma que ReinoTestCase) para hilos reales."""

    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ReinoTestCase.setUpTestData()
        for name in ("merchant_a", "store_a", "merchant_b", "store_b",
                     "product", "product2", "product_b"):
            setattr(cls, name, getattr(ReinoTestCase, name))

    def _variant(self):
        return self.product.variants.get(option_label="Talla M")

    def _run_threads(self, workers):
        """Lanza `workers` (lista de callables con nombre) con barrera de
        inicio, captura de excepciones y join con timeout. Devuelve
        {nombre: ("ok", valor) | ("error", excepción)} — jamás pierde un hilo.
        """
        barrier = threading.Barrier(len(workers) + 1)
        results = {}

        def wrap(name, fn):
            def run():
                try:
                    barrier.wait(timeout=15)
                    results[name] = ("ok", fn())
                except Exception as exc:  # capturada: ningún fallo invisible
                    results[name] = ("error", exc)
                finally:
                    connections.close_all()  # conexión propia del hilo
            return run

        threads = [threading.Thread(target=wrap(name, fn), name=name, daemon=True)
                   for name, fn in workers]
        for t in threads:
            t.start()
        barrier.wait(timeout=15)  # largada simultánea
        for t in threads:
            t.join(timeout=30)
        alive = [t.name for t in threads if t.is_alive()]
        self.assertFalse(alive, f"Hilos sin terminar (timeout): {alive}")
        # Conteo exacto: un resultado por hilo, ni más ni menos.
        self.assertEqual(len(results), len(workers),
                         f"Resultados perdidos: {set(n for n, _ in workers) - set(results)}")
        return results


@skipUnless(IS_POSTGRES, "concurrencia real: requiere PostgreSQL (CI/staging)")
class PostgresConcurrencyTests(_ConcurrencyBase):
    def _buy(self, name):
        def do():
            cart = c.get_open_cart(self.store_a, f"pg-{name}", create=True)
            c.add_item(cart, self._variant(), 1)
            ch = c.prepare_checkout(cart, "manual", idempotency_key=f"pg-{name}")
            return c.confirm_checkout(ch, {"name": name, "email": f"{name}@e.invalid"},
                                      ch.idempotency_key)
        return do

    def test_ultima_unidad_dos_compradores_concurrentes(self):
        """Última unidad, dos compradores a la vez: exactamente UN pedido,
        UN conflicto de negocio comprensible y stock jamás negativo (AC20)."""
        v = self._variant()
        v.stock = 1
        v.save()
        results = self._run_threads([("a", self._buy("a")), ("b", self._buy("b"))])

        orders, conflicts, errors = [], [], []
        for name, (kind, value) in results.items():
            if kind == "error":
                if isinstance(value, c.StockConflict):
                    conflicts.append(name)
                else:
                    errors.append(f"{name}: {value!r}")
            else:
                orders.append(value)
        self.assertEqual(errors, [], "Errores inesperados en hilos")
        self.assertEqual(len(orders), 1, "Debe crearse exactamente un pedido")
        self.assertEqual(len(conflicts), 1, "El otro comprador recibe conflicto claro")
        v.refresh_from_db()
        self.assertEqual(v.stock, 0)

    def test_doble_confirmacion_mismo_intento_un_pedido(self):
        """Dos confirmaciones simultáneas del MISMO intento: un solo pedido y
        ambas solicitudes obtienen el mismo resultado (idempotencia real)."""
        v = self._variant()
        cart = c.get_open_cart(self.store_a, "pg-doble", create=True)
        c.add_item(cart, v, 1)
        ch = c.prepare_checkout(cart, "manual", idempotency_key="pg-doble")

        def confirm():
            session = type(ch).objects.get(pk=ch.pk)  # instancia propia del hilo
            return c.confirm_checkout(session, {"name": "D", "email": "d@e.invalid"},
                                      ch.idempotency_key)

        results = self._run_threads([("c1", confirm), ("c2", confirm)])
        orders, errors = [], []
        for name, (kind, value) in results.items():
            (errors if kind == "error" else orders).append(value)
        self.assertEqual(errors, [], f"Errores: {errors!r}")
        self.assertEqual({o.pk for o in orders}.__len__(), 1)
        self.assertEqual(Order.objects.filter(idempotency_key=ch.idempotency_key).count(), 1)
        v.refresh_from_db()
        self.assertEqual(v.stock, 4)  # 5 iniciales - 1

    def test_doble_cancelacion_no_duplica_restitucion(self):
        """AC05 con PostgreSQL: dos solicitudes con instancias distintas del
        mismo pedido no restituyen dos veces el inventario."""
        v = self._variant()
        initial = v.stock
        cart = c.get_open_cart(self.store_a, "pg-cancel", create=True)
        c.add_item(cart, v, 1)
        ch = c.prepare_checkout(cart, "manual", idempotency_key="pg-cancel")
        order = c.confirm_checkout(ch, {"name": "C", "email": "c@e.invalid"},
                                   ch.idempotency_key)

        def cancel():
            instance = Order.objects.get(pk=order.pk)  # instancia propia
            return c.apply_transition(instance, "status", "cancelled")

        results = self._run_threads([("x1", cancel), ("x2", cancel)])
        errors = [v for kind, v in results.values() if kind == "error"]
        self.assertEqual(errors, [], f"Errores: {errors!r}")
        v.refresh_from_db()
        self.assertEqual(v.stock, initial, "La restitución ocurrió más de una vez")

    def test_acciones_del_asesor_simultaneas_una_sola_mutacion(self):
        """AC06: dos confirmaciones concurrentes de la MISMA propuesta del
        asesor agregan una sola vez al carrito."""
        v = self._variant()
        ctx = ToolContext(self.store_a, "pg-action")
        token = orchestrator._propose_action(
            "add_item_to_cart", {"variant_id": str(v.public_id), "quantity": 1}, ctx)

        def confirm():
            return run_tool("add_item_to_cart", {"action_id": token.action_id},
                            ToolContext(self.store_a, "pg-action"))

        results = self._run_threads([("a1", confirm), ("a2", confirm)])
        oks, errors = [], []
        for kind, value in results.values():
            if kind == "error":
                errors.append(value)
            elif isinstance(value, dict) and value.get("ok"):
                oks.append(value)
            else:
                errors.append(value)
        self.assertEqual(errors, [], f"Errores: {errors!r}")
        self.assertEqual(len(oks), 2, "Ambas reciben el resultado guardado")
        cart = c.get_open_cart(self.store_a, "pg-action")
        self.assertEqual(cart.items.get().quantity, 1)

    def test_referencias_unicas_bajo_concurrencia(self):
        """N pedidos concurrentes de la misma tienda: N resultados EXACTOS y
        N referencias únicas (la unicidad está respaldada por la base)."""
        v = self._variant()
        v.stock = 20
        v.save()
        n = 4
        workers = [(f"r{i}", self._buy(f"ref-{i}")) for i in range(n)]
        results = self._run_threads(workers)
        refs, errors = [], []
        for kind, value in results.values():
            if kind == "error":
                errors.append(value)
            else:
                refs.append(value.reference)
        self.assertEqual(errors, [], f"Errores: {errors!r}")
        self.assertEqual(len(refs), n, "Conteo exacto de pedidos creados")
        self.assertEqual(len(set(refs)), n, "Referencias duplicadas")
