"""Asistente guiado determinista (Task 9).

No usa IA generativa ni servicios externos: responde solo con datos del
catálogo (`PRODUCTOS`) y textos fijos. Todo lo que no está en el catálogo se
declara como desconocido en vez de inventarse. No sustituye las validaciones
del backend: las medidas y el precio se siguen validando en Smart Fit/Smart Quote.
"""

from .catalog import PRODUCTOS

MAX_QUERY_LENGTH = 200

# Ocasiones guiadas -> productos del catálogo.
OCCASIONS = {
    "wedding": (
        "Wedding or special occasion",
        ["wedding-dog"],
        "A formal suit pair made for weddings and special celebrations.",
    ),
    "adventure": (
        "Tactical or outdoor style",
        ["tactical-dog"],
        "Our bold outdoor-style outfit for adventures.",
    ),
    "holiday": (
        "Christmas or festive outfit",
        ["christmas-dog"],
        "Our festive outfit for holiday gatherings and photos.",
    ),
    "everyday": (
        "Comfortable everyday wear",
        ["cable-knit-jumper", "beige-anti-rub-harness"],
        "Comfortable pieces for everyday style.",
    ),
    "walks": (
        "Harness for walks",
        ["beige-anti-rub-harness", "alnut-whip-harness", "tutti-frutti-harness"],
        "Harnesses designed for walks.",
    ),
    "warmth": (
        "Warm knitted clothing",
        ["cable-knit-jumper"],
        "A knitted jumper to keep your dachshund warm.",
    ),
    "bath": (
        "Drying robe after a bath",
        ["bamboo-drying-robe"],
        "A robe to dry your dog after a bath.",
    ),
}

# Palabras clave -> producto (coinciden con nombres y descripciones del catálogo).
PRODUCT_KEYWORDS = {
    "wedding-dog": ("wedding", "formal", "suit", "celebration"),
    "tactical-dog": ("tactical", "adventure", "outdoor", "bold"),
    "christmas-dog": ("christmas", "holiday", "festive", "xmas"),
    "alnut-whip-harness": ("walnut", "alnut", "fleece", "harness"),
    "beige-anti-rub-harness": ("beige", "harness"),
    "tutti-frutti-harness": ("tutti", "frutti", "houndstooth", "ribbon", "harness"),
    "cable-knit-jumper": ("jumper", "cable", "knit", "sweater"),
    "bamboo-drying-robe": ("robe", "bamboo", "drying", "bath", "towel"),
}

PRICE_WORDS = ("price", "cost", "how much", "cuanto", "precio")
MEASURE_WORDS = ("measure", "measurement", "size", "fit", "medida", "talla", "tamaño")
UNSUPPORTED_WORDS = {
    "shipping": ("shipping", "delivery", "envio", "envío", "ship"),
    "payment": ("pay", "payment", "bitcoin", "card", "discount", "pago", "descuento"),
    "order status": ("order status", "my order", "track", "tracking", "pedido"),
    "returns": ("return", "refund", "warranty", "devolucion", "devolución"),
}

MEASURE_HELP = (
    "To get a quote we need your dog's name, breed, weight, back length and chest girth "
    "(neck girth is optional). You can use kg/lb and cm/in."
)


def _products_in(text):
    return [
        slug
        for slug, words in PRODUCT_KEYWORDS.items()
        if any(w in text for w in words)
    ]


def _product_card(slug):
    item = PRODUCTOS[slug]
    return {
        "slug": slug,
        "name": item["nombre"],
        "price": item["precio"],
        "tagline": item["tagline"],
        "description": item["descripcion"],
        "image": item["imagen"],
    }


def recommend(occasion):
    """Recomendación guiada por ocasión; None si la opción no existe."""
    if occasion not in OCCASIONS:
        return None
    _label, slugs, why = OCCASIONS[occasion]
    slugs = [s for s in slugs if s in PRODUCTOS]
    if not slugs:
        return None
    top = PRODUCTOS[slugs[0]]["nombre"]
    return {
        "message": f"Our best match: {top}. {why}",
        "products": [_product_card(s) for s in slugs],
        "next": "smart_fit",
        "unknown": False,
    }


def answer(query):
    """Respuesta determinista a una pregunta libre corta."""
    text = (query or "").strip().lower()[:MAX_QUERY_LENGTH]
    if not text:
        return {
            "message": "Please choose an option or type a short question.",
            "products": [],
            "next": None,
            "unknown": True,
        }

    for topic, words in UNSUPPORTED_WORDS.items():
        if any(w in text for w in words):
            return {
                "message": (
                    f"I don't have confirmed information about {topic} yet, so I can't "
                    "answer that. Our team will confirm it before any payment."
                ),
                "products": [],
                "next": None,
                "unknown": True,
            }

    found = _products_in(text)
    if len(found) > 1:
        names = " and ".join(PRODUCTOS[s]["nombre"] for s in found)
        return {
            "message": (
                f"You mentioned more than one product ({names}). "
                "Which one would you like to know about?"
            ),
            "products": [_product_card(s) for s in found],
            "next": None,
            "unknown": False,
        }

    if any(w in text for w in MEASURE_WORDS):
        return {
            "message": MEASURE_HELP + " We do not calculate a size or a size-based price yet.",
            "products": [_product_card(found[0])] if found else [],
            "next": "smart_fit",
            "unknown": False,
        }

    if found:
        card = _product_card(found[0])
        asks_price = any(w in text for w in PRICE_WORDS)
        message = (
            f"{card['name']} has a base price of {card['price']}. "
            "The final price is confirmed by Weiner Kingdom."
            if asks_price
            else f"{card['name']}: {card['description']}"
        )
        return {"message": message, "products": [card], "next": "smart_fit", "unknown": False}

    if any(w in text for w in PRICE_WORDS):
        return {
            "message": "Tell me which product you are interested in and I will share its base price.",
            "products": [_product_card(s) for s in PRODUCTOS],
            "next": None,
            "unknown": False,
        }

    return {
        "message": (
            "I can only help with our four products and how to take your dog's measurements. "
            "I don't have that information."
        ),
        "products": [],
        "next": None,
        "unknown": True,
    }
