from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from clients.helpers import get_client_from_request


class ClientIdentifierMiddleware(MiddlewareMixin):

    def process_request(self, request):
        request.client = SimpleLazyObject(lambda: get_client_from_request(request))
