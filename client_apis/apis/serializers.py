from rest_framework import serializers
from django.utils import timezone
from client_apis.models import ClientAPIKey, APIKeyUsageLog


class ClientAPIKeyCreateSerializer(serializers.Serializer):
    """Used only for KEY CREATION. Returns the raw key once."""

    name            = serializers.CharField(max_length=120)
    expires_at      = serializers.DateTimeField(required=False, allow_null=True)
    rate_limit_tier = serializers.ChoiceField(
        choices=ClientAPIKey.RateLimitTier.choices,
        default=ClientAPIKey.RateLimitTier.MEDIUM,
    )
    custom_rate_limit = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    allowed_ips     = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    created_by      = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data.get("expires_at") and data["expires_at"] < timezone.now():
            raise serializers.ValidationError({"expires_at": "Expiry must be in the future."})
        if data.get("rate_limit_tier") == ClientAPIKey.RateLimitTier.CUSTOM:
            if not data.get("custom_rate_limit"):
                raise serializers.ValidationError(
                    {"custom_rate_limit": "Required when tier is 'custom'."}
                )
        return data


class ClientAPIKeyReadSerializer(serializers.ModelSerializer):
    """Safe representation — never exposes hashed_key."""

    is_expired = serializers.BooleanField(read_only=True)
    is_valid   = serializers.BooleanField(read_only=True)
    requests_per_minute = serializers.IntegerField(read_only=True)
    client_name = serializers.CharField(source="client.client_name", read_only=True)

    class Meta:
        model = ClientAPIKey
        fields = [
            "id", "client_name", "name", "prefix",
            "is_active", "is_expired", "is_valid",
            "rate_limit_tier", "custom_rate_limit", "requests_per_minute",
            "allowed_ips", "expires_at", "created", "last_used_at",
            "revoked_at", "revoke_reason", "created_by",
        ]
        read_only_fields = fields


class ClientAPIKeyCreatedSerializer(ClientAPIKeyReadSerializer):
    """Extended serializer returned ONLY at creation time — includes raw key."""

    raw_key = serializers.CharField(read_only=True)

    class Meta(ClientAPIKeyReadSerializer.Meta):
        fields = ClientAPIKeyReadSerializer.Meta.fields + ["raw_key"]


class RevokeAPIKeySerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class APIKeyUsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = APIKeyUsageLog
        fields = [
            "id", "endpoint", "method", "status_code",
            "ip_address", "response_ms", "error_message", "timestamp",
        ]