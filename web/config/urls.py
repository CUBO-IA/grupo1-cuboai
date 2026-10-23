from django.urls import include, path

urlpatterns = [
    # Plataforma Reino Commerce (P0). La ruta "/" la resuelve primero `reino`;
    # todas las demás rutas históricas de `tienda` quedan intactas debajo
    # (Smart Fit, Smart Quote, cotización, carrito legacy, pedido y panel).
    path("", include("reino.urls")),
    path("", include("tienda.urls")),
]
