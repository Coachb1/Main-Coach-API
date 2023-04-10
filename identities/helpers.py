import logging

from identities.models import Identity
from tenants.models import Tenant
from users.models import User

logger = logging.getLogger(__name__)


def get_user_identities(user: User):
    return Identity.objects.filter(tenant_id=user.tenant_id, user_id=user.uid, deleted=0)


def create_identity(tenant: Tenant,
                    user: User,
                    identity_type: str,
                    value: str):
    identity = Identity.objects.create(
        tenant_id=tenant.uid,
        user_id=user.uid,
        identity_type=identity_type,
        value=value
    )

    logger.info("created identity for tenant %s", tenant.uid)

    return identity


def get_user_via_identity(tenant: Tenant,
                          identity_type: str,
                          identity_value: str) -> User:
    identity = Identity.objects.get(
        tenant_id=tenant.uid,
        identity_type=identity_type,
        value=identity_value,
        deleted=0
    )

    user = User.objects.get(
        tenant_id=tenant.uid,
        uid=identity.user_id,
        deleted=0
    )

    return user
