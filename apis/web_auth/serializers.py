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


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset using secret code."""
    subdomain_prefix = serializers.CharField()
    identity_context = IdentityContextSerializer()
    secret_code = serializers.CharField()
    new_password = serializers.CharField()
    
    def validate_new_password(self, value):
        """Validate the new password."""
        if len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters long.")
        return value