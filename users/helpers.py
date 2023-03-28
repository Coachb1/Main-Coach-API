import logging

from django.contrib.auth.hashers import make_password

from tenants.models import Tenant
from users.models import User

logger = logging.getLogger(__name__)


def create_user(tenant: Tenant,
                name: str,
                role: str,
                password: str) -> User:
    user = User.objects.create(
        tenant_id=tenant.uid,
        name=name,
        role=role,
        password=make_password(password) if password else None
    )

    logger.info("created user for tenant %s", tenant.uid)

    return user
