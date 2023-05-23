from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from web_auth.auth_backend import JwtAuthBackend


class UserAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.user = SimpleLazyObject(lambda: get_user(request))


def get_user(request):
    item, _ = JwtAuthBackend.authenticate(None, request)
    return item
