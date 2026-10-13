from django.urls import path
from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.productos, name="productos"),
    path("producto/<str:producto>/", views.detalle, name="detalle"),
]
