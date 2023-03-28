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
