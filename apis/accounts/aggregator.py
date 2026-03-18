import logging

from django.db import transaction

from apis.accounts.dtos import IdentityCreateContextDto
from apis.accounts.dtos import UserCreateContextDto
from coaching_conversations.helpers import create_or_assign_client_id
from commons.timeit import timeit
from identities.helpers import create_identity
from tenants.models import Tenant
from users.helpers import create_user
from users.helpers import upsert_user_attributes

logger = logging.getLogger(__name__)


@timeit
def create_user_account(tenant: Tenant,
                        user_context: UserCreateContextDto,
                        identity_context: IdentityCreateContextDto):
    """
    Creates a new user account by calling the `create_user` and `create_identity` functions.
    Updates or inserts user attributes using the `upsert_user_attributes` function.
    Logs the execution time of the function using the `timeit` decorator.

    Args:
        tenant (Tenant): The tenant object for which the user account is being created.
        user_context (UserCreateContextDto): The user context containing the user details such as name, role, password, and user attributes.
        identity_context (IdentityCreateContextDto): The identity context containing the identity details such as identity type and value.

    Returns:
        User: The newly created user object.
    """
    with transaction.atomic():
        user = create_user(tenant=tenant,
                           name=user_context.name,
                           role=user_context.role,
                           password=user_context.password)
        identity = create_identity(tenant=tenant,
                                   user=user,
                                   identity_type=identity_context.identity_type,
                                   value=identity_context.value)
        if user_context.user_attributes:
            tag = user_context.user_attributes.get("tag")
            attributes = user_context.user_attributes.get("attributes")

            user_attribute = upsert_user_attributes(user=user,
                                                    tag=tag,
                                                    attributes=attributes)
            
        create_or_assign_client_id(user.get_email(),tenant)


    logger.info("created user account for tenant %s", tenant.uid)

    return user
