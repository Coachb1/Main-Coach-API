from django.db import models

from tenants.models import TenantAwareModel
from tests.choices import InteractionModeChoices


class Test(TenantAwareModel):
    title = models.CharField(max_length=255, db_index=True)
    interaction_mode = models.CharField(max_length=255, choices=InteractionModeChoices)
    track = models.CharField(max_length=255, db_index=True)

    class Meta:
        db_table = "test"
