from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from tenants.helpers import tenant_from_client
from tenants.helpers import tenant_from_request


class TenantIdentifierMiddleware(MiddlewareMixin):

    def process_request(self, request):
        request.tenant = SimpleLazyObject(lambda: tenant_from_request(request) or tenant_from_client(request.client))
