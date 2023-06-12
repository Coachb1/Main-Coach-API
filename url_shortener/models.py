from django.db import models
from tenants.models import TenantAwareModel


class UrlShortenerMap(TenantAwareModel):
    long_url_hash = models.CharField(max_length=300)
    long_url = models.CharField(max_length=500)
    short_url = models.CharField(max_length=100)

    class Meta:
        db_table = "url_shortener_map"
        unique_together = ("long_url_hash", "tenant_id", "deleted")
