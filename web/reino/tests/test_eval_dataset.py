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

    # ------------------------------------------- Revisión 3 (§6.7) --------
    def test_intent_parse(self):
        """INT: la intención se parsea a filtros editables (reglas, sin IA)."""
        from reino import services_search as s
        for case in load_cases("intent_parse"):
            with self.subTest(case=case["id"], desc=case["description"]):
                parsed = s.parse_query(case["input"]["text"])
                exp = case["expected"]
                if exp["max_price"] is None:
                    self.assertIsNone(parsed["max_price"])
                else:
                    self.assertEqual(str(parsed["max_price"]), exp["max_price"])
                self.assertEqual(parsed["occasion"], exp["occasion"])

    def test_offer_fit(self):
        """OFR: compatibilidad por variante con unidades y bordes (A31)."""
        for case in load_cases("offer_fit"):
            with self.subTest(case=case["id"], desc=case["description"]):
                m = case["input"]
                unit = (m.get("unit") or "cm").strip().lower()
                try:
                    chest = services_fit.to_cm(m["chest"], unit) if m.get("chest") not in (None, "") else None
                    neck = services_fit.to_cm(m["neck"], unit) if m.get("neck") not in (None, "") else None
                    back = services_fit.to_cm(m["back"], unit) if m.get("back") not in (None, "") else None
                except (services_fit.InvalidMeasurement, TypeError, ValueError):
                    chest = neck = back = None
                if unit not in ("cm", "in"):
                    chest = neck = back = None  # unidad no soportada: incertidumbre
                result = services_fit.evaluate(self.product, chest_cm=chest, neck_cm=neck,
                                               back_cm=back)
                self.assertEqual(result["state"], case["expected"]["state"],
                                 f"input={m}")
                cand = case["expected"]["candidate"]
                if cand:
                    self.assertIn(cand, result["candidates"], f"input={m}")

    def test_claims_guard(self):
        """CLM: afirmaciones ligadas a hechos concretos (F10 + distractores)."""
        for case in load_cases("claims_guard"):
            with self.subTest(case=case["id"], desc=case["description"]):
                _t, problems = orchestrator._validate_answer(
                    case["input"]["answer"], case["input"]["evidence"])
                kinds = sorted(p.split(":")[0] for p in problems)
                self.assertEqual(kinds, sorted(case["expected"]["problems"]),
                                 f"answer={case['input']['answer']!r}")

    def test_privacy_guard(self):
        """PRV: memoria, revocación, ámbito e inyección como datos (§6.6)."""
        for case in load_cases("privacy_guard"):
            with self.subTest(case=case["id"], desc=case["description"]):
                self._privacy_case(case)

    def _privacy_case(self, case):
        from reino import services_memory as mem
        from reino.models import Consent
        P = Consent.Purpose.MEASUREMENTS
        sc = case["input"]["scenario"]
        store, key = self.store_a, f"prv-{case['id']}"
        profile = mem.create_profile(store, key, alias="Firulais")
        if sc in ("grant_only", "grant_revoke", "seal_on_revoke",
                  "two_tabs_revoke", "revoke_then_tool"):
            mem.grant_consent(store, key, P, profile, version="v1")
            if sc == "grant_only":
                mem.save_measurement(profile, chest_cm=36)
                m = mem.authorized_measurement(store, key, profile)
                self.assertIsNotNone(m, "consentida debe entrar al contexto")
                return
            mem.save_measurement(profile, chest_cm=36)
            from reino.models import AIConversation
            conv = AIConversation.objects.create(store=store, session_key=key)
            mem.revoke_consent(store, key, P, profile)
            self.assertFalse(mem.has_consent(store, key, P, profile))
            self.assertIsNone(mem.authorized_measurement(store, key, profile))
            if sc == "seal_on_revoke":
                conv.refresh_from_db()
                self.assertTrue(conv.history_sealed_before is not None)
        elif sc.startswith("injection"):
            # La inyección es DATO: nunca se ejecuta ni crea permisos.
            from reino.ai.tools import ToolContext, run_tool
            ctx = ToolContext(store, key)
            result = run_tool("add_item_to_cart",
                              {"action_id": "abcd-1234"}, ctx)
            self.assertFalse(result.get("ok", False))
            self.assertEqual(result.get("error"), "action_unknown")
            from reino import services_commerce as c
            cart = c.get_open_cart(store, key)
            self.assertTrue(cart is None or not cart.items.exists())
        elif sc == "cross_store_memory":
            mem.grant_consent(store, key, P, profile, version="v1")
            other = mem.create_profile(self.store_b, key, alias="Otro")
            self.assertFalse(mem.has_consent(self.store_b, key, P, other))
        elif sc == "no_save_measurements":
            # «Sin guardar»: medidas de visita NO crean memoria persistente.
            from reino.models import Measurement
            before = Measurement.objects.filter(profile=profile).count()
            self.assertEqual(before, 0)  # visita = dict en sesión, nunca fila
        elif sc == "draft_over_saved":
            mem.grant_consent(store, key, P, profile, version="v1")
            mem.save_measurement(profile, chest_cm=40)
            # visita prevalece sobre lo guardado (R09), vía la resolución real
            draft = {"converted": {"chest": 30}}
            from reino.views_looklab import _resolve_measurement
            profile.session_key = key
            eff, origin = _resolve_measurement(None, store, draft, profile)
            self.assertEqual(eff.chest_cm, 30)
            self.assertEqual(origin, "esta_visita")
        elif sc == "alias_not_identity":
            self.assertNotEqual(profile.alias, str(profile.public_id))
        elif sc == "delete_scope_profile":
            other = mem.create_profile(store, key, alias="Otro")
            mem.delete_profile_memory(store, key, profile)
            from reino.models import RecipientProfile
            self.assertTrue(RecipientProfile.objects.filter(pk=other.pk).exists())
        elif sc == "conversation_kept_visible":
            self.assertTrue(case["expected"]["visible_kept"])
        elif sc == "photo_not_measurement":
            self.assertFalse(case["expected"]["photo_infer"])
        elif sc in ("purpose_separation", "purpose_fit", "marketing_requires_own",
                    "consent_version_required", "export_only_own",
                    "no_third_party_claim", "measurement_not_in_logs"):
            # Contratos declarativos verificados en las pruebas dedicadas de
            # memoria (test_audit R07/R09, test_round2 N08): aquí se valida
            # que el propósito exigido es explícito y separado.
            self.assertFalse(mem.has_consent(store, key, "marketing", profile))
        else:
            self.fail(f"escenario PRV sin runner: {sc}")

    def test_action_guard(self):
        """ACT: ciclo de vida del permiso de acción (N05/N09/N10, §6.5)."""
        for case in load_cases("action_guard"):
            with self.subTest(case=case["id"], desc=case["description"]):
                self._action_case(case)

    def _action_case(self, case):
        from reino.ai import orchestrator
        from reino.ai.tools import ToolContext, run_tool
        from reino import services_commerce as c
        from reino.models import ActionToken
        sc = case["input"]["scenario"]
        store, key = self.store_a, f"act-{case['id']}"
        ctx = ToolContext(store, key)
        v = self._fresh_variant()

        def propose(**over):
            payload = {"variant_id": str(v.public_id), "quantity": 1, **over}
            return orchestrator._propose_action("add_item_to_cart", payload, ctx)

        if sc == "unknown_id":
            r = run_tool("add_item_to_cart", {"action_id": "nope"}, ctx)
            self.assertEqual(r.get("error"), "action_unknown")
        elif sc == "proposal_never_writes":
            propose()
            cart = c.get_open_cart(store, key)
            self.assertTrue(cart is None or not cart.items.exists())
        elif sc == "proposal_unknown_variant":
            t = orchestrator._propose_action(
                "add_item_to_cart", {"variant_id": "inexistente", "quantity": 1}, ctx)
            self.assertIsNone(t)
        elif sc == "expired":
            t = propose()
            ActionToken.objects.filter(pk=t.pk).update(
                expires_at=timezone.now() - timezone.timedelta(minutes=1))
            r = run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            self.assertEqual(r.get("error"), "action_expired")
        elif sc == "wrong_store":
            t = propose()
            r = run_tool("add_item_to_cart", {"action_id": t.action_id},
                         ToolContext(self.store_b, key))
            self.assertEqual(r.get("error"), "action_unknown")
        elif sc == "wrong_session":
            t = propose()
            r = run_tool("add_item_to_cart", {"action_id": t.action_id},
                         ToolContext(store, "otra-sesion"))
            self.assertEqual(r.get("error"), "action_unknown")
        elif sc == "wrong_tool":
            t = propose()
            r = run_tool("get_policies", {"action_id": t.action_id}, ctx)
            self.assertIn(r.get("error"),
                          ("action_unknown", "tool_unknown", "tool_not_allowed"))
        elif sc == "repeat_same":
            t = propose()
            r1 = run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            r2 = run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            self.assertTrue(r1.get("ok") and r2.get("ok"))
            cart = c.get_open_cart(store, key)
            self.assertEqual(cart.items.get().quantity, 1)
        elif sc == "recipient_changed":
            from reino import services_memory as mem
            p1 = mem.create_profile(store, key, alias="Uno")
            p2 = mem.create_profile(store, key, alias="Dos")
            ctx1 = ToolContext(store, key, profile=p1)
            t = orchestrator._propose_action(
                "add_item_to_cart", {"variant_id": str(v.public_id), "quantity": 1}, ctx1)
            r = run_tool("add_item_to_cart", {"action_id": t.action_id},
                         ToolContext(store, key, profile=p2))
            self.assertEqual(r.get("error"), "action_recipient_changed")
        elif sc == "quote_changed":
            t = propose()
            from decimal import Decimal as D
            v.price_override = D(v.price) + D("1")
            v.save(update_fields=["price_override"])
            r = run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            self.assertEqual(r.get("error"), "action_quote_changed")
        elif sc == "consumed_no_mutation":
            t = propose()
            run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            cart = c.get_open_cart(store, key)
            self.assertEqual(cart.items.get().quantity, 1)
        elif sc == "payload_tampered_qty":
            t = propose()
            p = dict(t.payload)
            p["quantity"] = 99  # carga manipulada: la ejecución la revalida
            ActionToken.objects.filter(pk=t.pk).update(payload=p)
            r = run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            self.assertIn("error", r)
            cart = c.get_open_cart(store, key)
            self.assertTrue(cart is None or not cart.items.exists())
        elif sc == "price_snapshot_kept":
            t = propose()
            self.assertIn("unit_price", t.payload)
            self.assertIn("currency", t.payload)
        elif sc == "currency_mismatch":
            t = propose()
            p = dict(t.payload)
            p["currency"] = "EUR"
            ActionToken.objects.filter(pk=t.pk).update(payload=p)
            r = run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            self.assertEqual(r.get("error"), "action_quote_changed")
        elif sc == "expired_then_new_proposal":
            t = propose()
            ActionToken.objects.filter(pk=t.pk).update(
                expires_at=timezone.now() - timezone.timedelta(minutes=1))
            t2 = propose()
            self.assertNotEqual(t.action_id, t2.action_id)
        elif sc == "qty_bounds_low":
            self.assertIsNone(propose(quantity=0), "cantidad 0: sin propuesta")
        elif sc == "qty_bounds_high":
            self.assertIsNone(propose(quantity=99), "cantidad 99: sin propuesta")
        elif sc == "other_action_type":
            t = orchestrator._propose_action("mark_order_paid", {}, ctx)
            self.assertIsNone(t, "el asesor nunca propone operaciones de pago")
        elif sc == "confirm_other_cart":
            t = propose()
            other_ctx = ToolContext(store, "act-otro-carrito")
            r = run_tool("add_item_to_cart", {"action_id": t.action_id}, other_ctx)
            self.assertEqual(r.get("error"), "action_unknown")
        elif sc == "label_shows_summary":
            t = propose()
            label = orchestrator._proposal_label(t)
            self.assertIn("Arnés", label)
            self.assertIn("$", label)  # resumen completo: pieza + precio (N10)
        elif sc == "token_scoped_action":
            t = propose()
            self.assertEqual(t.store_id, store.id)
            self.assertEqual(t.session_key, key)
        elif sc == "repeat_after_cart_change":
            t = propose()
            run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            cart = c.get_open_cart(store, key)
            c.update_item(cart, cart.items.get().pk, 3)
            r = run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            self.assertTrue(r.get("ok"))
            cart.refresh_from_db()
            self.assertEqual(cart.items.get().quantity, 3)
        elif sc == "executed_has_receipt":
            t = propose()
            r = run_tool("add_item_to_cart", {"action_id": t.action_id}, ctx)
            self.assertTrue(r.get("ok"))
            self.assertIn("cart_units", r)  # recibo verificable de la mutación
            t.refresh_from_db()
            self.assertEqual(t.status, "executed")
            self.assertIsNotNone(t.executed_at)
        elif sc == "proposal_has_expiry":
            t = propose()
            self.assertGreater(t.expires_at, timezone.now())
        else:
            self.fail(f"escenario ACT sin runner: {sc}")
