import logging

from django.db import DatabaseError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import CheckoutForm, SmartFitForm
from .models import Cart, DogProfile, Order, Quote

logger = logging.getLogger(__name__)

# El catálogo vive en tienda/catalog.py (fuente de verdad).
from .catalog import PRODUCTOS  # noqa: E402,F401


def inicio(request):
    # Featured para la homepage premium (solo slugs del catálogo activo).
    _featured = ("wedding-dog", "tactical-dog", "cable-knit-jumper", "bamboo-drying-robe")
    featured = {s: PRODUCTOS[s] for s in _featured if s in PRODUCTOS}
    return render(request, "tienda/inicio.html", {"featured": featured})

def productos(request):
    return render(request, "tienda/productos.html", {"productos": PRODUCTOS})

def detalle(request, producto):
    item = PRODUCTOS.get(producto)
    if item is None:
        return render(request, "tienda/detalle.html", {"producto": None}, status=404)
    from . import services

    saved = _saved_dogs(request)
    return render(
        request,
        "tienda/detalle.html",
        {
            "producto": item,
            "slug": producto,
            "saved_dog": saved[0] if saved else None,
            "saved_dogs": saved,
            "size_options": services.size_options(),
            "quantities": range(1, services.MAX_QUANTITY + 1),
        },
    )


SESSION_DOGS = "dogs"


def _uuid_or_none(raw):
    import uuid

    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        return None


def _remember_dog(request, dog):
    """Recuerda hasta 5 perfiles en la sesión para reutilizarlos."""
    ids = [i for i in request.session.get(SESSION_DOGS, []) if i != str(dog.public_id)]
    request.session[SESSION_DOGS] = ([str(dog.public_id)] + ids)[:5]


def _saved_dogs(request):
    ids = request.session.get(SESSION_DOGS, [])
    found = {str(d.public_id): d for d in DogProfile.objects.filter(public_id__in=ids)}
    return [found[i] for i in ids if i in found]


def _requested_product(request):
    slug = request.GET.get("producto", "")
    return slug if slug in PRODUCTOS else ""


FLASH = "flash"
SAVE_ERROR = (
    "We could not save your measurements right now. Your data is still in the form; "
    "please try again in a moment."
)


def _save_dog(request, form):
    """Guarda el perfil; si se reenvía el mismo formulario reutiliza el perfil
    ya guardado en la sesión en vez de duplicarlo."""
    d = form.cleaned_data
    fields = {
        "name": d.get("name", ""),
        "breed": d["breed"],
        "weight_kg": d["weight_kg"],
        "back_length_cm": d["back_length_cm"],
        "chest_girth_cm": d["chest_girth_cm"],
        "neck_girth_cm": d.get("neck_girth_cm"),
    }
    for dog in _saved_dogs(request):
        if all(getattr(dog, k) == v for k, v in fields.items()):
            _remember_dog(request, dog)
            return dog
    dog = form.save()
    _remember_dog(request, dog)
    return dog


def smart_fit(request):
    from . import services

    producto = _requested_product(request)
    require_neck = bool(producto) and services.measurement_requirements(producto)["neck_girth"]
    if request.method == "POST":
        form = SmartFitForm(request.POST, require_neck=require_neck)
        if form.is_valid():
            try:
                dog = _save_dog(request, form)
            except DatabaseError:
                logger.exception("Smart Fit: could not save measurements")
                form.add_error(None, SAVE_ERROR)
            else:
                request.session[FLASH] = "Measurements saved."
                url = reverse("smart_fit_resultado", args=[dog.public_id])
                return redirect(url + (f"?producto={producto}" if producto else ""))
    else:
        form = SmartFitForm(
            initial={"weight_unit": "kg", "length_unit": "cm"}, require_neck=require_neck
        )
    return render(
        request,
        "tienda/smartfit.html",
        {
            "form": form,
            "saved_dogs": _saved_dogs(request),
            "producto": PRODUCTOS.get(producto),
            "editing": False,
        },
    )


def smart_fit_editar(request, public_id):
    from . import services

    dog = get_object_or_404(DogProfile, public_id=public_id)
    producto = _requested_product(request)
    require_neck = bool(producto) and services.measurement_requirements(producto)["neck_girth"]
    back_quote = Quote.objects.filter(
        public_id=_uuid_or_none(request.GET.get("quote")), dog=dog
    ).first()
    if request.method == "POST":
        form = SmartFitForm(request.POST, require_neck=require_neck)
        if form.is_valid():
            try:
                form.save(instance=dog)
            except DatabaseError:
                logger.exception("Smart Fit: could not update measurements")
                form.add_error(None, SAVE_ERROR)
            else:
                _remember_dog(request, dog)
                request.session[FLASH] = "Measurements saved."
                if request.GET.get("next") == "cart":
                    return redirect("cart")
                if back_quote:
                    return redirect("smart_quote", public_id=back_quote.public_id)
                url = reverse("smart_fit_resultado", args=[dog.public_id])
                return redirect(url + (f"?producto={producto}" if producto else ""))
    else:
        form = SmartFitForm(initial=SmartFitForm.initial_from(dog), require_neck=require_neck)
    return render(
        request,
        "tienda/smartfit.html",
        {
            "form": form,
            "saved_dogs": [],
            "producto": PRODUCTOS.get(producto),
            "editing": True,
            "dog": dog,
        },
    )


def smart_fit_resultado(request, public_id):
    from . import services

    dog = get_object_or_404(DogProfile, public_id=public_id)
    _remember_dog(request, dog)
    size = services.classify_size(dog) if request.GET.get("calcular") else None
    return render(
        request,
        "tienda/smartfit_resultado.html",
        {
            "dog": dog,
            "productos": PRODUCTOS,
            "preselect": _requested_product(request),
            "size": size,
            "max_quantity": services.MAX_QUANTITY,
            "size_options": services.size_options(),
        },
    )


def smart_quote_crear(request, public_id):
    # Local import: services depende de PRODUCTOS (definido en este módulo).
    from . import services

    dog = get_object_or_404(DogProfile, public_id=public_id)
    if request.method != "POST":
        return redirect("smart_fit_resultado", public_id=dog.public_id)
    # Solo se leen la clave del producto y la cantidad; cualquier precio se ignora.
    slug = request.POST.get("producto", "")
    if slug in PRODUCTOS and services.missing_measurements(dog, slug):
        # La prenda exige una medida que falta: se pide antes de cotizar.
        url = reverse("smart_fit_editar", args=[dog.public_id])
        return redirect(f"{url}?producto={slug}")

    def _error(message):
        return render(
            request,
            "tienda/smartfit_resultado.html",
            {"dog": dog, "productos": PRODUCTOS, "quote_error": message,
             "max_quantity": services.MAX_QUANTITY, "size_options": services.size_options(),
             "preselect": slug if slug in PRODUCTOS else ""},
            status=400,
        )

    try:
        quantity = services.normalize_quantity(request.POST.get("quantity", "1"))
    except services.QuantityError as exc:
        return _error(str(exc))
    size = request.POST.get("size", "").strip()
    if size and size not in services.size_options():
        return _error("Choose a size from the list.")
    try:
        quote = services.create_quote(dog, slug, quantity, size)
    except services.UnknownProduct:
        return _error("Please choose a product.")
    return redirect("smart_quote", public_id=quote.public_id)


def _quote_context(quote, payment_method="unspecified"):
    from . import services

    producto = services.get_product(quote.product_slug)
    return {
        "quote": quote,
        "dog": quote.dog,
        "producto": producto,
        "breakdown": services.build_breakdown(quote, payment_method),
        "size": services.classify_size(quote.dog),
        "discount_eligible": services.discount_eligible(quote.product_slug),
        "max_quantity": services.MAX_QUANTITY,
        "quantities": range(1, services.MAX_QUANTITY + 1),
        "size_options": services.size_options(),
    }


def _unavailable(request):
    return render(request, "tienda/checkout.html", {"cancelled": True}, status=410)


def smart_quote(request, public_id):
    quote = get_object_or_404(Quote.objects.select_related("dog"), public_id=public_id)
    if quote.product_slug not in PRODUCTOS:
        return _unavailable(request)
    return render(request, "tienda/smartquote.html", _quote_context(quote))


def smart_quote_cantidad(request, public_id):
    from . import services

    quote = get_object_or_404(Quote.objects.select_related("dog"), public_id=public_id)
    if quote.product_slug not in PRODUCTOS:
        return _unavailable(request)
    if request.method != "POST":
        return redirect("smart_quote", public_id=quote.public_id)
    try:
        services.set_quote_quantity(quote, request.POST.get("quantity", ""))
    except services.QuantityError as exc:
        context = _quote_context(quote)
        context["quantity_error"] = str(exc)
        return render(request, "tienda/smartquote.html", context, status=400)
    return redirect("smart_quote", public_id=quote.public_id)


def checkout(request, public_id):
    from . import services

    quote = get_object_or_404(Quote.objects.select_related("dog"), public_id=public_id)
    existing = Order.objects.filter(quote=quote).first()
    if existing:
        return redirect("order_detail", public_id=existing.public_id)
    if quote.product_slug not in PRODUCTOS:
        return _unavailable(request)
    if quote.status == Quote.Status.CANCELLED:
        return render(request, "tienda/checkout.html", {"cancelled": True}, status=400)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            if request.POST.get("step") == "review":
                # Paso de revisión: se muestran todos los importes antes de confirmar.
                method = form.cleaned_data["payment_method"]
                context = _quote_context(quote, method)
                context.update(
                    {
                        "data": form.cleaned_data,
                        "payment_label": dict(form.fields["payment_method"].choices)[method],
                        "method": method,
                        "is_demo": method in services.DEMO_METHODS,
                    }
                )
                return render(request, "tienda/checkout_review.html", context)
            try:
                order, _ = services.create_order(quote, form.cleaned_data)
            except services.QuoteNotOrderable:
                return render(request, "tienda/checkout.html", {"cancelled": True}, status=400)
            return redirect("order_detail", public_id=order.public_id)
    else:
        form = CheckoutForm()
    context = _quote_context(quote)
    context["form"] = form
    return render(request, "tienda/checkout.html", context)


CART_SESSION = "cart"


def _session_cart(request, create=False):
    """Carrito abierto de la sesión (opcionalmente lo crea)."""
    from . import services

    try:
        cart = services.get_open_cart(request.session.get(CART_SESSION))
    except Exception:
        cart = None
    if cart is None and create:
        cart = Cart.objects.create()
        request.session[CART_SESSION] = str(cart.public_id)
    return cart


def _cart_context(cart, payment_method="unspecified"):
    from . import services

    return {
        "cart": cart,
        "summary": services.cart_summary(cart, payment_method) if cart else None,
        "size_options": services.size_options(),
        "quantities": range(1, services.MAX_QUANTITY + 1),
    }


def cart_view(request):
    cart = _session_cart(request)
    return render(request, "tienda/cart.html", _cart_context(cart))


def cart_add(request):
    """Añade un producto al carrito. Solo se leen perfil, producto, cantidad y
    talla; el precio sale del catálogo."""
    from . import services

    if request.method != "POST":
        return redirect("cart")
    dog = DogProfile.objects.filter(public_id=_uuid_or_none(request.POST.get("dog"))).first()
    if dog is None:
        return redirect("smart_fit")
    slug = request.POST.get("producto", "")

    def _error(message):
        return render(
            request,
            "tienda/smartfit_resultado.html",
            {"dog": dog, "productos": PRODUCTOS, "quote_error": message,
             "max_quantity": services.MAX_QUANTITY, "size_options": services.size_options(),
             "preselect": slug if slug in PRODUCTOS else ""},
            status=400,
        )

    if slug not in PRODUCTOS:
        return _error("Please choose a product.")
    if services.missing_measurements(dog, slug):
        url = reverse("smart_fit_editar", args=[dog.public_id])
        return redirect(f"{url}?producto={slug}")
    try:
        quantity = services.normalize_quantity(request.POST.get("quantity", "1"))
        services.add_to_cart(
            _session_cart(request, create=True), dog, slug, quantity,
            request.POST.get("size", ""),
        )
    except (services.QuantityError, services.CartError, services.UnknownProduct,
            services.InvalidCatalogPrice) as exc:
        return _error(str(exc) or "That product cannot be added.")
    return redirect("cart")


def _cart_quote(request, public_id):
    cart = _session_cart(request)
    if cart is None:
        return None, None
    quote = Quote.objects.filter(
        public_id=public_id, cart=cart, status=Quote.Status.DRAFT
    ).first()
    return cart, quote


def cart_line_update(request, public_id):
    from . import services

    cart, quote = _cart_quote(request, public_id)
    if quote is None:
        return redirect("cart")
    if request.method == "POST":
        error = None
        quantity = quote.quantity
        try:
            quantity = services.normalize_quantity(request.POST.get("quantity", ""))
        except services.QuantityError as exc:
            error = str(exc)
        size = request.POST.get("size", "").strip()
        if error is None and size and size not in services.size_options():
            error = "Choose a size from the list."
        if error:
            context = _cart_context(cart)
            context["line_error"] = {"id": str(quote.public_id), "message": error}
            return render(request, "tienda/cart.html", context, status=400)
        quote.quantity = quantity
        quote.size_label = size
        quote.save(update_fields=["quantity", "size_label"])
    return redirect("cart")


def cart_line_remove(request, public_id):
    cart, quote = _cart_quote(request, public_id)
    if quote is not None and request.method == "POST":
        quote.delete()
    return redirect("cart")


def quote_to_cart(request, public_id):
    """Pasa una cotización existente al carrito de la sesión."""
    quote = get_object_or_404(Quote.objects.select_related("dog"), public_id=public_id)
    if request.method != "POST":
        return redirect("smart_quote", public_id=quote.public_id)
    if quote.product_slug not in PRODUCTOS or quote.status != Quote.Status.DRAFT:
        return _unavailable(request)
    cart = _session_cart(request, create=True)
    if quote.cart_id not in (None, cart.pk):
        return _unavailable(request)
    quote.cart = cart
    quote.save(update_fields=["cart"])
    return redirect("cart")


def cart_checkout(request):
    from . import services

    cart = _session_cart(request)
    if cart is None or not services.cart_lines(cart):
        return redirect("cart")
    summary = services.cart_summary(cart)
    if summary["has_missing"] or not summary["lines"]:
        return redirect("cart")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            if request.POST.get("step") == "review":
                method = form.cleaned_data["payment_method"]
                context = _cart_context(cart, method)
                context.update(
                    {
                        "data": form.cleaned_data,
                        "payment_label": dict(form.fields["payment_method"].choices)[method],
                        "method": method,
                        "is_demo": method in services.DEMO_METHODS,
                    }
                )
                return render(request, "tienda/cart_checkout_review.html", context)
            try:
                order, _ = services.create_order_from_cart(cart, form.cleaned_data)
            except (services.QuoteNotOrderable, services.CartError):
                return redirect("cart")
            return redirect("order_detail", public_id=order.public_id)
    else:
        form = CheckoutForm()
    context = _cart_context(cart)
    context["form"] = form
    return render(request, "tienda/cart_checkout.html", context)


def order_detail(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    labels = {
        "status": "Order",
        "payment_status": "Payment",
        "production_status": "Production",
        "shipping_status": "Shipping",
    }
    public_events = [
        {"created_at": e.created_at, "label": f"{labels[e.field]}: {e.to_value.replace('_', ' ')}"}
        for e in order.events.filter(field__in=labels)
    ]
    return render(
        request,
        "tienda/order.html",
        {"order": order, "snap": order.snapshot, "public_events": public_events},
    )


def assistant(request):
    from . import assistant as bot

    occasion = request.GET.get("occasion", "")
    q = request.GET.get("q", "")[: bot.MAX_QUERY_LENGTH]
    reply = None
    if q.strip():
        reply = bot.answer(q)
    elif occasion:
        reply = bot.recommend(occasion) or bot.answer("")
    return render(
        request,
        "tienda/assistant.html",
        {
            "occasions": [(k, v[0]) for k, v in bot.OCCASIONS.items()],
            "saved_dog": (_saved_dogs(request) or [None])[0],
            "selected": occasion,
            "q": q,
            "reply": reply,
        },
    )
