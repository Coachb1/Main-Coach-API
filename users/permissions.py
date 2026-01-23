from rest_framework.permissions import BasePermission


class IsAuthenticatedUser(BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        return request.auth_user is not None and request.tenant is not None


class IsAuthenticatedRootUser(BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        return request.auth_user is not None and request.auth_user.is_root


class IsSuperAdmin(BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        return request.auth_user is not None and request.auth_user.role == "super_admin"