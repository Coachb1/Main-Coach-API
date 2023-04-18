from django.db import models

from documents.choices import DocTypeChoice, DocOwnerTypeChoice
from tenants.models import TenantAwareModel


class Document(TenantAwareModel):
    display_name = models.TextField()

    object_id = models.TextField()
    bucket_name = models.TextField()
    doc_type = models.CharField(max_length=255, choices=DocTypeChoice)
    content_type = models.CharField(max_length=255)
    size = models.CharField(max_length=255)
    owner_type = models.CharField(max_length=255, choices=DocOwnerTypeChoice)
    owner_id = models.CharField(max_length=255, db_index=True)

    transcript_details = models.JSONField(null=True, blank=True)

    doc_status = models.CharField(max_length=255)

    class Meta:
        db_table = "document"
        ordering = ("id",)
