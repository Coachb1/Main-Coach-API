from django.db import models

from commons.db.model import MyModel
from tenants.choices import SubscriptionChoices
from commons.cache_utils import get_cache, set_cache


class Tenant(MyModel):
    name = models.TextField()
    subdomain_prefix = models.CharField(max_length=255, unique=True)
    subscription = models.CharField(max_length=255, choices=SubscriptionChoices, default=SubscriptionChoices.paused)
    document_storage_bucket_name = models.TextField(default="")
    is_repeat = models.BooleanField(default=True, null=True, blank=True)
    logo = models.TextField(default="", null=True, blank=True)
    test_per_month = models.IntegerField(default=10, null=True, blank=True)
    mobile_number_restriction_whatsapp = models.BooleanField(default=False, null=True, blank=True)
    mobile_number_list = models.TextField(null=True,blank=True,default=None)
    web_test_code_json = models.JSONField(null=True,blank=True,default=None)
    use_skills_from_skill_bank = models.BooleanField(default=False, null=True, blank=False)

    @staticmethod
    def get_tenant_choices():
        choices = get_cache('tenant_choices')
        if not choices:
            choices = [(tenant.uid, f"{tenant.name} ({tenant.subdomain_prefix})") for tenant in Tenant.objects.all()]
            set_cache('tenant_choices', choices, timeout=3600)  # Cache for 1 hour
        return choices
    
    class Meta:
        db_table = 'tenant'

        ordering = ("-id", )


class TenantAwareModel(MyModel):
    tenant_id = models.CharField(max_length=255, db_index=True)

    class Meta:
        abstract = True
