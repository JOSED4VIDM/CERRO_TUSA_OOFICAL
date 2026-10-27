import logging
import re
from datetime import datetime, timezone

from bson import ObjectId
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from pymongo.errors import DuplicateKeyError, PyMongoError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from store.authentication import issue_token
from store.mongo import get_client, get_database
from store.permissions import IsStoreAdmin
from store.serializers import (
    CartItemSerializer,
    CartRemoveItemSerializer,
    CategorySerializer,
    LoginSerializer,
    OrderStatusSerializer,
    ProductSerializer,
    RegisterSerializer,
)

logger = logging.getLogger(__name__)


def public_document(document):
    result = dict(document)
    result["id"] = str(result.pop("_id"))
    result.pop("password_hash", None)
    return result


def mongo_object_id(value):
    return ObjectId(value) if ObjectId.is_valid(value) else None


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        if not settings.TECHGEAR_MONGODB_URI:
            return Response({"status": "error", "detail": "TECHGEAR_MONGODB_URI no está configurado."}, status=503)
        try:
            get_client().admin.command("ping")
        except PyMongoError:
            logger.exception("TechGear Atlas health check failed")
            return Response({"status": "error", "detail": "No se pudo conectar con MongoDB Atlas."}, status=503)
        return Response({"status": "ok", "database": settings.TECHGEAR_MONGODB_DATABASE})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        email = values["email"].strip().lower()
        database = get_database()
        if database["users"].find_one({"email": email}):
            return Response({"detail": "Ya existe una cuenta con ese correo."}, status=409)
        user = {
            "name": values["name"].strip(),
            "email": email,
            "password_hash": make_password(values["password"]),
            "role": "customer",
            "active": True,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            result = database["users"].insert_one(user)
        except DuplicateKeyError:
            return Response({"detail": "Ya existe una cuenta con ese correo."}, status=409)
        user["_id"] = result.inserted_id
        try:
            token = issue_token(result.inserted_id)
        except RuntimeError as exc:
            database["users"].delete_one({"_id": result.inserted_id})
            return Response({"detail": str(exc)}, status=503)
        if settings.DEBUG and not settings.TECHGEAR_JWT_SECRET:
            logger.warning("TECHGEAR_JWT_SECRET is unset; using the development-only fallback.")
        return Response({"token": token, "user": public_document(user)}, status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        user = get_database()["users"].find_one({"email": values["email"].strip().lower(), "active": True})
        if user is None or not check_password(values["password"], user.get("password_hash", "")):
            return Response({"detail": "Correo o contraseña incorrectos."}, status=401)
        try:
            token = issue_token(user["_id"])
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=503)
        if settings.DEBUG and not settings.TECHGEAR_JWT_SECRET:
            logger.warning("TECHGEAR_JWT_SECRET is unset; using the development-only fallback.")
        return Response({"token": token, "user": public_document(user)})


class CategoryListCreateView(APIView):
    def get_permissions(self):
        return [IsStoreAdmin()] if self.request.method == "POST" else [AllowAny()]

    def get(self, request):
        query = {"active": True}
        if request.user.is_authenticated and request.user.role == "admin":
            query = {}
        categories = get_database()["categories"].find(query).sort("name", 1).limit(200)
        return Response([public_document(item) for item in categories])

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = {**serializer.validated_data, "created_at": datetime.now(timezone.utc)}
        try:
            result = get_database()["categories"].insert_one(document)
        except DuplicateKeyError:
            return Response({"detail": "Ya existe una categoría con ese identificador."}, status=409)
        document["_id"] = result.inserted_id
        return Response(public_document(document), status=201)


class CategoryDetailView(APIView):
    permission_classes = [IsStoreAdmin]

    def patch(self, request, category_id):
        object_id = mongo_object_id(category_id)
        if object_id is None:
            return Response({"detail": "No se encontró la categoría."}, status=404)
        current = get_database()["categories"].find_one({"_id": object_id})
        if current is None:
            return Response({"detail": "No se encontró la categoría."}, status=404)
        serializer = CategorySerializer(data={**current, **request.data})
        serializer.is_valid(raise_exception=True)
        try:
            get_database()["categories"].update_one({"_id": object_id}, {"$set": serializer.validated_data})
        except DuplicateKeyError:
            return Response({"detail": "Ya existe una categoría con ese identificador."}, status=409)
        return Response(public_document({**current, **serializer.validated_data}))


class ProductListCreateView(APIView):
    def get_permissions(self):
        return [IsStoreAdmin()] if self.request.method == "POST" else [AllowAny()]

    def get(self, request):
        query = {"active": True}
        if request.user.is_authenticated and request.user.role == "admin":
            query = {}
        category_id = request.query_params.get("category")
        if category_id:
            object_id = mongo_object_id(category_id)
            if object_id is None:
                return Response({"detail": "La categoría no es válida."}, status=400)
            query["category_id"] = str(object_id)
        search = request.query_params.get("search", "").strip()
        if search:
            safe_search = re.escape(search[:80])
            query["$or"] = [
                {"name": {"$regex": safe_search, "$options": "i"}},
                {"description": {"$regex": safe_search, "$options": "i"}},
            ]
        products = get_database()["products"].find(query).sort("created_at", -1).limit(100)
        return Response([public_document(item) for item in products])

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        category_id = ObjectId(values["category_id"])
        if get_database()["categories"].find_one({"_id": category_id, "active": True}) is None:
            return Response({"detail": "Selecciona una categoría activa."}, status=400)
        document = {**values, "category_id": str(category_id), "created_at": datetime.now(timezone.utc)}
        try:
            result = get_database()["products"].insert_one(document)
        except DuplicateKeyError:
            return Response({"detail": "Ya existe un producto con ese identificador."}, status=409)
        document["_id"] = result.inserted_id
        return Response(public_document(document), status=201)


class ProductDetailView(APIView):
    def get_permissions(self):
        return [IsStoreAdmin()] if self.request.method in {"PATCH", "DELETE"} else [AllowAny()]

    def get(self, request, product_id):
        object_id = mongo_object_id(product_id)
        if object_id is None:
            return Response({"detail": "No se encontró el producto."}, status=404)
        query = {"_id": object_id}
        if not request.user.is_authenticated or request.user.role != "admin":
            query["active"] = True
        product = get_database()["products"].find_one(query)
        if product is None:
            return Response({"detail": "No se encontró el producto."}, status=404)
        return Response(public_document(product))

    def patch(self, request, product_id):
        object_id = mongo_object_id(product_id)
        if object_id is None:
            return Response({"detail": "No se encontró el producto."}, status=404)
        current = get_database()["products"].find_one({"_id": object_id})
        if current is None:
            return Response({"detail": "No se encontró el producto."}, status=404)
        serializer = ProductSerializer(data={**current, **request.data})
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if get_database()["categories"].find_one({"_id": ObjectId(values["category_id"]), "active": True}) is None:
            return Response({"detail": "Selecciona una categoría activa."}, status=400)
        try:
            get_database()["products"].update_one(
                {"_id": object_id},
                {"$set": {**values, "category_id": str(values["category_id"])}},
            )
        except DuplicateKeyError:
            return Response({"detail": "Ya existe un producto con ese identificador."}, status=409)
        return Response(public_document({**current, **values}))

    def delete(self, request, product_id):
        object_id = mongo_object_id(product_id)
        if object_id is None:
            return Response({"detail": "No se encontró el producto."}, status=404)
        result = get_database()["products"].update_one({"_id": object_id}, {"$set": {"active": False}})
        if result.matched_count == 0:
            return Response({"detail": "No se encontró el producto."}, status=404)
        return Response(status=204)


def cart_response(database, user_id):
    cart = database["carts"].find_one({"user_id": user_id}) or {"items": []}
    items = []
    total = 0
    for line in cart.get("items", []):
        product = database["products"].find_one({"_id": ObjectId(line["product_id"]), "active": True})
        if product is None:
            continue
        item_total = product["price"] * line["quantity"]
        total += item_total
        items.append({
            "product": public_document(product),
            "quantity": line["quantity"],
            "subtotal": item_total,
        })
    return {"items": items, "total": total}


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(cart_response(get_database(), request.user.id))

    def post(self, request):
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        database = get_database()
        product_id = ObjectId(values["product_id"])
        product = database["products"].find_one({"_id": product_id, "active": True})
        if product is None:
            return Response({"detail": "El producto no está disponible."}, status=404)
        cart = database["carts"].find_one({"user_id": request.user.id}) or {"user_id": request.user.id, "items": []}
        existing = next((line for line in cart["items"] if line["product_id"] == str(product_id)), None)
        quantity = values["quantity"] + (existing["quantity"] if existing else 0)
        if quantity > product["stock"]:
            return Response({"detail": "No hay suficiente inventario disponible."}, status=400)
        if existing:
            existing["quantity"] = quantity
        else:
            cart["items"].append({"product_id": str(product_id), "quantity": quantity})
        database["carts"].update_one(
            {"user_id": request.user.id},
            {"$set": {"items": cart["items"], "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return Response(cart_response(database, request.user.id))

    def delete(self, request):
        serializer = CartRemoveItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        database = get_database()
        database["carts"].update_one(
            {"user_id": request.user.id},
            {"$pull": {"items": {"product_id": serializer.validated_data["product_id"]}}},
        )
        return Response(cart_response(database, request.user.id))


class OrderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = get_database()["orders"].find({"user_id": request.user.id}).sort("created_at", -1).limit(100)
        return Response([public_document(order) for order in orders])

    def post(self, request):
        database = get_database()
        cart = database["carts"].find_one({"user_id": request.user.id})
        if not cart or not cart.get("items"):
            return Response({"detail": "El carrito está vacío."}, status=400)
        order_lines = []
        decremented = []
        total = 0
        for line in cart["items"]:
            product_id = ObjectId(line["product_id"])
            quantity = line["quantity"]
            result = database["products"].update_one(
                {"_id": product_id, "active": True, "stock": {"$gte": quantity}},
                {"$inc": {"stock": -quantity}},
            )
            if result.modified_count != 1:
                for reserved_id, reserved_quantity in decremented:
                    database["products"].update_one({"_id": reserved_id}, {"$inc": {"stock": reserved_quantity}})
                return Response({"detail": "Un producto ya no tiene inventario suficiente. Revisa el carrito."}, status=409)
            decremented.append((product_id, quantity))
            product = database["products"].find_one({"_id": product_id})
            subtotal = product["price"] * quantity
            total += subtotal
            order_lines.append({
                "product_id": str(product_id),
                "name": product["name"],
                "unit_price": product["price"],
                "quantity": quantity,
                "subtotal": subtotal,
            })
        order = {
            "user_id": request.user.id,
            "items": order_lines,
            "total": total,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }
        try:
            result = database["orders"].insert_one(order)
        except PyMongoError:
            for reserved_id, reserved_quantity in decremented:
                database["products"].update_one({"_id": reserved_id}, {"$inc": {"stock": reserved_quantity}})
            raise
        database["carts"].update_one({"user_id": request.user.id}, {"$set": {"items": []}})
        order["_id"] = result.inserted_id
        return Response(public_document(order), status=201)


class AdminOrderListView(APIView):
    permission_classes = [IsStoreAdmin]

    def get(self, request):
        orders = get_database()["orders"].find().sort("created_at", -1).limit(200)
        return Response([public_document(order) for order in orders])


class AdminOrderStatusView(APIView):
    permission_classes = [IsStoreAdmin]

    def patch(self, request, order_id):
        object_id = mongo_object_id(order_id)
        if object_id is None:
            return Response({"detail": "No se encontró el pedido."}, status=404)
        serializer = OrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        collection = get_database()["orders"]
        current = collection.find_one({"_id": object_id})
        if current is None:
            return Response({"detail": "No se encontró el pedido."}, status=404)
        next_status = serializer.validated_data["status"]
        if current["status"] in {"cancelled", "shipped"} and next_status != current["status"]:
            return Response({"detail": "No se puede cambiar el estado final de este pedido."}, status=409)
        if current["status"] == next_status:
            return Response(public_document(current))
        result = collection.find_one_and_update(
            {"_id": object_id, "status": current["status"]},
            {"$set": {"status": next_status, "updated_at": datetime.now(timezone.utc)}},
            return_document=True,
        )
        if result is None:
            return Response({"detail": "El pedido cambió mientras se actualizaba. Intenta de nuevo."}, status=409)
        if next_status == "cancelled":
            for item in result["items"]:
                get_database()["products"].update_one(
                    {"_id": ObjectId(item["product_id"])},
                    {"$inc": {"stock": item["quantity"]}},
                )
        return Response(public_document(result))
