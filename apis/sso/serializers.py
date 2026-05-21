from rest_framework import serializers


class TeamsSSOTokenSerializer(serializers.Serializer):
    """
    Serializer for Teams SSO token exchange request.
    
    Accepts a bootstrap token from the Teams client and exchanges it
    for our own JWT.
    """
    teams_token = serializers.CharField(
        required=True,
        help_text="Bootstrap token from Teams JS SDK"
    )
    
    def validate_teams_token(self, value):
        if not value or len(value) < 50:
            raise serializers.ValidationError("Invalid token format")
        return value


class UserResponseSerializer(serializers.Serializer):
    """
    Serializer for user info in SSO response.
    """
    uid = serializers.CharField()
    name = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_null=True)
    role = serializers.CharField()


class TeamsSSOResponseSerializer(serializers.Serializer):
    """
    Serializer for Teams SSO token exchange response.
    
    Returns our JWT token and user information.
    """
    access_token = serializers.CharField()
    refresh_token = serializers.CharField(required=False, allow_null=True)
    user = UserResponseSerializer()
    auth_type = serializers.CharField(default='sso_login')
