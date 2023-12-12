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
    """
    Creates a new identity object in the database.

    Args:
        tenant (Tenant): The tenant object for which the identity is being created.
        user (User): The user object for whom the identity is being created.
        identity_type (str): The type of identity being created (e.g., email, phone number).
        value (str): The value of the identity (e.g., email address, phone number).

    Returns:
        Identity: The newly created Identity object.
    """
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
    """
    Retrieves a user object based on the given tenant, identity type, and identity value.

    Args:
        tenant (Tenant): The tenant object representing the user's organization.
        identity_type (str): The type of identity to search for (e.g., email, username).
        identity_value (str): The value of the identity to search for (e.g., example@example.com, johndoe).

    Returns:
        User: The user object corresponding to the given tenant, identity type, and identity value.
    """
    try:
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
    except Exception as e:
        logger.info({"!!!!ERROR": e}, exc_info=True)

    return user
