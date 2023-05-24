import uuid

import jwt
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.exceptions import PermissionDenied

from web_auth.models import RefreshToken


def create_new_tokens(entity_type: str,
                      entity_identifier_key: str,
                      entity_identifier_value: str) -> dict:
    # validate password
    # then create tokens

    now = timezone.now()
    random_token = str(uuid.uuid4())

    token, created = RefreshToken.objects.get_or_create(
        entity_type=entity_type,
        entity_identifier_key=entity_identifier_key,
        entity_identifier_value=entity_identifier_value,
        defaults=dict(
            token=random_token,
            nbf=now,
            iat=now,
            exp=now + timezone.timedelta(days=30)
        ))

    if not created:
        token.token = random_token
        token.nbf = now
        token.iat = now
        token.exp = now + timezone.timedelta(days=30)
        token.save()

    return {"refresh": token.refresh_token, "access": token.access_token}


def verify_refresh_token(jwt_token) -> RefreshToken:
    try:
        decoded = jwt.decode(jwt=jwt_token, key=settings.SECRET_KEY, algorithms=["HS256"], )
    except:
        raise PermissionDenied

    token = decoded["token"]
    token_obj = RefreshToken.objects.get(token=token)

    if not token_obj.is_valid():
        raise PermissionDenied

    return token_obj


def verify_access_token(jwt_token):
    try:
        decoded = jwt.decode(jwt=jwt_token, key=settings.SECRET_KEY, algorithms=["HS256"])
    except:
        raise AuthenticationFailed

    token = decoded["token"]

    token_obj = RefreshToken.objects.get(token=token)
    if not token_obj.is_valid():
        raise AuthenticationFailed

    return decoded


def get_new_access_token(refresh_token):
    token_obj = verify_refresh_token(refresh_token)
    return {"access": token_obj.access_token}


def logout_entity(entity_type: str,
                  entity_identifier_key: str,
                  entity_identifier_value: str):
    RefreshToken.objects.filter(entity_type=entity_type,
                                entity_identifier_key=entity_identifier_key,
                                entity_identifier_value=entity_identifier_value,
                                is_expired=False).update(is_expired=True)
    return True
