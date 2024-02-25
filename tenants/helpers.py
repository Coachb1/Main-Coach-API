from clients.models import Client
from tenants.models import Tenant
from users.models import User


def hostname_from_request(request) -> str:
    """
    Extracts the hostname from the given request.

    This function takes a request object as input and returns the hostname part of the request's host, converted to lowercase.

    Args:
        request: A Django HttpRequest object.

    Returns:
        A string representing the hostname part of the request's host.

    Example:
        >>> hostname_from_request(request)
        'example.com'
    """

    return request.get_host().split(':')[0].lower()

def tenant_from_request(request):
    """
    Retrieves the Tenant object associated with the subdomain prefix in the request's hostname.

    This function extracts the hostname from the request, takes the subdomain prefix, and queries the Tenant model to find a matching, non-deleted Tenant.

    Args:
        request: A Django HttpRequest object.

    Returns:
        A Tenant object if a match is found, otherwise None.

    Example:
        >>> tenant_from_request(request)
        <Tenant: Tenant object (1)>
    """
    hostname = hostname_from_request(request)
    subdomain_prefix = hostname.split('.')[0]
    return Tenant.objects.filter(subdomain_prefix=subdomain_prefix, deleted=0).first()


def tenant_from_client(client: Client) -> Tenant:
    """
    Retrieves the Tenant object associated with the given Client.

    This function takes a Client object, uses its tenant_id attribute to query the Tenant model, and returns the corresponding, non-deleted Tenant.

    Args:
        client: A Client object.

    Returns:
        A Tenant object if a match is found, otherwise None.

    Example:
        >>> tenant_from_client(client)
        <Tenant: Tenant object (1)>
    """
    if client:
        return Tenant.objects.get(uid=client.tenant_id, deleted=0)


def tenant_from_user(user: User) -> Tenant:
    """
    Retrieves the Tenant object associated with the given User.

    This function takes a User object, uses its tenant_id attribute to query the Tenant model, and returns the corresponding, non-deleted Tenant.

    Args:
        user: A User object.

    Returns:
        A Tenant object if a match is found, otherwise None.

    Example:
        >>> tenant_from_user(user)
        <Tenant: Tenant object (1)>
    """
    if user:
        return Tenant.objects.get(uid=user.tenant_id, deleted=0)


def tenant_from_tenant_id(tenant_id) -> Tenant:
    """
    Retrieves the Tenant object associated with the given tenant_id.

    This function takes a tenant_id, queries the Tenant model, and returns the corresponding, non-deleted Tenant.

    Args:
        tenant_id: A string or integer representing the tenant_id.

    Returns:
        A Tenant object if a match is found, otherwise None.

    Example:
        >>> tenant_from_tenant_id('1')
        <Tenant: Tenant object (1)>
    """
    return Tenant.objects.get(uid=tenant_id, deleted=0)


def tenant_from_subdomain_prefix(subdomain_prefix) -> Tenant:
    """
    Retrieves the Tenant object associated with the given subdomain prefix.

    This function takes a subdomain prefix, queries the Tenant model, and returns the corresponding, non-deleted Tenant.

    Args:
        subdomain_prefix: A string representing the subdomain prefix.

    Returns:
        A Tenant object if a match is found, otherwise None.

    Example:
        >>> tenant_from_subdomain_prefix('example')
        <Tenant: Tenant object (1)>
    """
    return Tenant.objects.get(subdomain_prefix=subdomain_prefix, deleted=0)
