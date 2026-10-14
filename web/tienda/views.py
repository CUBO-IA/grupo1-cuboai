from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import CheckoutForm, SmartFitForm
from .models import DogProfile, Order, Quote

PRODUCTOS = {
    "wedding-dog": {
        "nombre": "Wedding Dog",
        "precio": "$650",
        "imagen": "tienda/img/wedding-dog.jpg",
        "tagline": "A Little Suit for Your Biggest Moments.",
        "descripcion": "Elegant formalwear for dachshunds, designed for weddings, special celebrations, and unforgettable moments with your best friend.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "A Special-Occasion Look", "texto": "A polished style for weddings, celebrations, and memorable photographs."},
            {"icono": "⌁", "titulo": "Made for Dachshunds", "texto": "A distinctive look created with the long, charming dachshund silhouette in mind."},
            {"icono": "◇", "titulo": "Style with Comfort in Mind", "texto": "Choose a fit that lets your companion move as comfortably as possible."},
            {"icono": "✧", "titulo": "For Unforgettable Moments", "texto": "Celebrate the occasions when your best friend deserves to be part of the moment."},
        ],
    },
    "tactical-dog": {
        "nombre": "Tactical Dog",
        "precio": "$300",
        "imagen": "tienda/img/tactical-dog.jpg",
        "tagline": "Built for Adventure. Styled for Royalty.",
        "descripcion": "A bold, functional look for dachshunds with fearless personalities, designed to bring distinctive style to everyday adventures.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Bold, Distinctive Style", "texto": "A confident look for dogs with plenty of personality."},
            {"icono": "⌁", "titulo": "Adventure-Inspired", "texto": "A playful design for outings, photos, and everyday adventures."},
            {"icono": "◇", "titulo": "Comfort Comes First", "texto": "Always choose a fit that allows your dog to move freely and comfortably."},
            {"icono": "✧", "titulo": "Ready for Their Moment", "texto": "Make ordinary outings and special snapshots feel a little more memorable."},
        ],
    },
    "christmas-dog": {
        "nombre": "Christmas Dog",
        "precio": "$250",
        "imagen": "tienda/img/christmas-dog.jpg",
        "tagline": "Make Every Celebration Magical.",
        "descripcion": "A festive look for holiday gatherings, family photos, and memorable celebrations with your little companion.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Festive by Design", "texto": "A seasonal look for holiday gatherings and celebrations."},
            {"icono": "⌁", "titulo": "Made for Photo Moments", "texto": "Bring extra charm to family pictures and seasonal memories."},
            {"icono": "◇", "titulo": "Comfort Comes First", "texto": "Check the fit and make sure your dog can move comfortably while wearing it."},
            {"icono": "✧", "titulo": "Celebrate Together", "texto": "Include your little companion in the moments that make the season special."},
        ],
    },
    "dog-sweater": {
        "nombre": "Dog Sweater",
        "precio": "$125",
        "imagen": "tienda/img/dog-sweater.jpg",
        "tagline": "Everyday Comfort. Unmistakable Style.",
        "descripcion": "A timeless wardrobe essential for dachshunds, designed to bring effortless style to everyday walks and relaxed moments.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Everyday Style", "texto": "A timeless look for walks, outings, and relaxed moments together."},
            {"icono": "⌁", "titulo": "Made for Dachshund Charm", "texto": "A look that celebrates the distinctive personality of your companion."},
            {"icono": "◇", "titulo": "Comfort Comes First", "texto": "Check the fit to help your dog move naturally and comfortably."},
            {"icono": "✧", "titulo": "A Wardrobe Essential", "texto": "Bring a little extra personality to everyday adventures."},
        ],
    },
}

def inicio(request):
    return render(request, "tienda/inicio.html")

def productos(request):
    return render(request, "tienda/productos.html", {"productos": PRODUCTOS})

def detalle(request, producto):
    item = PRODUCTOS.get(producto)
    if item is None:
        return render(request, "tienda/detalle.html", {"producto": None}, status=404)
    return render(request, "tienda/detalle.html", {"producto": item})


SESSION_DOGS = "dogs"


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


def smart_fit(request):
    from . import services

    producto = _requested_product(request)
    require_neck = bool(producto) and services.measurement_requirements(producto)["neck_girth"]
    if request.method == "POST":
        form = SmartFitForm(request.POST, require_neck=require_neck)
        if form.is_valid():
            dog = form.save()
            _remember_dog(request, dog)
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
    if request.method == "POST":
        form = SmartFitForm(request.POST, require_neck=require_neck)
        if form.is_valid():
            form.save(instance=dog)
            _remember_dog(request, dog)
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
        },
    )


def smart_quote_crear(request, public_id):
    # Local import: services depende de PRODUCTOS (definido en este módulo).
    from . import services

    dog = get_object_or_404(DogProfile, public_id=public_id)
    if request.method != "POST":
        return redirect("smart_fit_resultado", public_id=dog.public_id)
    # Solo se lee la clave del producto; cualquier precio enviado se ignora.
    slug = request.POST.get("producto", "")
    if slug in PRODUCTOS and services.missing_measurements(dog, slug):
        # La prenda exige una medida que falta: se pide antes de cotizar.
        url = reverse("smart_fit_editar", args=[dog.public_id])
        return redirect(f"{url}?producto={slug}")
    try:
        quote = services.create_quote(dog, slug)
    except services.UnknownProduct:
        return render(
            request,
            "tienda/smartfit_resultado.html",
            {"dog": dog, "productos": PRODUCTOS, "quote_error": "Please choose a product."},
            status=400,
        )
    return redirect("smart_quote", public_id=quote.public_id)


def smart_quote(request, public_id):
    from . import services

    quote = get_object_or_404(Quote, public_id=public_id)
    return render(
        request,
        "tienda/smartquote.html",
        {
            "quote": quote,
            "dog": quote.dog,
            "producto": services.get_product(quote.product_slug),
            "breakdown": services.build_breakdown(quote),
        },
    )


def checkout(request, public_id):
    from . import services

    quote = get_object_or_404(Quote.objects.select_related("dog"), public_id=public_id)
    existing = Order.objects.filter(quote=quote).first()
    if existing:
        return redirect("order_detail", public_id=existing.public_id)
    if quote.status == Quote.Status.CANCELLED:
        return render(request, "tienda/checkout.html", {"cancelled": True}, status=400)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order, _ = services.create_order(quote, form.cleaned_data)
            except services.QuoteNotOrderable:
                return render(request, "tienda/checkout.html", {"cancelled": True}, status=400)
            return redirect("order_detail", public_id=order.public_id)
    else:
        form = CheckoutForm()
    return render(
        request,
        "tienda/checkout.html",
        {
            "form": form,
            "quote": quote,
            "dog": quote.dog,
            "producto": services.get_product(quote.product_slug),
            "breakdown": services.build_breakdown(quote),
        },
    )


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
            "selected": occasion,
            "q": q,
            "reply": reply,
        },
    )
