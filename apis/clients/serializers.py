from rest_framework import serializers

from clients.models import Client


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["uid", "name", "key", "description", "deleted", "created", "updated"]


class SetupClientSerializer(serializers.Serializer):
    tenant_id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(default="", required=False)
