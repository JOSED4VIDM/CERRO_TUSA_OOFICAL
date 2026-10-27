import re

from bson import ObjectId
from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=120, trim_whitespace=True)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=12, max_length=128, write_only=True, trim_whitespace=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=1, max_length=128, write_only=True, trim_whitespace=False)


class CategorySerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(min_length=2, max_length=80)
    slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    description = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    active = serializers.BooleanField(required=False, default=True)


class ProductSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(min_length=2, max_length=160)
    slug = serializers.RegexField(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    description = serializers.CharField(max_length=4000, allow_blank=True, required=False, default="")
    price = serializers.IntegerField(min_value=0, max_value=2_000_000_000)
    stock = serializers.IntegerField(min_value=0, max_value=1_000_000)
    category_id = serializers.CharField(max_length=24)
    image_url = serializers.URLField(max_length=1000, allow_blank=True, required=False, default="")
    active = serializers.BooleanField(required=False, default=True)

    def validate_category_id(self, value):
        if not ObjectId.is_valid(value):
            raise serializers.ValidationError("La categoría no es válida.")
        return value

    def validate_image_url(self, value):
        if value and not re.match(r"^https://", value, re.IGNORECASE):
            raise serializers.ValidationError("La URL de imagen debe usar HTTPS.")
        return value


class CartItemSerializer(serializers.Serializer):
    product_id = serializers.CharField(max_length=24)
    quantity = serializers.IntegerField(min_value=1, max_value=99)

    def validate_product_id(self, value):
        if not ObjectId.is_valid(value):
            raise serializers.ValidationError("El producto no es válido.")
        return value


class CartRemoveItemSerializer(serializers.Serializer):
    product_id = serializers.CharField(max_length=24)

    def validate_product_id(self, value):
        if not ObjectId.is_valid(value):
            raise serializers.ValidationError("El producto no es válido.")
        return value


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["pending", "paid", "shipped", "cancelled"])
