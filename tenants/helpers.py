from clients.models import Client
from tenants.models import Tenant


def hostname_from_request(request) -> str:
    return request.get_host().split(':')[0].lower()


def tenant_from_request(request):
    hostname = hostname_from_request(request)
    subdomain_prefix = hostname.split('.')[0]
    return Tenant.objects.filter(subdomain_prefix=subdomain_prefix, deleted=0).first()


def tenant_from_client(client: Client) -> Tenant:
    if client:
        return Tenant.objects.get(uid=client.tenant_id, deleted=0)


def tenant_from_tenant_id(tenant_id) -> Tenant:
    return Tenant.objects.get(uid=tenant_id, deleted=0)


def tenant_from_subdomain_prefix(subdomain_prefix) -> Tenant:
    return Tenant.objects.get(subdomain_prefix=subdomain_prefix, deleted=0)
