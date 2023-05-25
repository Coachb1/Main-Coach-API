import logging

from django.contrib.auth.hashers import make_password, check_password

from identities.helpers import get_user_via_identity
from tenants.models import Tenant
from users.models import User
from users.models import UserAttribute
from web_auth.helpers import create_new_tokens, logout_entity

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


def login_user(tenant: Tenant,
               identity_type: str,
               identity_value: str,
               password: str) -> dict:
    try:
        user = get_user_via_identity(
            tenant=tenant,
            identity_type=identity_type,
            identity_value=identity_value
        )
    except Exception as e:
        logger.exception("user get failed err: %s", e)
        raise ValueError("invalid credentials")

    if not user.can_login:
        logger.exception("user cannot login")
        raise ValueError("invalid credentials")

    if not check_password(password, user.password):
        raise ValueError("invalid credentials")

    return create_new_tokens(
        entity_type="user",
        entity_identifier_key="uid",
        entity_identifier_value=user.uid
    )


def logout_user(user: User):
    logout_entity(
        entity_type="user",
        entity_identifier_key="uid",
        entity_identifier_value=user.uid
    )


def upsert_user_attributes(user: User, tag: str, attributes: dict) -> UserAttribute:
    if not attributes:
        return

    user_attribute, created = UserAttribute.objects.get_or_create(
        tenant_id=user.tenant_id,
        user_id=user.uid,
        tag=tag
    )

    updated_attributes = user_attribute.attributes or {}
    updated_attributes.update(attributes)
    user_attribute.attributes = updated_attributes
    user_attribute.save()
    return user_attribute


def get_user_skills_report_attribute(user: User) -> UserAttribute:
    return UserAttribute.objects.filter(
        tenant_id=user.tenant_id,
        user_id=user.uid,
        tag="skills_report"
    ).last()
