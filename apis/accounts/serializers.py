from rest_framework import serializers

from users.choices import UserRoleChoice
from users.models import User


class UserAttributesUserContextSerializer(serializers.Serializer):
    tag = serializers.CharField()
    attributes = serializers.JSONField()


class SetupAccountUserContextSerializer(serializers.Serializer):
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=UserRoleChoice)
    password = serializers.CharField(required=False, default=None)
    user_attributes = UserAttributesUserContextSerializer(required=False)


class SetupAccountIdentityContextSerializer(serializers.Serializer):
    identity_type = serializers.CharField()
    value = serializers.CharField()


class SetupAccountSerializer(serializers.Serializer):
    user_context = SetupAccountUserContextSerializer()
    identity_context = SetupAccountIdentityContextSerializer()


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["uid", "name", "role", "created", "updated"]
