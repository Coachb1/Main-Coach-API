from rest_framework import serializers

from identities.helpers import get_user_identities
from identities.serializers import IdentityUserViewSerializer
from users.choices import UserRoleChoice
from users.models import User


class SetupAccountUserContextSerializer(serializers.Serializer):
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=UserRoleChoice)
    password = serializers.CharField(required=False, default=None)


class SetupAccountIdentityContextSerializer(serializers.Serializer):
    identity_type = serializers.CharField()
    value = serializers.CharField()


class SetupAccountSerializer(serializers.Serializer):
    user_context = SetupAccountUserContextSerializer()
    identity_context = SetupAccountIdentityContextSerializer()


class AccountSerializer(serializers.ModelSerializer):
    identities = serializers.SerializerMethodField(method_name="get_identities")

    class Meta:
        model = User
        fields = ["uid", "name", "identities", "created", "updated"]

    def get_identities(self, instance: User):
        return IdentityUserViewSerializer(instance=get_user_identities(instance.uid), many=True).data
