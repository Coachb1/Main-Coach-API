from django.db import models

from commons.db.model import MyModel
from tenants.choices import SubscriptionChoices


class Tenant(MyModel):
    name = models.TextField()
    subdomain_prefix = models.CharField(max_length=255, unique=True)
    subscription = models.CharField(max_length=255, choices=SubscriptionChoices, default=SubscriptionChoices.paused)
    document_storage_bucket_name = models.TextField(default="")
    is_repeat = models.BooleanField(default=True, null=True, blank=True)
    logo = models.TextField(default="", null=True, blank=True)

    class Meta:
        db_table = 'tenant'

        ordering = ("-id", )


class TenantAwareModel(MyModel):
    tenant_id = models.CharField(max_length=255, db_index=True)

    class Meta:
        abstract = True
