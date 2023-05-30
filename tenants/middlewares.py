from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from tenants.helpers import tenant_from_client, tenant_from_user


class TenantIdentifierMiddleware(MiddlewareMixin):

    def process_request(self, request):
        request.tenant = SimpleLazyObject(
            lambda: get_tenant(request)
        )


def get_tenant(request):
    return tenant_from_client(request.client) or tenant_from_user(request.auth_user)
