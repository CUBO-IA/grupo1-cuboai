from django.shortcuts import get_object_or_404, redirect, render

from .forms import SmartFitForm
from .models import DogProfile, Quote

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


def smart_fit(request):
    if request.method == "POST":
        form = SmartFitForm(request.POST)
        if form.is_valid():
            dog = form.save()
            return redirect("smart_fit_resultado", pk=dog.pk)
    else:
        form = SmartFitForm(initial={"weight_unit": "kg", "length_unit": "cm"})
    return render(request, "tienda/smartfit.html", {"form": form})


def smart_fit_resultado(request, pk):
    dog = get_object_or_404(DogProfile, pk=pk)
    return render(
        request, "tienda/smartfit_resultado.html", {"dog": dog, "productos": PRODUCTOS}
    )


def smart_quote_crear(request, pk):
    # Local import: services depende de PRODUCTOS (definido en este módulo).
    from . import services

    dog = get_object_or_404(DogProfile, pk=pk)
    if request.method != "POST":
        return redirect("smart_fit_resultado", pk=dog.pk)
    # Solo se lee la clave del producto; cualquier precio enviado se ignora.
    slug = request.POST.get("producto", "")
    try:
        quote = services.create_quote(dog, slug)
    except services.UnknownProduct:
        return render(
            request,
            "tienda/smartfit_resultado.html",
            {"dog": dog, "productos": PRODUCTOS, "quote_error": "Please choose a product."},
            status=400,
        )
    return redirect("smart_quote", pk=quote.pk)


def smart_quote(request, pk):
    from . import services

    quote = get_object_or_404(Quote, pk=pk)
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
