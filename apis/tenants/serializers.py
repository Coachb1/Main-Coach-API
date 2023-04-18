from rest_framework import serializers

from tenants.models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["uid", "name", "subdomain_prefix", "document_storage_bucket_name", "subscription", "deleted",
                  "created", "updated"]
