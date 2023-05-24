import logging

from django.db import transaction

from apis.accounts.dtos import IdentityCreateContextDto
from apis.accounts.dtos import UserCreateContextDto
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

    logger.info("created user account for tenant %s", tenant.uid)

    return user
