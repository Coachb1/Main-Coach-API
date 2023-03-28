from django.db import models

from tenants.models import TenantAwareModel
from users.choices import UserRoleChoice


class User(TenantAwareModel):
    name = models.TextField(blank=True, null=True, default="")
    role = models.CharField(max_length=255, choices=UserRoleChoice)
    password = models.TextField(null=True)

    class Meta:
        db_table = "user"

    @property
    def can_login(self):
        return self.password is not None
