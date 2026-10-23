"""Rutas de la plataforma Reino Commerce (mapa de pantallas §5).

- "" redirige a /tiendas/ (directorio P01); la home histórica de Weiner
  Kingdom queda preservada en /legacy/ (redirección documentada).
- /s/<slug>/... namespacing por tienda (S01–S12).
- /cuenta/ Royal Passport (S10), /para-negocios/ (M01), /negocio/<slug>/ (M03+),
  /plataforma/ (P02 mínimo).
"""

from django.urls import path

from . import views_account, views_looklab, views_merchant, views_platform, views_storefront, views_stylist

urlpatterns = [
    # NOTA: "/" la sirve la app histórica `tienda` (home preservada, tests en verde).
    # La plataforma nueva vive en /tiendas/ y /s/<slug>/ (redirección documentada en docs/01).
    path("tiendas/", views_platform.directory, name="reino_directory"),
    path("para-negocios/", views_platform.for_business, name="reino_for_business"),
    path("plataforma/", views_platform.platform_admin, name="reino_platform"),

    # S01–S12 · tienda
    path("s/<slug:slug>/", views_storefront.store_home, name="reino_store_home"),
    path("s/<slug:slug>/coleccion/", views_storefront.collection, name="reino_collection"),
    path("s/<slug:slug>/producto/<slug:product_slug>/", views_storefront.product_detail, name="reino_product"),
    path("s/<slug:slug>/tallas/", views_storefront.smart_fit, name="reino_fit"),
    path("s/<slug:slug>/looklab/", views_looklab.looklab, name="reino_looklab"),
    path("s/<slug:slug>/looklab/agregar/", views_looklab.looklab_add, name="reino_looklab_add"),
    path("s/<slug:slug>/looklab/guardar/", views_looklab.looklab_save, name="reino_looklab_save"),
    path("s/<slug:slug>/asesor/", views_stylist.stylist, name="reino_stylist"),
    path("s/<slug:slug>/asesor/mensaje/", views_stylist.stylist_message, name="reino_stylist_message"),
    path("s/<slug:slug>/carrito/", views_storefront.cart_view, name="reino_cart"),
    path("s/<slug:slug>/carrito/agregar/", views_storefront.cart_add, name="reino_cart_add"),
    path("s/<slug:slug>/carrito/linea/<int:item_id>/", views_storefront.cart_update, name="reino_cart_update"),
    path("s/<slug:slug>/carrito/linea/<int:item_id>/quitar/", views_storefront.cart_remove, name="reino_cart_remove"),
    path("s/<slug:slug>/checkout/", views_storefront.checkout, name="reino_checkout"),
    path("s/<slug:slug>/pedido/<uuid:public_id>/", views_storefront.order_detail, name="reino_order"),
    path("s/<slug:slug>/pedido/<uuid:public_id>/<uuid:token>/", views_storefront.order_detail, name="reino_order_guest"),
    path("s/<slug:slug>/ayuda/", views_storefront.help_center, name="reino_help"),

    # S10 · cuenta / Royal Passport
    path("cuenta/", views_account.account_home, name="reino_account"),
    path("cuenta/perfiles/nuevo/", views_account.profile_create, name="reino_profile_create"),
    path("cuenta/perfiles/<uuid:public_id>/medidas/", views_account.profile_measurements, name="reino_profile_measure"),
    path("cuenta/perfiles/<uuid:public_id>/activar/", views_account.profile_activate, name="reino_profile_activate"),
    path("cuenta/perfiles/<uuid:public_id>/memoria/borrar/", views_account.profile_memory_delete, name="reino_profile_memory_delete"),
    path("cuenta/consentimiento/", views_account.consent_update, name="reino_consent"),
    path("cuenta/looks/", views_account.looks, name="reino_looks"),

    # M01–M10 · panel del comerciante
    path("negocio/<slug:slug>/", views_merchant.dashboard, name="reino_merchant"),
    path("negocio/<slug:slug>/catalogo/", views_merchant.catalog, name="reino_merchant_catalog"),
    path("negocio/<slug:slug>/pedidos/", views_merchant.orders, name="reino_merchant_orders"),
    path("negocio/<slug:slug>/pedidos/<uuid:public_id>/", views_merchant.order_detail, name="reino_merchant_order"),
    path("negocio/<slug:slug>/pedidos/<uuid:public_id>/transicion/", views_merchant.order_transition, name="reino_merchant_order_transition"),
    path("negocio/<slug:slug>/configuracion/", views_merchant.settings_view, name="reino_merchant_settings"),
]
