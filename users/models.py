from django.db import models

from tenants.models import TenantAwareModel
from users.choices import UserRoleChoice


class User(TenantAwareModel):
    name = models.TextField(blank=True, null=True, default="")
    role = models.CharField(max_length=255, choices=UserRoleChoice)
    password = models.TextField(null=True)
    is_root = models.BooleanField(null=True, default=None)

    class Meta:
        db_table = "user"
        ordering = ("-id",)

    @property
    def can_login(self):
        return self.password is not None

    @property
    def is_active(self):
        return self.can_login


class UserAttribute(TenantAwareModel):
    user_id = models.CharField(max_length=255)
    tag = models.CharField(max_length=255)
    attributes = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        db_table = "user_attribute"

        unique_together = (("tenant_id", "user_id", "tag"),)
