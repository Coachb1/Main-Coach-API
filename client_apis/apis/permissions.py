from rest_framework.permissions import BasePermission


class HasValidAPIKey(BasePermission):
    """
    Allows access only to requests authenticated with a valid ClientAPIKey.
    Attach this alongside APIKeyAuthentication.
    """

    message = "A valid API key is required."

    def has_permission(self, request, view):
        # request.auth is the ClientAPIKey instance (set by APIKeyAuthentication)
        from client_apis.models import ClientAPIKey
        return isinstance(request.auth, ClientAPIKey) and request.auth.is_valid


class IsActiveClient(BasePermission):
    """Ensures the linked ClientUserInfo is still active."""

    message = "Your client account is inactive."

    def has_permission(self, request, view):
        client = request.user
        if not client:
            return False
        return getattr(client, "is_active", False)