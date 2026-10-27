from rest_framework.permissions import BasePermission


class IsStoreAdmin(BasePermission):
    message = "Se requiere una cuenta administradora de TechGear."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")
