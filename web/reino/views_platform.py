"""Plataforma: gateway, directorio de tiendas (P01), para-negocios (M01), P02."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

from .models import Merchant, Store


def directory(request):
    """P01 · Directorio de tiendas de la demostración.

    Texto honesto: comercios de demostración; la marca activa siempre visible.
    """
    stores = Store.objects.exclude(status=Store.Status.DRAFT).select_related("merchant")
    return render(request, "reino/directory.html", {"stores": stores})


def for_business(request):
    """M01 · Presentación de Reino Commerce para comercios (piloto por invitación)."""
    return render(request, "reino/for_business.html")


@login_required(login_url="panel_login")
@user_passes_test(lambda u: u.is_superuser, login_url="panel_login")
def platform_admin(request):
    """P02 mínimo: comercios, estados y consumo de IA (solo superusuario)."""
    merchants = Merchant.objects.prefetch_related("stores").all()
    return render(request, "reino/platform_admin.html", {"merchants": merchants})
