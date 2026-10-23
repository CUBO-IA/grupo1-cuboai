from django import template

register = template.Library()


@register.filter
def lookup(mapping, key):
    """Acceso a dict por clave en templates (p. ej. medidas por perfil)."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None
