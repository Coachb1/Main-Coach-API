from django.db import models

from tenants.models import TenantAwareModel


class Identity(TenantAwareModel):
    user_id = models.CharField(max_length=255, db_index=True)
    identity_type = models.CharField(max_length=255)
    value = models.CharField(max_length=255)

    class Meta:
        db_table = "identity"

        unique_together = (
            ("tenant_id", "value", "deleted"),
        )
