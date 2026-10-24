"""Ejecutor determinista del dataset de evaluación versionado.

Dataset: reino/tests/eval_dataset.json (81 casos identificables con ID,
categoría, entrada y resultado esperado). Fuente: auditoría PR #3 + plan §23.

La parte DETERMINISTA corre en CI (este archivo): fit, presupuesto,
descuento, idempotencia, zonas, memoria, transiciones/roles, validación de
texto, stock agregado y acciones de IA con proveedor simulado. La evaluación
con proveedor REAL es una comprobación explícita aparte (requiere clave y se
registra con versión/fecha/latencia/coste, sin secretos).
"""

import json
import os
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone

from reino import services_commerce as c
from reino import services_fit, services_memory
from reino.ai import adapter, orchestrator
from reino.ai.tools import ToolContext, run_tool
from reino.models import (
    ActionToken, AIConversation, Consent, MerchantMember, Order, ShippingZone,
)
from reino.tests import ReinoTestCase
from reino.views_looklab import _reveal

DATASET_PATH = os.path.join(os.path.dirname(__file__), "eval_dataset.json")
AI = {"API_KEY": "fake-for-local-tests", "MAX_TOOL_ROUNDS": 4}
CUSTOMER = {"name": "Eval", "email": "eval@example.invalid"}


def load_cases(category):
    data = json.load(open(DATASET_PATH, encoding="utf-8"))
    return [c for c in data["cases"] if c["category"] == category]


class EvalDatasetTests(ReinoTestCase):
    """Un método por categoría; cada caso se identifica por su ID al fallar."""

    def _fresh_variant(self, label="Talla M", stock=5):
        """Variante con stock y reservas limpias para cada caso (aislamiento)."""
        from reino.models import StockReservation, Variant
        v = self.product.variants.get(option_label=label)
        v.stock = stock
        v.save()
        StockReservation.objects.filter(
            variant=v, status=StockReservation.Status.ACTIVE).update(
            status=StockReservation.Status.RELEASED)
        return v


    # ------------------------------------------------------------- FIT ----
    def test_fit(self):
        for case in load_cases("fit"):
            with self.subTest(case=case["id"], desc=case["description"]):
                m = case["input"]
                unit = m.get("unit", "cm")
                try:
                    chest = services_fit.to_cm(m["chest"], unit) if m.get("chest") else None
                    neck = services_fit.to_cm(m["neck"], unit) if m.get("neck") else None
                    back = services_fit.to_cm(m["back"], unit) if m.get("back") else None
                except services_fit.InvalidMeasurement:
                    chest = neck = back = None  # inválida => incertidumbre honesta
                result = services_fit.evaluate(self.product, chest_cm=chest,
                                               neck_cm=neck, back_cm=back)
                self.assertEqual(result["state"], case["expected"]["state"])
                cand = case["expected"]["candidate"]
                if cand:
                    self.assertIn(cand, result["candidates"])

    # ---------------------------------------------------------- BUDGET ----
    def test_budget(self):
        for case in load_cases("budget"):
            with self.subTest(case=case["id"], desc=case["description"]):
                result = _reveal(None, self.store_a, dict(case["input"]), None)
                cap = case["expected"]["max_total"]
                if cap:
                    self.assertLessEqual(result["selection_total"], Decimal(cap))

    # --------------------------------------------------------- DISCOUNT ---
    def test_discount(self):
        for case in load_cases("discount"):
            with self.subTest(case=case["id"], desc=case["description"]):
                self.product.bitcoin_discount_eligible = case["input"]["eligible"]
                self.product.save()
                v = self.product.variants.get(option_label="Talla M")  # $63
                cart = c.get_open_cart(self.store_a, f"eval-{case['id']}", create=True)
                c.add_item(cart, v, case["input"]["qty"])
                summary = c.cart_summary(cart, case["input"]["method"])
                self.assertEqual(summary["discount"], Decimal(case["expected"]["discount"]))

    # ------------------------------------------------------ IDEMPOTENCY ---
    def test_idempotency(self):
        for case in load_cases("idempotency"):
            op = case["input"]["op"]
            with self.subTest(case=case["id"], desc=case["description"]):
                v = self._fresh_variant()
                if op == "ai_action":
                    cart_key = f"eval-{case['id']}"
                    ctx = ToolContext(self.store_a, cart_key)
                    token = orchestrator._propose_action(
                        "add_item_to_cart",
                        {"variant_id": str(v.public_id), "quantity": 1}, ctx)
                    args = {"action_id": token.action_id}
                    for _ in range(case["input"]["repeats"]):
                        run_tool("add_item_to_cart", args, ctx)
                    cart = c.get_open_cart(self.store_a, cart_key)
                    self.assertEqual(cart.items.get().quantity, case["expected"]["units"])
                elif op == "prepare":
                    cart = c.get_open_cart(self.store_a, f"eval-{case['id']}", create=True)
                    c.add_item(cart, v, 1)
                    s1 = c.prepare_checkout(cart, "manual", idempotency_key=f"eval-{case['id']}")
                    s2 = c.prepare_checkout(cart, "manual", idempotency_key=f"eval-{case['id']}")
                    self.assertEqual(s1.pk, s2.pk)
                elif op == "confirm":
                    cart = c.get_open_cart(self.store_a, f"eval-{case['id']}", create=True)
                    c.add_item(cart, v, 1)
                    ch = c.prepare_checkout(cart, "manual", idempotency_key=f"eval-{case['id']}")
                    orders = {c.confirm_checkout(ch, CUSTOMER, f"eval-{case['id']}").pk
                              for _ in range(case["input"]["repeats"])}
                    self.assertEqual(len(orders), 1)
                elif op == "edit_checkout":
                    cart = c.get_open_cart(self.store_a, f"eval-{case['id']}", create=True)
                    c.add_item(cart, v, 1)
                    key = f"eval-{case['id']}"
                    c.prepare_checkout(cart, "manual", idempotency_key=key)
                    edited = c.prepare_checkout(cart, "bitcoin", idempotency_key=key)
                    self.assertEqual(edited.summary["payment_method"], "bitcoin")
                    current = c.CheckoutSession.objects.filter(cart=cart, is_current=True)
                    self.assertEqual(current.count(), 1)
                elif op == "edit_then_confirm":
                    cart = c.get_open_cart(self.store_a, f"eval-{case['id']}", create=True)
                    c.add_item(cart, v, 1)
                    key = f"eval-{case['id']}"
                    c.prepare_checkout(cart, "manual", idempotency_key=key)
                    ch = c.prepare_checkout(cart, "bitcoin", idempotency_key=key)
                    o1 = c.confirm_checkout(ch, CUSTOMER, ch.idempotency_key)
                    o2 = c.confirm_checkout(ch, CUSTOMER, ch.idempotency_key)
                    self.assertEqual(o1.pk, o2.pk)
                elif op == "cancel_twice":
                    cart = c.get_open_cart(self.store_a, f"eval-{case['id']}", create=True)
                    c.add_item(cart, v, 1)
                    ch = c.prepare_checkout(cart, "manual", idempotency_key=f"eval-{case['id']}")
                    order = c.confirm_checkout(ch, CUSTOMER, ch.idempotency_key)
                    c.apply_transition(order, "status", "cancelled")
                    stock_after = type(v).objects.get(pk=v.pk).stock
                    c._restock_once(order)  # reintento directo: no suma de nuevo
                    self.assertEqual(type(v).objects.get(pk=v.pk).stock, stock_after)

    # -------------------------------------------------------------- ZONE --
    def test_zone(self):
        for case in load_cases("zone"):
            with self.subTest(case=case["id"], desc=case["description"]):
                zone = None
                if case["input"]["zone"]:
                    zone = ShippingZone.objects.filter(
                        store=self.store_a, name=case["input"]["zone"]).first()
                try:
                    mode, zone_ok, fee = c.validate_shipping(
                        self.store_a, case["input"]["mode"], zone)
                    ok = True
                except c.CartError:
                    ok = False
                self.assertEqual(ok, case["expected"]["ok"])

    # ------------------------------------------------------------ MEMORY --
    def test_memory(self):
        for case in load_cases("memory"):
            with self.subTest(case=case["id"], desc=case["description"]):
                session = f"eval-{case['id']}"
                profile = self._profile(self.store_a, session=session)
                if case["input"].get("grant"):
                    mem = services_memory
                    mem.grant_consent(self.store_a, session,
                                      Consent.Purpose.MEASUREMENTS, profile)
                    mem.save_measurement(profile, chest_cm=36, neck_cm=24, back_cm=28)
                if case["input"].get("revoke"):
                    services_memory.revoke_consent(
                        self.store_a, session, Consent.Purpose.MEASUREMENTS, profile)
                if case["input"].get("delete"):
                    services_memory.delete_profile_memory(self.store_a, session, profile)
                    check = case["input"]["check"]
                    if check == "measurements":
                        self.assertEqual(profile.measurements.count(), 0)
                    elif check == "preferences":
                        self.assertEqual(profile.preferences.count(), 0)
                    elif check == "conversation":
                        self.assertEqual(
                            AIConversation.objects.filter(
                                store=self.store_a, session_key=session).count(), 0)
                    continue
                ctx = ToolContext(self.store_a, session, profile)
                context = orchestrator._memory_context(ctx)
                self.assertEqual("pecho 36" in context, case["expected"]["in_context"])

    # -------------------------------------------------------- TRANSITION --
    def test_transition(self):
        for case in load_cases("transition"):
            with self.subTest(case=case["id"], desc=case["description"]):
                role, field, to = (case["input"]["role"], case["input"]["field"],
                                   case["input"]["to"])
                user = User.objects.create_user(username=f"eval-{case['id']}")
                member = MerchantMember.objects.create(user=user, merchant=self.merchant_a,
                                                       role=role)
                if field is None:
                    # Capacidad de catálogo (matriz rol→capacidad).
                    self.assertEqual(c.member_can(member, "catalog"),
                                     case["expected"]["allowed"])
                    continue
                v = self._fresh_variant()
                cart = c.get_open_cart(self.store_a, f"eval-{case['id']}", create=True)
                c.add_item(cart, v, 1)
                ch = c.prepare_checkout(cart, "manual", idempotency_key=f"eval-{case['id']}")
                order = c.confirm_checkout(ch, CUSTOMER, ch.idempotency_key)
                note = "comprobante verificado #1" if not str(to).endswith("no_note") else ""
                to_value = "paid" if str(to).endswith("no_note") else to
                try:
                    c.apply_transition(order, field, to_value, user=user,
                                       note=note, member=member)
                    allowed = True
                except c.CartError:
                    allowed = False
                self.assertEqual(allowed, case["expected"]["allowed"])

    # -------------------------------------------------------- TEXT GUARD --
    def test_text_guard(self):
        for case in load_cases("text_guard"):
            with self.subTest(case=case["id"], desc=case["description"]):
                answer = case["input"]["answer"]
                evidence = ['{"price": "$45.00", "products": []}'] \
                    if case["input"]["with_evidence"] else []
                _text, problems = orchestrator._validate_answer(answer, evidence)
                self.assertEqual(bool(problems), case["expected"]["rejected"])

    # --------------------------------------------------------- AGGREGATE --
    def test_aggregate(self):
        for case in load_cases("aggregate"):
            with self.subTest(case=case["id"], desc=case["description"]):
                v = self._fresh_variant(stock=case["input"]["stock"])
                cart = c.get_open_cart(self.store_a, f"eval-{case['id']}", create=True)
                for i, qty in enumerate(case["input"]["lines"]):
                    c.add_item(cart, v, qty,
                               recipient=self._profile(self.store_a,
                                                       session=f"eval-{case['id']}", alias=f"P{i}"))
                try:
                    c.prepare_checkout(cart, "manual", idempotency_key=f"eval-{case['id']}")
                    conflict = False
                except c.StockConflict:
                    conflict = True
                self.assertEqual(conflict, case["expected"]["conflict"])

    # -------------------------------------------------------- AI ACTIONS --
    @override_settings(REINO_AI=AI)
    def test_ai_actions(self):
        for case in load_cases("ai_actions"):
            with self.subTest(case=case["id"], desc=case["description"]):
                session = f"eval-{case['id']}"
                variant = self.product.variants.get(option_label="Talla M")
                if not case["input"].get("authorized"):
                    # El modelo solicita escritura: el orquestador propone,
                    # NO ejecuta (R11).
                    conv = AIConversation.objects.create(store=self.store_a,
                                                         session_key=session)
                    first = {"role": "assistant", "content": None,
                             "tool_calls": [{"id": "x", "type": "function",
                                             "function": {"name": "add_item_to_cart",
                                                          "arguments": '{"variant_id":"' + str(variant.public_id) + '","quantity":1}'}}]}
                    last = {"role": "assistant", "content": "¿Lo agrego?"}
                    with mock.patch.object(adapter, "chat", side_effect=[first, last]):
                        reply = orchestrator.respond(
                            conv, case["input"].get("message", "agregalo"),
                            ToolContext(self.store_a, session))
                    cart = c.get_open_cart(self.store_a, session)
                    self.assertEqual(cart is None or cart.items.count() == 0,
                                     case["expected"]["cart_empty"])
                    self.assertTrue(reply["proposed_actions"])
                else:
                    ctx = ToolContext(self.store_a, session)
                    if case["input"].get("expired"):
                        token = ActionToken.objects.create(
                            action_id=f"eval-{case['id']}", store=self.store_a,
                            session_key=session, tool="add_item_to_cart",
                            payload={"variant_id": str(variant.public_id), "quantity": 1},
                            expires_at=timezone.now())
                        result = run_tool("add_item_to_cart",
                                          {"action_id": token.action_id}, ctx)
                        self.assertEqual(result["error"], case["expected"]["error"])
                    else:
                        token = orchestrator._propose_action(
                            "add_item_to_cart",
                            {"variant_id": str(variant.public_id), "quantity": 1}, ctx)
                        run_tool("add_item_to_cart", {"action_id": token.action_id}, ctx)
                        cart = c.get_open_cart(self.store_a, session)
                        self.assertEqual(cart.items.get().quantity,
                                         case["expected"]["units"])
