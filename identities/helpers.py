import logging

from identities.models import Identity
from tenants.models import Tenant
from users.models import User

logger = logging.getLogger(__name__)


def get_user_identities(user_id):
    return Identity.objects.filter(user_id=user_id, deleted=0)


def create_identity(tenant: Tenant,
                    user: User,
                    identity_type: str,
                    value: str):
    identity = Identity.objects.create(
        user_id=user.uid,
        identity_type=identity_type,
        value=value
    )

    logger.info("created identity for tenant %s", tenant.uid)

    return identity
