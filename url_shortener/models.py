from django.db import models
from tenants.models import TenantAwareModel


class UrlShortenerMap(TenantAwareModel):
    long_url_hash = models.CharField(max_length=255)
    long_url = models.TextField()
    short_url = models.CharField(max_length=255)

    class Meta:
        db_table = "url_shortener_map"
        unique_together = ("long_url_hash", "tenant_id", "deleted")
