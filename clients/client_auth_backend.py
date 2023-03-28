import base64
import binascii

from django.contrib.auth.hashers import check_password
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.authentication import get_authorization_header

from clients.models import Client


class ClientBasicAuthentication(BaseAuthentication):
    """
    HTTP Basic authentication against key/secret.
    """
    www_authenticate_realm = 'api'

    def authenticate(self, request) -> tuple[Client, None]:
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'basic':
            return None, None

        if len(auth) == 1:
            msg = 'No credentials provided.'
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = 'Credentials string should not contain spaces.'
            raise exceptions.AuthenticationFailed(msg)

        try:
            try:
                auth_decoded = base64.b64decode(auth[1]).decode('utf-8')
            except UnicodeDecodeError:
                auth_decoded = base64.b64decode(auth[1]).decode('latin-1')
            auth_parts = auth_decoded.partition(':')
        except (TypeError, UnicodeDecodeError, binascii.Error):
            msg = 'Credentials not correctly base64 encoded.'
            raise exceptions.AuthenticationFailed(msg)

        key, secret = auth_parts[0], auth_parts[2]

        return self.authenticate_credentials(key, secret, request)

    def authenticate_credentials(self, key, secret, request=None) -> tuple[Client, None]:
        try:
            client = Client.objects.get(key=key, deleted=0)
        except:
            raise exceptions.AuthenticationFailed("Invalid credentials")

        if not check_password(secret, client.secret):
            raise exceptions.AuthenticationFailed("Invalid credentials")

        return client, None

    def authenticate_header(self, request):
        return 'Basic realm="%s"' % self.www_authenticate_realm
