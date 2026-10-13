from django.urls import path
from django.contrib.auth import views as auth_views

from . import panel, views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.productos, name="productos"),
    path("producto/<str:producto>/", views.detalle, name="detalle"),
    path("smart-fit/", views.smart_fit, name="smart_fit"),
    path("guide/", views.assistant, name="assistant"),
    path("smart-fit/<uuid:public_id>/", views.smart_fit_resultado, name="smart_fit_resultado"),
    path("smart-fit/<uuid:public_id>/cotizar/", views.smart_quote_crear, name="smart_quote_crear"),
    path("quote/<uuid:public_id>/", views.smart_quote, name="smart_quote"),
    path("quote/<uuid:public_id>/checkout/", views.checkout, name="checkout"),
    path("order/<uuid:public_id>/", views.order_detail, name="order_detail"),
    path(
        "panel/login/",
        auth_views.LoginView.as_view(template_name="tienda/panel_login.html"),
        name="panel_login",
    ),
    path("panel/logout/", auth_views.LogoutView.as_view(), name="panel_logout"),
    path("panel/", panel.orders, name="panel_orders"),
    path("panel/orders/<uuid:public_id>/", panel.order, name="panel_order"),
]
