import uuid

from django.db import models

from tenants.models import TenantAwareModel


class Client(TenantAwareModel):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True, default="")

    key = models.CharField(max_length=255, default=uuid.uuid4, unique=True)
    secret = models.TextField()

    class Meta:
        db_table = "client"

        unique_together = (("tenant_id", "name", "deleted"),)
