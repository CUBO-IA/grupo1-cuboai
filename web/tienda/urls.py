from django.urls import path
from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.productos, name="productos"),
    path("producto/<str:producto>/", views.detalle, name="detalle"),
    path("smart-fit/", views.smart_fit, name="smart_fit"),
    path("smart-fit/<uuid:public_id>/", views.smart_fit_resultado, name="smart_fit_resultado"),
    path("smart-fit/<uuid:public_id>/cotizar/", views.smart_quote_crear, name="smart_quote_crear"),
    path("quote/<uuid:public_id>/", views.smart_quote, name="smart_quote"),
    path("quote/<uuid:public_id>/checkout/", views.checkout, name="checkout"),
    path("order/<uuid:public_id>/", views.order_detail, name="order_detail"),
]
