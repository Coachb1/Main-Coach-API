from rest_framework import serializers


class IdentityContextSerializer(serializers.Serializer):
    identity_type = serializers.CharField()
    value = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    subdomain_prefix = serializers.CharField()
    identity_context = IdentityContextSerializer()
    password = serializers.CharField()
    client_id = serializers.CharField(
            required=False,
            allow_blank=True
        )