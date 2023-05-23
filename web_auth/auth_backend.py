from django.core.exceptions import PermissionDenied
from rest_framework.authentication import BaseAuthentication

from users.models import User
from web_auth.helpers import verify_access_token


class JwtAuthBackend(BaseAuthentication):

    def authenticate(self, request, **kwargs):
        auth_token = request.META.get("HTTP_AUTHORIZATION")
        if not auth_token:
            return None, None

        auth_token = auth_token.split()

        if not auth_token or len(auth_token) != 2 or auth_token[0].lower() != 'bearer':
            return None, None

        jwt_token = auth_token[1]
        if not jwt_token:
            return None, None

        decoded_token = verify_access_token(jwt_token)

        entity_type = decoded_token['entity_type']
        entity_identifier_key = decoded_token['entity_identifier_key']
        entity_identifier_value = decoded_token['entity_identifier_value']

        if entity_type == "user":
            try:
                u = User.objects.get(**{entity_identifier_key: entity_identifier_value}, deleted=0)
                return u, None
            except:
                raise PermissionDenied

        raise PermissionDenied

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response, or `None` if the
        authentication scheme should return `403 Permission Denied` responses.
        """
        return "Bearer"
