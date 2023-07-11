import logging
import uuid

import jwt
from django.conf import settings
from django.db import models
from django.utils import timezone

from tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)


class RefreshToken(TenantAwareModel):
    entity_type = models.CharField(max_length=255)
    entity_identifier_key = models.CharField(max_length=255)
    entity_identifier_value = models.CharField(max_length=255, db_index=True)

    token = models.CharField(max_length=255, unique=True)
    nbf = models.DateTimeField()
    iat = models.DateTimeField()
    exp = models.DateTimeField()
    v = models.CharField(max_length=64, default=uuid.uuid4)
    is_expired = models.BooleanField(default=False)

    class Meta:
        db_table = "custom_auth_refresh_token"

    @property
    def refresh_token(self) -> str:
        return jwt.encode(
            algorithm='HS256',
            payload=dict(token=self.token,
                         nbf=self.nbf,
                         iat=self.iat,
                         exp=self.exp,
                         v=str(self.v)), key=settings.SECRET_KEY)

    @property
    def access_token(self) -> str:
        return jwt.encode(
            payload=dict(token=self.token,
                         entity_type=self.entity_type,
                         entity_identifier_key=self.entity_identifier_key,
                         entity_identifier_value=self.entity_identifier_value,
                         iat=self.iat,
                         exp=(timezone.now() + timezone.timedelta(days=1)),
                         v=str(uuid.uuid4())),
            key=settings.SECRET_KEY)

    def is_valid(self):
        if self.is_expired or self.exp < timezone.now():
            return False
        return True
