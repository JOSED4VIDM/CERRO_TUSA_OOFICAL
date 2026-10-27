from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from urllib.parse import urlencode

from storefront.api import StoreAPIError, api_request


def _api(path, *, request=None, method="GET", data=None):
    token = request.session.get("techgear_token") if request else None
    return api_request(path, method=method, token=token, data=data)


def _error(request, error):
    messages.error(request, str(error))


def health(request):
    try:
        _api("health/")
        return render(request, "storefront/health.html", {"api_status": "Conectada"})
    except StoreAPIError as exc:
        return render(request, "storefront/health.html", {"api_status": str(exc)}, status=503)


def catalog(request):
    try:
        filters = {
            key: request.GET.get(key, "").strip()
            for key in ("category", "search")
            if request.GET.get(key, "").strip()
        }
        product_path = "products/"
        if filters:
            product_path += f"?{urlencode(filters)}"
        products = _api(product_path, request=request)
        categories = _api("categories/", request=request)
        category_names = {category["id"]: category["name"] for category in categories}
        for product in products:
            product["category_name"] = category_names.get(product["category_id"], "TechGear")
    except StoreAPIError as exc:
        products, categories = [], []
        _error(request, exc)
    return render(request, "storefront/catalog.html", {
        "products": products,
        "categories": categories,
        "selected_category": request.GET.get("category", ""),
        "search": request.GET.get("search", ""),
    })


def product_detail(request, product_id):
    try:
        product = _api(f"products/{product_id}/", request=request)
        categories = _api("categories/")
    except StoreAPIError as exc:
        _error(request, exc)
        return redirect("catalog")
    return render(request, "storefront/product.html", {"product": product, "categories": categories})


@require_http_methods(["GET", "POST"])
def account(request):
    if request.method == "POST":
        action = request.POST.get("action")
        data = {"email": request.POST.get("email", ""), "password": request.POST.get("password", "")}
        if action == "register":
            data["name"] = request.POST.get("name", "")
            path = "auth/register/"
        else:
            path = "auth/login/"
        try:
            response = _api(path, method="POST", data=data)
            request.session["techgear_token"] = response["token"]
            request.session["techgear_user"] = response["user"]
            return redirect("catalog")
        except StoreAPIError as exc:
            _error(request, exc)
    return render(request, "storefront/account.html")


@require_POST
def logout(request):
    request.session.pop("techgear_token", None)
    request.session.pop("techgear_user", None)
    messages.success(request, "Sesión cerrada.")
    return redirect("catalog")


def cart(request):
    if not request.session.get("techgear_token"):
        messages.info(request, "Inicia sesión para ver tu carrito.")
        return redirect("account")
    try:
        contents = _api("cart/", request=request)
    except StoreAPIError as exc:
        _error(request, exc)
        contents = {"items": [], "total": 0}
    return render(request, "storefront/cart.html", {"cart": contents})


@require_POST
def add_to_cart(request, product_id):
    if not request.session.get("techgear_token"):
        messages.info(request, "Inicia sesión para agregar productos al carrito.")
        return redirect("account")
    try:
        _api("cart/", request=request, method="POST", data={
            "product_id": product_id,
            "quantity": max(1, min(int(request.POST.get("quantity", "1")), 99)),
        })
        messages.success(request, "Producto agregado al carrito.")
    except (StoreAPIError, ValueError) as exc:
        _error(request, exc if isinstance(exc, StoreAPIError) else "La cantidad indicada no es válida.")
    return redirect("cart")


@require_POST
def remove_from_cart(request, product_id):
    try:
        _api("cart/", request=request, method="DELETE", data={"product_id": product_id, "quantity": 1})
    except StoreAPIError as exc:
        _error(request, exc)
    return redirect("cart")


@require_POST
def checkout(request):
    try:
        order = _api("orders/", request=request, method="POST", data={})
        messages.success(request, f"Pedido recibido: {order['id']}. Estado: {order['status']}.")
        return redirect("orders")
    except StoreAPIError as exc:
        _error(request, exc)
        return redirect("cart")


def orders(request):
    if not request.session.get("techgear_token"):
        return redirect("account")
    try:
        order_list = _api("orders/", request=request)
    except StoreAPIError as exc:
        order_list = []
        _error(request, exc)
    return render(request, "storefront/orders.html", {"orders": order_list})


@require_http_methods(["GET", "POST"])
def admin_dashboard(request):
    user = request.session.get("techgear_user", {})
    if user.get("role") != "admin":
        messages.error(request, "Inicia sesión con una cuenta administradora.")
        return redirect("account")

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "category":
                _api("categories/", request=request, method="POST", data={
                    "name": request.POST.get("name", ""),
                    "slug": request.POST.get("slug", ""),
                    "description": request.POST.get("description", ""),
                    "active": True,
                })
                messages.success(request, "Categoría creada.")
            elif action == "product":
                product_id = request.POST.get("product_id", "").strip()
                data = {
                    "name": request.POST.get("name", ""),
                    "slug": request.POST.get("slug", ""),
                    "description": request.POST.get("description", ""),
                    "price": int(request.POST.get("price", "")),
                    "stock": int(request.POST.get("stock", "")),
                    "category_id": request.POST.get("category_id", ""),
                    "image_url": request.POST.get("image_url", ""),
                    "active": request.POST.get("active") == "true",
                }
                path = f"products/{product_id}/" if product_id else "products/"
                method = "PATCH" if product_id else "POST"
                _api(path, request=request, method=method, data=data)
                messages.success(request, "Producto guardado.")
            elif action == "deactivate_product":
                product_id = request.POST.get("product_id", "")
                _api(f"products/{product_id}/", request=request, method="DELETE")
                messages.success(request, "Producto desactivado.")
            elif action == "category_status":
                category_id = request.POST.get("category_id", "")
                active = request.POST.get("active") == "true"
                _api(f"categories/{category_id}/", request=request, method="PATCH", data={"active": active})
                messages.success(request, "Estado de categoría actualizado.")
            elif action == "order_status":
                order_id = request.POST.get("order_id", "")
                _api(
                    f"admin/orders/{order_id}/",
                    request=request,
                    method="PATCH",
                    data={"status": request.POST.get("status", "")},
                )
                messages.success(request, "Estado del pedido actualizado.")
            else:
                messages.error(request, "La acción de administración no es válida.")
        except (StoreAPIError, ValueError) as exc:
            _error(request, exc if isinstance(exc, StoreAPIError) else "Revisa los valores numéricos del producto.")
        return redirect("admin-dashboard")

    try:
        categories = _api("categories/", request=request)
        products = _api("products/", request=request)
        order_list = _api("admin/orders/", request=request)
        category_names = {category["id"]: category["name"] for category in categories}
        for product in products:
            product["category_name"] = category_names.get(product["category_id"], "Sin categoría")
    except StoreAPIError as exc:
        categories, products, order_list = [], [], []
        _error(request, exc)
    return render(request, "storefront/admin.html", {
        "categories": categories,
        "products": products,
        "orders": order_list,
    })
