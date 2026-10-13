from django.urls import path
from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.productos, name="productos"),
    path("producto/<str:producto>/", views.detalle, name="detalle"),
    path("smart-fit/", views.smart_fit, name="smart_fit"),
    path("smart-fit/<int:pk>/", views.smart_fit_resultado, name="smart_fit_resultado"),
    path("smart-fit/<int:pk>/cotizar/", views.smart_quote_crear, name="smart_quote_crear"),
    path("quote/<int:pk>/", views.smart_quote, name="smart_quote"),
]
