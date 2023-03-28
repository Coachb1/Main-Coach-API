from rest_framework.permissions import BasePermission


class IsAuthenticatedClient(BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        return request.client is not None and request.tenant is not None
