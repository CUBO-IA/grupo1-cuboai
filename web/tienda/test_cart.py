"""Carrito multiproducto: líneas con medidas y talla propias, un solo checkout,
pedido con líneas, producción y costos por línea."""

import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from . import services
from .models import Cart, DogProfile, Order, OrderEvent, ProductMeasurement, Quote

CUSTOMER = {
    "customer_name": "Ana Perez", "customer_email": "ana@example.com",
    "customer_phone": "+503 7000 0000", "country": "El Salvador",
    "city": "San Salvador", "address": "Calle 1 #2", "payment_method": "unspecified",
}


def make_dog(name="Rex", chest="42.5", back="35.0", weight="7.50", neck=None):
    return DogProfile.objects.create(
        name=name, breed="Dachshund", weight_kg=Decimal(weight),
        back_length_cm=Decimal(back), chest_girth_cm=Decimal(chest),
        neck_girth_cm=Decimal(neck) if neck else None,
    )


def staff():
    return User.objects.create_user("staff", password="x", is_staff=True)


def build_cart(*items):
    """items: (dog, slug, quantity[, size]) -> Cart con esas líneas."""
    cart = Cart.objects.create()
    for item in items:
        dog, slug, qty = item[:3]
        size = item[3] if len(item) > 3 else ""
        services.add_to_cart(cart, dog, slug, qty, size)
    return cart


class AddToCartServiceTests(TestCase):
    def test_add_creates_line_with_server_price(self):
        cart = Cart.objects.create()
        quote = services.add_to_cart(cart, make_dog(), "tactical-dog", 2, "S (small dogs)")
        self.assertEqual(quote.cart, cart)
        self.assertEqual((quote.quantity, quote.base_price), (2, Decimal("300.00")))
        self.assertEqual(quote.size_label, "S (small dogs)")
        self.assertEqual(quote.status, Quote.Status.DRAFT)

    def test_same_dog_product_size_accumulates_quantity(self):
        dog, cart = make_dog(), Cart.objects.create()
        services.add_to_cart(cart, dog, "tactical-dog", 2)
        services.add_to_cart(cart, dog, "tactical-dog", 3)
        self.assertEqual(cart.quotes.count(), 1)
        self.assertEqual(cart.quotes.get().quantity, 5)

    def test_different_size_or_dog_makes_separate_lines(self):
        cart = Cart.objects.create()
        a, b = make_dog("A"), make_dog("B")
        services.add_to_cart(cart, a, "tactical-dog", 1, "S (small dogs)")
        services.add_to_cart(cart, a, "tactical-dog", 1, "M (small dogs)")
        services.add_to_cart(cart, b, "tactical-dog", 1, "S (small dogs)")
        self.assertEqual(cart.quotes.count(), 3)

    def test_validation(self):
        cart, dog = Cart.objects.create(), make_dog()
        with self.assertRaises(services.UnknownProduct):
            services.add_to_cart(cart, dog, "dog-sweater", 1)
        with self.assertRaises(services.QuantityError):
            services.add_to_cart(cart, dog, "tactical-dog", 0)
        with self.assertRaises(services.QuantityError):
            services.add_to_cart(cart, dog, "tactical-dog", 11)
        with self.assertRaises(services.CartError):
            services.add_to_cart(cart, dog, "tactical-dog", 1, "XXL-fake")
        services.add_to_cart(cart, dog, "tactical-dog", 10)
        with self.assertRaises(services.QuantityError):
            services.add_to_cart(cart, dog, "tactical-dog", 1)  # 11 > máximo
        self.assertEqual(cart.quotes.get().quantity, 10)

    def test_required_measurement_blocks_adding(self):
        ProductMeasurement.objects.filter(product_slug="cable-knit-jumper").update(
            requires_neck=True
        )
        cart, dog = Cart.objects.create(), make_dog()
        with self.assertRaises(services.CartError) as ctx:
            services.add_to_cart(cart, dog, "cable-knit-jumper", 1)
        self.assertIn("neck girth", str(ctx.exception))
        # el resto de productos no se bloquea
        services.add_to_cart(cart, dog, "tactical-dog", 1)
        dog.neck_girth_cm = Decimal("25")
        dog.save()
        services.add_to_cart(cart, dog, "cable-knit-jumper", 1)


class CartSummaryTests(TestCase):
    def test_totals_and_units(self):
        cart = build_cart(
            (make_dog("A"), "wedding-dog", 1),
            (make_dog("B"), "tactical-dog", 2),
            (make_dog("C"), "bamboo-drying-robe", 1),
        )
        s = services.cart_summary(cart)
        self.assertEqual([l["totals"]["subtotal"] for l in s["lines"]],
                         [Decimal("650.00"), Decimal("600.00"), Decimal("88.00")])
        self.assertEqual(s["subtotal"], Decimal("1338.00"))
        self.assertEqual(s["units"], 4)
        self.assertTrue(s["is_provisional"])
        self.assertIsNone(s["shipping"])
        self.assertEqual(s["discount_amount"], Decimal("0.00"))  # método sin descuento

    def test_discount_only_on_eligible_lines_with_bitcoin(self):
        cart = build_cart(
            (make_dog("A"), "wedding-dog", 1),
            (make_dog("B"), "cable-knit-jumper", 2),
            (make_dog("C"), "bamboo-drying-robe", 1),
        )
        s = services.cart_summary(cart, "bitcoin")
        self.assertEqual(s["subtotal"], Decimal("1038.00"))
        # 15 % de 300.00 (jumper × 2) + 15 % de 88.00 (bata); el traje no es elegible
        self.assertEqual(s["discount_amount"], Decimal("58.20"))
        self.assertEqual(s["total_if_discount"], Decimal("979.80"))

    def test_missing_flag(self):
        ProductMeasurement.objects.filter(product_slug="tactical-dog").update(requires_neck=True)
        cart = Cart.objects.create()
        dog = make_dog()
        # cargado antes de exigir el cuello: queda marcado como incompleto
        ProductMeasurement.objects.filter(product_slug="tactical-dog").update(requires_neck=False)
        services.add_to_cart(cart, dog, "tactical-dog", 1)
        ProductMeasurement.objects.filter(product_slug="tactical-dog").update(requires_neck=True)
        self.assertTrue(services.cart_summary(cart)["has_missing"])


class CartOrderTests(TestCase):
    def setUp(self):
        self.dog_a = make_dog("Rex", chest="42.5", back="35.0")
        self.dog_b = make_dog("Luna", chest="36", back="28", neck="24")
        self.cart = build_cart(
            (self.dog_a, "wedding-dog", 1),
            (self.dog_b, "tactical-dog", 2, "S (small dogs)"),
            (self.dog_a, "bamboo-drying-robe", 1),
        )

    def test_one_order_with_a_line_per_product(self):
        order, created = services.create_order_from_cart(self.cart, CUSTOMER)
        self.assertTrue(created)
        lines = list(order.lines.all())
        self.assertEqual([l.product_slug for l in lines],
                         ["wedding-dog", "tactical-dog", "bamboo-drying-robe"])
        self.assertEqual([l.quantity for l in lines], [1, 2, 1])
        self.assertEqual(order.total, Decimal("1338.00"))
        self.assertEqual(order.quantity, 4)
        self.assertIsNone(order.quote)
        self.assertEqual(order.cart, self.cart)
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(order.production_status, "not_started")
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.status, Cart.Status.ORDERED)
        self.assertEqual(
            set(Quote.objects.filter(cart=self.cart).values_list("status", flat=True)),
            {"accepted"},
        )

    def test_each_line_keeps_its_own_measurements_and_size(self):
        order, _ = services.create_order_from_cart(self.cart, CUSTOMER)
        tactical = order.lines.get(product_slug="tactical-dog")
        self.assertEqual(tactical.dog_snapshot["name"], "Luna")
        self.assertEqual(tactical.dog_snapshot["chest_girth_cm"], "36.0")
        self.assertEqual(tactical.size_selected, "S (small dogs)")
        wedding = order.lines.get(product_slug="wedding-dog")
        self.assertEqual(wedding.dog_snapshot["name"], "Rex")
        self.assertEqual(wedding.dog_snapshot["chest_girth_cm"], "42.5")
        self.assertEqual(wedding.size_selected, "")
        # editar el perfil después no altera el pedido
        self.dog_b.chest_girth_cm = Decimal("60")
        self.dog_b.save()
        tactical.refresh_from_db()
        self.assertEqual(tactical.dog_snapshot["chest_girth_cm"], "36.0")

    def test_idempotent_and_empty_cart(self):
        first, _ = services.create_order_from_cart(self.cart, CUSTOMER)
        second, created = services.create_order_from_cart(self.cart, CUSTOMER)
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Order.objects.count(), 1)
        with self.assertRaises(services.CartError):
            services.create_order_from_cart(Cart.objects.create(), CUSTOMER)

    def test_bitcoin_discount_per_eligible_line(self):
        order, _ = services.create_order_from_cart(
            self.cart, {**CUSTOMER, "payment_method": "bitcoin"}
        )
        self.assertEqual(order.discount_amount, Decimal("13.20"))  # solo la bata
        self.assertEqual(order.discount_status, "pending_verification")
        self.assertEqual(order.amount_due, Decimal("1338.00"))
        self.assertEqual(order.amount_if_discount, Decimal("1324.80"))
        robe = order.lines.get(product_slug="bamboo-drying-robe")
        self.assertEqual((robe.discount_eligible, robe.discount_amount),
                         (True, Decimal("13.20")))
        self.assertEqual(order.lines.get(product_slug="wedding-dog").discount_amount, 0)

    def test_totals_not_influenced_by_client(self):
        self.client.post(reverse("cart_checkout"))  # sin sesión: redirige
        self.assertEqual(Order.objects.count(), 0)

    def test_snapshot_has_all_lines(self):
        order, _ = services.create_order_from_cart(self.cart, CUSTOMER)
        self.assertEqual(len(order.snapshot["lines"]), 3)
        self.assertEqual(order.snapshot["lines"][1]["product"]["slug"], "tactical-dog")
        self.assertEqual(order.snapshot["lines"][1]["quantity"], 2)

    def test_single_line_cart_keeps_quote_link(self):
        cart = build_cart((make_dog(), "tactical-dog", 1))
        order, _ = services.create_order_from_cart(cart, CUSTOMER)
        self.assertIsNotNone(order.quote)
        self.assertEqual(order.lines.count(), 1)


class LineProductionTests(TestCase):
    def setUp(self):
        self.ok = make_dog("Rex", chest="42.5", back="35.0")
        self.ambiguous = make_dog("Luna", chest="46", back="36")  # talla ambigua
        cart = build_cart(
            (self.ok, "tactical-dog", 1),
            (self.ambiguous, "christmas-dog", 1),
        )
        self.order, _ = services.create_order_from_cart(cart, CUSTOMER)
        self.ok_line = self.order.lines.get(product_slug="tactical-dog")
        self.amb_line = self.order.lines.get(product_slug="christmas-dog")

    def pay(self):
        services.apply_transition(self.order, "payment_status", "paid", note="REF")
        self.order.refresh_from_db()

    def test_readiness_is_per_line(self):
        self.pay()
        r = services.order_readiness(self.order)
        self.assertFalse(r["info_validated"])
        self.assertFalse(r["ready"])
        by_slug = {x["line"].product_slug: x for x in r["lines"]}
        self.assertTrue(by_slug["tactical-dog"]["ready"])
        self.assertFalse(by_slug["christmas-dog"]["ready"])
        self.assertIn("Christmas Dog", " ".join(r["blockers"]))

    def test_order_level_start_blocked_but_ready_line_can_start(self):
        self.pay()
        with self.assertRaises(services.TransitionError):
            services.apply_transition(self.order, "production_status", "in_production")
        services.apply_line_transition(self.ok_line, "in_production", note="go")
        self.order.refresh_from_db()
        self.ok_line.refresh_from_db()
        self.assertEqual(self.ok_line.production_status, "in_production")
        self.assertEqual(self.order.production_status, "in_production")
        with self.assertRaises(services.TransitionError) as ctx:
            services.apply_line_transition(self.amb_line, "in_production")
        self.assertIn("Cannot start production", str(ctx.exception))

    def test_unpaid_blocks_line_production(self):
        with self.assertRaises(services.TransitionError) as ctx:
            services.apply_line_transition(self.ok_line, "in_production")
        self.assertIn("Payment must be verified", str(ctx.exception))

    def test_size_confirmation_per_line_unblocks_it(self):
        self.pay()
        with self.assertRaises(services.TransitionError):
            services.confirm_size(self.order, "M")  # varias líneas: hay que elegir
        services.confirm_size(self.order, "M (medium dogs)", line=self.amb_line.pk)
        self.amb_line.refresh_from_db()
        self.assertEqual(self.amb_line.size_confirmed, "M (medium dogs)")
        self.assertTrue(services.order_readiness(self.order)["ready"])
        self.assertTrue(OrderEvent.objects.filter(field="size_confirmed").exists())
        # el pedido completo ya puede iniciar la producción de todas las líneas
        services.apply_transition(self.order, "production_status", "in_production")
        self.assertEqual(
            set(self.order.lines.values_list("production_status", flat=True)), {"in_production"}
        )

    def test_customer_size_choice_resolves_ambiguity(self):
        cart = build_cart((self.ambiguous, "tactical-dog", 1, "M (small dogs)"))
        order, _ = services.create_order_from_cart(cart, CUSTOMER)
        line = order.lines.get()
        self.assertIn("M (small dogs)", line.size_reference["candidates"])
        self.assertTrue(services.order_readiness(order)["lines"][0]["size_ok"])

    def test_customer_size_conflicting_with_measurements_needs_staff(self):
        cart = build_cart((self.ok, "tactical-dog", 1, "XXL (large dogs)"))
        order, _ = services.create_order_from_cart(cart, CUSTOMER)
        r = services.order_readiness(order)["lines"][0]
        self.assertFalse(r["size_ok"])
        self.assertIn("customer chose XXL (large dogs)", " ".join(r["blockers"]))

    def test_aggregate_status_and_shipping_gate(self):
        self.pay()
        services.confirm_size(self.order, "M", line=self.amb_line.pk)
        services.apply_line_transition(self.ok_line, "in_production")
        services.apply_line_transition(self.ok_line, "completed")
        self.order.refresh_from_db()
        self.assertEqual(self.order.production_status, "in_production")  # falta otra línea
        with self.assertRaises(services.TransitionError):
            services.apply_transition(self.order, "shipping_status", "shipped")
        services.apply_line_transition(self.amb_line, "in_production")
        services.apply_line_transition(self.amb_line, "completed")
        self.order.refresh_from_db()
        self.assertEqual(self.order.production_status, "completed")
        services.apply_transition(self.order, "shipping_status", "shipped")

    def test_invalid_line_transitions(self):
        self.pay()
        with self.assertRaises(services.TransitionError):
            services.apply_line_transition(self.ok_line, "completed")
        services.apply_transition(self.order, "status", "cancelled")
        with self.assertRaises(services.TransitionError):
            services.apply_line_transition(self.ok_line, "in_production")

    def test_payment_method_change_recomputes_each_line(self):
        cart = build_cart(
            (make_dog("A"), "cable-knit-jumper", 1),
            (make_dog("B"), "tactical-dog", 1),
        )
        order, _ = services.create_order_from_cart(cart, CUSTOMER)
        services.set_payment_method(order, "bitcoin")
        order.refresh_from_db()
        self.assertEqual(order.discount_amount, Decimal("22.50"))
        self.assertEqual(order.lines.get(product_slug="cable-knit-jumper").discount_amount,
                         Decimal("22.50"))
        services.set_payment_method(order, "unspecified")
        order.refresh_from_db()
        self.assertEqual(order.discount_amount, Decimal("0.00"))

    def test_cost_sums_lines_times_quantity(self):
        cart = build_cart(
            (make_dog("A"), "tactical-dog", 1),     # 175.00
            (make_dog("B"), "cable-knit-jumper", 2),  # 2 × 35.00
        )
        order, _ = services.create_order_from_cart(cart, CUSTOMER)
        s = services.cost_summary(order)
        self.assertEqual(s["cost"], Decimal("245.00"))
        self.assertEqual(s["revenue"], Decimal("600.00"))
        self.assertEqual(s["margin"], Decimal("355.00"))
        self.assertEqual(s["cost_source"], "product_estimate")


class CartViewTests(TestCase):
    def add(self, dog, slug="tactical-dog", **extra):
        data = {"dog": str(dog.public_id), "producto": slug, "quantity": "1", "size": ""}
        data.update(extra)
        return self.client.post(reverse("cart_add"), data)

    def test_empty_cart_page(self):
        r = self.client.get(reverse("cart"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Your cart is empty")

    def test_add_and_view(self):
        dog = make_dog()
        r = self.add(dog, "tactical-dog", quantity="2", size="S (small dogs)")
        self.assertRedirects(r, reverse("cart"))
        page = self.client.get(reverse("cart"))
        self.assertContains(page, "Tactical Dog")
        self.assertContains(page, "tienda/img/tactical-dog.jpg")
        self.assertContains(page, "$600.00")
        self.assertContains(page, "Provisional")
        self.assertContains(page, "To be confirmed")
        self.assertContains(page, "Cart (2)")  # contador en la cabecera

    def test_two_products_two_dogs(self):
        a, b = make_dog("A"), make_dog("B", chest="36", back="28")
        self.add(a, "tactical-dog")
        self.add(b, "bamboo-drying-robe")
        page = self.client.get(reverse("cart"))
        self.assertContains(page, "Tactical Dog")
        self.assertContains(page, "Showercover Bamboo Dachshund Drying Robe")
        self.assertContains(page, "$388.00")
        self.assertContains(page, "Checkout (2 items)")

    def test_price_and_status_cannot_be_injected(self):
        dog = make_dog()
        self.add(dog, "tactical-dog", base_price="1", unit_price="1", total="1", status="accepted")
        q = Quote.objects.get()
        self.assertEqual((q.base_price, q.status), (Decimal("300.00"), "draft"))

    def test_invalid_input(self):
        dog = make_dog()
        for extra in ({"producto": "nope"}, {"producto": "dog-sweater"}, {"quantity": "0"},
                      {"quantity": "11"}, {"quantity": "x"}, {"size": "XXL-fake"}):
            r = self.add(dog, **extra)
            self.assertEqual(r.status_code, 400, extra)
        self.assertEqual(Quote.objects.count(), 0)
        r = self.client.post(reverse("cart_add"), {"dog": str(uuid.uuid4()), "producto": "tactical-dog"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Quote.objects.count(), 0)

    def test_update_and_remove(self):
        dog = make_dog()
        self.add(dog, "tactical-dog")
        q = Quote.objects.get()
        r = self.client.post(
            reverse("cart_line_update", args=[q.public_id]),
            {"quantity": "4", "size": "M (small dogs)"},
        )
        self.assertRedirects(r, reverse("cart"))
        q.refresh_from_db()
        self.assertEqual((q.quantity, q.size_label), (4, "M (small dogs)"))
        r = self.client.post(reverse("cart_line_update", args=[q.public_id]), {"quantity": "99"})
        self.assertEqual(r.status_code, 400)
        q.refresh_from_db()
        self.assertEqual(q.quantity, 4)
        r = self.client.post(reverse("cart_line_remove", args=[q.public_id]))
        self.assertRedirects(r, reverse("cart"))
        self.assertEqual(Quote.objects.count(), 0)

    def test_other_session_cannot_touch_lines(self):
        dog = make_dog()
        self.add(dog, "tactical-dog")
        q = Quote.objects.get()
        other = Client()
        other.post(reverse("cart_line_update", args=[q.public_id]), {"quantity": "9"})
        other.post(reverse("cart_line_remove", args=[q.public_id]))
        q.refresh_from_db()
        self.assertEqual(q.quantity, 1)

    def test_quote_to_cart(self):
        dog = make_dog()
        r = self.client.post(
            reverse("smart_quote_crear", args=[dog.public_id]),
            {"producto": "christmas-dog", "quantity": "1", "size": "S (small dogs)"},
        )
        quote = Quote.objects.get()
        self.assertEqual(quote.size_label, "S (small dogs)")
        page = self.client.get(r.url)
        self.assertContains(page, "Add to cart")
        r = self.client.post(reverse("quote_to_cart", args=[quote.public_id]))
        self.assertRedirects(r, reverse("cart"))
        quote.refresh_from_db()
        self.assertIsNotNone(quote.cart)

    def test_csrf_enforced(self):
        dog = make_dog()
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("cart_add"), {"dog": str(dog.public_id), "producto": "tactical-dog"})
        self.assertEqual(r.status_code, 403)

    def test_full_checkout_with_review_and_double_submit(self):
        a, b = make_dog("A"), make_dog("B", chest="36", back="28")
        self.add(a, "tactical-dog", quantity="2")
        self.add(b, "cable-knit-jumper")
        url = reverse("cart_checkout")
        self.assertContains(self.client.get(url), "Review order")
        r = self.client.post(url, {**CUSTOMER, "payment_method": "bitcoin", "step": "review"})
        self.assertContains(r, "Review your order")
        self.assertContains(r, "Confirm order")
        self.assertContains(r, "-$22.50")
        self.assertEqual(Order.objects.count(), 0)
        data = {**CUSTOMER, "payment_method": "bitcoin", "step": "confirm"}
        r1 = self.client.post(url, data)
        order = Order.objects.get()
        self.assertRedirects(r1, reverse("order_detail", args=[order.public_id]))
        self.client.post(url, data)  # reenvío accidental
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(order.lines.count(), 2)
        self.assertEqual(order.total, Decimal("750.00"))
        self.assertEqual(order.discount_amount, Decimal("22.50"))
        page = self.client.get(r1.url)
        self.assertContains(page, "Tactical Dog")
        self.assertContains(page, "Luxury Cable Knit Dachshund Jumper")
        self.assertContains(page, "Quantity")
        self.assertContains(page, "$600.00")
        self.assertNotContains(page, "Hilo premium")
        # el carrito ya no está abierto
        self.assertContains(self.client.get(reverse("cart")), "Your cart is empty")

    def test_checkout_validation_and_empty(self):
        self.assertEqual(self.client.get(reverse("cart_checkout")).status_code, 302)
        dog = make_dog()
        self.add(dog)
        r = self.client.post(
            reverse("cart_checkout"), {**CUSTOMER, "customer_email": "bad", "step": "review"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Enter a valid email")
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_client_cannot_inject_amounts(self):
        dog = make_dog()
        self.add(dog, "tactical-dog")
        self.client.post(
            reverse("cart_checkout"),
            {**CUSTOMER, "step": "confirm", "total": "1", "discount_amount": "999",
             "quantity": "9"},
        )
        order = Order.objects.get()
        self.assertEqual((order.total, order.quantity), (Decimal("300.00"), 1))
        self.assertEqual(order.discount_amount, Decimal("0.00"))


class PanelCartTests(TestCase):
    def setUp(self):
        a, b = make_dog("Rex"), make_dog("Luna", chest="46", back="36")
        cart = build_cart((a, "tactical-dog", 1), (b, "bamboo-drying-robe", 2))
        self.order, _ = services.create_order_from_cart(cart, CUSTOMER)
        self.url = reverse("panel_order", args=[self.order.public_id])
        self.staff = staff()

    def test_panel_shows_lines_and_controls(self):
        self.client.force_login(self.staff)
        page = self.client.get(self.url)
        for text in ("Tactical Dog × 1", "Showercover Bamboo Dachshund Drying Robe × 2",
                     "Luna", "Confirm size", "Not ready to make"):
            self.assertContains(page, text)

    def test_list_summary_and_search_by_line_product(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("panel_orders"))
        self.assertContains(r, "Tactical Dog + 1 more")
        r = self.client.get(reverse("panel_orders"), {"q": "bamboo"})
        self.assertEqual([o.pk for o in r.context["orders"]], [self.order.pk])
        r = self.client.get(reverse("panel_orders"), {"q": "tactical"})
        self.assertEqual(len(r.context["orders"]), 1)

    def test_line_production_through_panel(self):
        services.apply_transition(self.order, "payment_status", "paid", note="REF")
        self.client.force_login(self.staff)
        line = self.order.lines.get(product_slug="tactical-dog")
        r = self.client.post(
            self.url, {"form": "line_production", "line": line.pk, "value": "in_production"}
        )
        self.assertRedirects(r, self.url)
        line.refresh_from_db()
        self.assertEqual(line.production_status, "in_production")
        other = self.order.lines.get(product_slug="bamboo-drying-robe")
        r = self.client.post(
            self.url, {"form": "line_production", "line": other.pk, "value": "in_production"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "Cannot start production", status_code=400)

    def test_size_confirmation_per_line_through_panel(self):
        self.client.force_login(self.staff)
        line = self.order.lines.get(product_slug="bamboo-drying-robe")
        r = self.client.post(
            self.url, {"form": "size", "line": line.pk, "size_confirmed": "M (medium dogs)"}
        )
        self.assertRedirects(r, self.url)
        line.refresh_from_db()
        self.assertEqual(line.size_confirmed, "M (medium dogs)")

    def test_line_forms_require_staff_and_csrf(self):
        line = self.order.lines.first()
        data = {"form": "line_production", "line": line.pk, "value": "in_production"}
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.staff)
        self.assertEqual(c.post(self.url, data).status_code, 403)

    def test_line_of_another_order_is_rejected(self):
        other_order, _ = services.create_order_from_cart(
            build_cart((make_dog("Z"), "christmas-dog", 1)), CUSTOMER
        )
        foreign = other_order.lines.get()
        self.client.force_login(self.staff)
        r = self.client.post(
            self.url, {"form": "line_production", "line": foreign.pk, "value": "in_production"}
        )
        self.assertEqual(r.status_code, 400)
        foreign.refresh_from_db()
        self.assertEqual(foreign.production_status, "not_started")

    def test_sheet_groups_every_line(self):
        self.client.force_login(self.staff)
        page = self.client.get(reverse("panel_order_sheet", args=[self.order.public_id]))
        for text in ("1. Tactical Dog × 1", "2. Showercover Bamboo Dachshund Drying Robe × 2",
                     "Nylon Cordura 1000D", "Tela de rizo con fibra de bambú",
                     "multiply each consumption by 2", "Confection status"):
            self.assertContains(page, text)

    def test_internal_data_not_in_customer_order_page(self):
        page = self.client.get(reverse("order_detail", args=[self.order.public_id])).content.decode()
        for text in ("Nylon Cordura", "Tela de rizo", "Workshop", "ESTIMATE", "175.00",
                     "Readiness", "REF"):
            self.assertNotIn(text, page)
