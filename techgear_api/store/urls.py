from django.urls import path

from store.views import (
    AdminOrderListView,
    AdminOrderStatusView,
    CartView,
    CategoryDetailView,
    CategoryListCreateView,
    HealthView,
    LoginView,
    OrderListCreateView,
    ProductDetailView,
    ProductListCreateView,
    RegisterView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("categories/", CategoryListCreateView.as_view(), name="categories"),
    path("categories/<str:category_id>/", CategoryDetailView.as_view(), name="category-detail"),
    path("products/", ProductListCreateView.as_view(), name="products"),
    path("products/<str:product_id>/", ProductDetailView.as_view(), name="product-detail"),
    path("cart/", CartView.as_view(), name="cart"),
    path("orders/", OrderListCreateView.as_view(), name="orders"),
    path("admin/orders/", AdminOrderListView.as_view(), name="admin-orders"),
    path("admin/orders/<str:order_id>/", AdminOrderStatusView.as_view(), name="admin-order-status"),
]
