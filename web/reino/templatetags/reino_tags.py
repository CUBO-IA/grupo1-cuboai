from django import template

register = template.Library()


@register.filter
def lookup(mapping, key):
    """Acceso a dict por clave en templates (p. ej. medidas por perfil)."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


# Razones del motor traducidas a lenguaje comercial verificable (auditoría §4):
# los códigos internos quedan en diagnóstico, nunca en el recorrido del cliente.
REASON_LABELS = {
    "MATCH_OCCASION": "Coincide con la ocasión",
    "MATCH_STYLE": "Coincide con el estilo que elegiste",
    "FIT_RANGE_CONFIRMED": "Talla confirmada por sus medidas",
    "FIT_NEEDS_REVIEW": "Talla al límite: conviene revisar la guía",
    "FIT_UNKNOWN": "Talla por confirmar",
    "BUDGET_TOTAL_OK": "Dentro de tu presupuesto",
    "DELIVERY_UNKNOWN": "Entrega por confirmar",
    "QUALITY_COMPLETE": "Ficha completa revisada",
    "EDITORIAL_FEATURED": "Selección editorial de la casa",
}

EXCLUDED_LABELS = {
    "OUT_OF_STOCK": "sin existencias",
    "OVER_BUDGET": "supera el presupuesto por pieza",
    "OVER_BUDGET_TOTAL": "supera el presupuesto del conjunto",
    "FIT_INCOMPATIBLE": "no es compatible con sus medidas",
}


@register.filter
def reason_label(code):
    """Código interno => frase comercial; un código desconocido no se muestra."""
    return REASON_LABELS.get(code, "")


@register.filter
def excluded_label(code):
    return EXCLUDED_LABELS.get(code, code)


@register.filter
def module_visible(modules, key):
    """Marca el checkbox si el módulo está visible en la config del tema."""
    for module in (modules or []):
        if module.get("key") == key:
            return 'checked="checked"' if module.get("visible") else ""
    return 'checked="checked"'  # módulo nuevo: visible por defecto
