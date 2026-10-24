"""Catálogo comercial (fuente de verdad de nombres, precios y fichas públicas).

Fuente: Weiner_Kingdom_Guia_Maestra_Organizada_v2.docx (tabla de productos).
Los precios base corresponden a perros pequeños. La ficha pública de
"Materiales del traje" contiene SOLO nombres y una explicación breve: nunca
consumos, precios unitarios, costos ni márgenes (eso es interno, ver
`ProductCost` / `MaterialLine`).
"""

# Pares (material, función breve). La función describe el material sin
# atribuirle propiedades que su nombre no respalde.
_WEDDING = [
    ("Satén Duchess de poliéster premium", "Tejido principal de apariencia formal y acabado satinado."),
    ("Forro de satén Bemberg", "Forro suave al tacto para mayor comodidad."),
    ("Encaje Chantilly bordado", "Detalle decorativo de encaje bordado."),
    ("Tul ilusión premium", "Capa ligera y translúcida de efecto decorativo."),
    ("Cierre invisible YKK", "Cierre discreto que no interrumpe la línea del traje."),
    ("Hilo Gütermann Mara", "Hilo de confección para costuras firmes."),
    ("Perlas y cristales decorativos", "Adornos para ocasiones especiales."),
    ("Entretela fusible premium", "Refuerzo interno que ayuda a mantener la forma."),
    ("Pasamanería y cinta satinada", "Remates decorativos de acabado fino."),
]
_TACTICAL = [
    ("Nylon Cordura 1000D", "Textil técnico de alta resistencia al desgaste."),
    ("Forro de malla 3D transpirable", "Capa interior que favorece la ventilación."),
    ("Cincha de nylon de alta resistencia", "Cincha estructural para ajustes y refuerzos."),
    ("Hebillas Duraflex", "Herrajes para ajustar y asegurar la prenda."),
    ("Cierre YKK de uso rudo", "Cierre reforzado para uso frecuente."),
    ("Velcro industrial", "Cierre de contacto de sujeción firme."),
    ("Hilo bonded nylon Tex 70", "Hilo resistente para costuras de refuerzo."),
    ("Panel acolchado de espuma EVA", "Acolchado que aporta amortiguación."),
    ("Argollas metálicas resistentes", "Puntos metálicos de anclaje."),
]
_CHRISTMAS = [
    ("Terciopelo de poliéster premium", "Tejido principal de tacto suave y aspecto festivo."),
    ("Tela tartán escocés premium", "Estampado de cuadros tradicional de temporada."),
    ("Forro de satén", "Forro liso y suave al contacto."),
    ("Ribete de pelo sintético premium", "Remate decorativo de textura suave."),
    ("Cierre YKK", "Cierre confiable para ponerse y quitar la prenda."),
    ("Hilo Gütermann Mara", "Hilo de confección para costuras firmes."),
    ("Galón dorado decorativo", "Cinta decorativa dorada."),
    ("Cascabeles y adornos festivos", "Detalles festivos de temporada."),
    ("Entretela premium", "Refuerzo interno que ayuda a mantener la forma."),
]
_ALNUT = [
    ("Polar fleece premium antipilling", "Exterior suave que resiste la formación de bolitas."),
    ("Forro térmico transpirable", "Capa interior que aporta abrigo y deja respirar."),
    ("Refuerzo de nylon para arnés", "Estructura resistente en zonas de tensión."),
    ("Hebillas de liberación rápida", "Permiten ponerlo y quitarlo con rapidez."),
    ("Cinta de ajuste acolchada", "Ajuste regulable con acolchado suave."),
    ("Cierre YKK", "Cierre confiable."),
    ("Hilo reforzado para exteriores", "Hilo resistente para costuras expuestas."),
    ("Etiqueta tejida de marca", "Identificación de marca."),
    ("Argollas metálicas resistentes", "Puntos metálicos de sujeción."),
]
_BEIGE = [
    ("Tejido beige premium resistente", "Tejido exterior resistente de tono beige."),
    ("Forro de malla suave", "Capa interior suave y ligera."),
    ("Espuma de acolchado", "Acolchado para mayor comodidad."),
    ("Cinta de nylon de alta resistencia", "Cinta estructural resistente."),
    ("Hebillas ajustables", "Permiten regular el ajuste."),
    ("Argolla metálica", "Punto metálico de sujeción."),
    ("Hilo de poliéster reforzado", "Hilo para costuras firmes."),
    ("Ribete suave antipellizcos", "Borde suave pensado para no pellizcar."),
    ("Etiqueta de marca", "Identificación de marca."),
]
_TUTTI = [
    ("Tejido premium pata de gallo", "Tejido exterior de estampado pata de gallo."),
    ("Forro suave transpirable", "Capa interior suave que deja respirar."),
    ("Cinta decorativa multicolor", "Detalle decorativo de colores."),
    ("Cinta de nylon estructural", "Cinta estructural resistente."),
    ("Hebillas ajustables", "Permiten regular el ajuste."),
    ("Argolla metálica", "Punto metálico de sujeción."),
    ("Hilo reforzado", "Hilo para costuras firmes."),
    ("Ribete suave de acabado", "Borde suave de acabado."),
    ("Etiqueta de marca", "Identificación de marca."),
]
_JUMPER = [
    ("Hilo premium de lana merino", "Fibra natural suave que aporta abrigo."),
    ("Hilo de mezcla de alpaca", "Fibra suave que complementa el abrigo."),
    ("Hilo elástico para puños", "Aporta elasticidad a los puños."),
    ("Hilo de confección", "Hilo para costuras y acabados."),
    ("Etiqueta tejida de marca", "Identificación de marca."),
    ("Refuerzo suave para el pecho", "Refuerzo interno suave en la zona del pecho."),
    ("Botones decorativos premium", "Detalle decorativo."),
]
_ROBE = [
    ("Tela de rizo con fibra de bambú", "Tejido absorbente de tacto suave."),
    ("Forro ligero absorbente", "Capa interior ligera que ayuda a absorber."),
    ("Cinta de ajuste suave", "Ajuste regulable y suave."),
    ("Velcro suave de contacto", "Cierre de contacto de tacto suave."),
    ("Ribete de algodón premium", "Borde de algodón para un acabado suave."),
    ("Hilo resistente a lavados", "Hilo pensado para lavados frecuentes."),
    ("Etiqueta tejida de marca", "Identificación de marca."),
    ("Broche de ajuste", "Broche para regular el ajuste."),
]


def _materials(pairs):
    return [{"nombre": n, "funcion": f} for n, f in pairs]


PRODUCTOS = {
    "wedding-dog": {
        "nombre": "Waterproof Linen Dachshund Wedding Dog Suit Pair for Two",
        "nombre_corto": "Wedding Dog",
        "precio": "$650",
        "imagen": "tienda/img/wedding-dog.jpg",
        "imagenes": ["tienda/img/wedding-dog.jpg"],
        "tagline": "A Little Suit for Your Biggest Moments.",
        "descripcion": "Elegant formalwear for dachshunds, designed for weddings, special celebrations, and unforgettable moments with your best friend.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "A Special-Occasion Look", "texto": "A polished style for weddings, celebrations, and memorable photographs."},
            {"icono": "⌁", "titulo": "Made for Dachshunds", "texto": "A distinctive look created with the long, charming dachshund silhouette in mind."},
            {"icono": "◇", "titulo": "Style with Comfort in Mind", "texto": "Choose a fit that lets your companion move as comfortably as possible."},
            {"icono": "✧", "titulo": "For Unforgettable Moments", "texto": "Celebrate the occasions when your best friend deserves to be part of the moment."},
        ],
        "materiales": _materials(_WEDDING),
    },
    "tactical-dog": {
        "nombre": "Tactical Dog",
        "nombre_corto": "Tactical Dog",
        "precio": "$300",
        "imagen": "tienda/img/tactical-dog.jpg",
        "imagenes": ["tienda/img/tactical-dog.jpg"],
        "tagline": "Built for Adventure. Styled for Royalty.",
        "descripcion": "A bold, functional look for dachshunds with fearless personalities, designed to bring distinctive style to everyday adventures.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Bold, Distinctive Style", "texto": "A confident look for dogs with plenty of personality."},
            {"icono": "⌁", "titulo": "Adventure-Inspired", "texto": "A playful design for outings, photos, and everyday adventures."},
            {"icono": "◇", "titulo": "Comfort Comes First", "texto": "Always choose a fit that allows your dog to move freely and comfortably."},
            {"icono": "✧", "titulo": "Ready for Their Moment", "texto": "Make ordinary outings and special snapshots feel a little more memorable."},
        ],
        "materiales": _materials(_TACTICAL),
    },
    "christmas-dog": {
        "nombre": "Christmas Dog",
        "nombre_corto": "Christmas Dog",
        "precio": "$250",
        "imagen": "tienda/img/christmas-dog.jpg",
        "imagenes": ["tienda/img/christmas-dog.jpg"],
        "tagline": "Make Every Celebration Magical.",
        "descripcion": "A festive look for holiday gatherings, family photos, and memorable celebrations with your little companion.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Festive by Design", "texto": "A seasonal look for holiday gatherings and celebrations."},
            {"icono": "⌁", "titulo": "Made for Photo Moments", "texto": "Bring extra charm to family pictures and seasonal memories."},
            {"icono": "◇", "titulo": "Comfort Comes First", "texto": "Check the fit and make sure your dog can move comfortably while wearing it."},
            {"icono": "✧", "titulo": "Celebrate Together", "texto": "Include your little companion in the moments that make the season special."},
        ],
        "materiales": _materials(_CHRISTMAS),
    },
    "alnut-whip-harness": {
        "nombre": "Walnut Whip Dachshund Harness Fleece",
        "nombre_corto": "Walnut Whip Harness",
        "precio": "$250.00",
        "imagen": "tienda/img/alnut-whip-1.jpg",
        "imagenes": ["tienda/img/alnut-whip-1.jpg", "tienda/img/alnut-whip-2.jpg"],
        "tagline": "Soft fleece outside, warm lining inside.",
        "descripcion": "Fleece-style harness with a soft outer layer, warm lining and durable details.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Soft, Pill-Resistant Fleece", "texto": "Premium antipilling polar fleece on the outside."},
            {"icono": "⌁", "titulo": "Warm, Breathable Lining", "texto": "A thermal, breathable lining for warmth."},
            {"icono": "◇", "titulo": "Secure, Quick Fit", "texto": "Quick-release buckles and a padded adjustment strap."},
        ],
        "materiales": _materials(_ALNUT),
    },
    "beige-anti-rub-harness": {
        "nombre": "Beige Sophisticated Sausage Dachshund Anti-Rub Dog Harness",
        "nombre_corto": "Beige Anti-Rub Harness",
        "precio": "$63.00",
        "imagen": "tienda/img/beige-harness-2.jpg",
        "imagenes": ["tienda/img/beige-harness-2.jpg", "tienda/img/beige-harness-1.jpg"],
        "tagline": "Padded comfort with soft edges.",
        "descripcion": "Padded beige harness with soft edges and durable hardware.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Padded Comfort", "texto": "Padding foam with a soft mesh lining."},
            {"icono": "⌁", "titulo": "Anti-Rub Edges", "texto": "Soft binding designed to avoid pinching."},
            {"icono": "◇", "titulo": "Adjustable Fit", "texto": "Adjustable buckles and a sturdy nylon strap."},
        ],
        "materiales": _materials(_BEIGE),
    },
    "tutti-frutti-harness": {
        "nombre": "Tutti Frutti Houndstooth Anti-Rub Harness – Ribbon",
        "nombre_corto": "Tutti Frutti Harness",
        "precio": "$63.00",
        "imagen": "tienda/img/tutti-frutti-1.jpg",
        "imagenes": ["tienda/img/tutti-frutti-1.jpg"],
        "tagline": "Houndstooth print with a ribbon finish.",
        "descripcion": "Printed harness with a decorative ribbon trim and an anti-rub finish.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Houndstooth Print", "texto": "Premium houndstooth fabric with a decorative multicolor ribbon."},
            {"icono": "⌁", "titulo": "Soft, Breathable Lining", "texto": "A soft lining that lets the garment breathe."},
            {"icono": "◇", "titulo": "Adjustable Fit", "texto": "Adjustable buckles and a structural nylon strap."},
        ],
        "materiales": _materials(_TUTTI),
    },
    "cable-knit-jumper": {
        "nombre": "Luxury Cable Knit Dachshund Jumper",
        "nombre_corto": "Cable Knit Jumper",
        "precio": "$150.00",
        "imagen": "tienda/img/cable-knit-jumper-1.jpg",
        "imagenes": ["tienda/img/cable-knit-jumper-1.jpg"],
        "tagline": "Cable-knit warmth with knitted finishes.",
        "descripcion": "Cable-knit jumper made from a blend of premium fibers with knitted finishes.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Merino and Alpaca Blend", "texto": "A blend of merino wool and alpaca yarns."},
            {"icono": "⌁", "titulo": "Elastic Cuffs", "texto": "Elastic yarn in the cuffs."},
            {"icono": "◇", "titulo": "Finishing Details", "texto": "Decorative buttons and a soft chest reinforcement."},
        ],
        "materiales": _materials(_JUMPER),
    },
    "bamboo-drying-robe": {
        "nombre": "Showercover Bamboo Dachshund Drying Robe",
        "nombre_corto": "Bamboo Drying Robe",
        "precio": "$88.00",
        "imagen": "tienda/img/drying-robe-1.jpg",
        "imagenes": [
            "tienda/img/drying-robe-1.jpg",
            "tienda/img/drying-robe-2.jpg",
            "tienda/img/drying-robe-3.jpg",
        ],
        "tagline": "Absorbent bamboo fabric, soft finishes.",
        "descripcion": "Absorbent robe made with bamboo-fibre fabric, an adjustable closure and soft finishes.",
        "caracteristicas": [
            {"icono": "✦", "titulo": "Bamboo-Fibre Terry", "texto": "Absorbent terry fabric with bamboo fibre."},
            {"icono": "⌁", "titulo": "Light Absorbent Lining", "texto": "A lightweight lining that helps absorb water."},
            {"icono": "◇", "titulo": "Adjustable Closure", "texto": "Soft-touch fastener and an adjustment clasp."},
        ],
        "materiales": _materials(_ROBE),
    },
}

# Producto retirado del catálogo activo: se conserva solo para que pedidos o
# cotizaciones históricas sigan siendo legibles. No se puede cotizar.
RETIRED_SLUGS = ("dog-sweater",)
