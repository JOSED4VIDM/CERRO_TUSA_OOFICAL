from django.urls import path

from storefront import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.catalog, name="catalog"),
    path("producto/<str:product_id>/", views.product_detail, name="product"),
    path("cuenta/", views.account, name="account"),
    path("salir/", views.logout, name="logout"),
    path("carrito/", views.cart, name="cart"),
    path("carrito/agregar/<str:product_id>/", views.add_to_cart, name="add-to-cart"),
    path("carrito/quitar/<str:product_id>/", views.remove_from_cart, name="remove-from-cart"),
    path("carrito/confirmar/", views.checkout, name="checkout"),
    path("pedidos/", views.orders, name="orders"),
    path("gestion/", views.admin_dashboard, name="admin-dashboard"),
]
