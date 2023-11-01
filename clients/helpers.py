import logging
import uuid

from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from clients.client_auth_backend import ClientBasicAuthentication
from clients.models import Client
from commons.timeit import timeit
from tenants.models import Tenant

logger = logging.getLogger(__name__)


@timeit
def setup_client(tenant_id: str,
                 name: str,
                 description: str) -> tuple[Client, str]:
    """
    Creates or updates a client object in the database based on the provided inputs.

    Args:
        tenant_id (str): The ID of the tenant for which the client is being created or updated.
        name (str): The name of the client.
        description (str): The description of the client.

    Returns:
        tuple[Client, str]: The created or updated client object and a randomly generated secret key.

    Raises:
        serializers.ValidationError: If the provided tenant ID is invalid.

    Example Usage:
        client, secret = setup_client(tenant_id="123", name="Client 1", description="This is a client")

    Code Analysis:
        - Generate a random secret key using the `uuid.uuid4()` function.
        - Check if a tenant with the provided `tenant_id` exists in the database. If not, raise a validation error.
        - Use the `get_or_create()` method to either retrieve an existing client object or create a new one with the provided `tenant_id` and `name`.
        - If the client is created, log a message and return the client object and the secret key.
        - If the client already exists, update its `secret` and `description` fields with the generated secret key and the provided description (if any), respectively. Save the changes to the database and log a message. Then, return the client object and the secret key.
    """
    secret = str(uuid.uuid4())

    if not Tenant.objects.filter(uid=tenant_id, deleted=0).exists():
        raise serializers.ValidationError("invalid tenant id")

    client, is_created = Client.objects.get_or_create(
        tenant_id=tenant_id,
        name=name,
        defaults=dict(
            description=description,
            secret=make_password(secret)
        )
    )

    if is_created:
        logger.info("client created for tenant %s", tenant_id)
    else:
        client.secret = make_password(secret)
        client.description = description or client.description
        client.save()

        logger.info("client updated for tenant %s", tenant_id)

    return client, secret


def get_client_from_request(request):
    client, _ = ClientBasicAuthentication().authenticate(request)
    return client
