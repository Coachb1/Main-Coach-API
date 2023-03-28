from rest_framework import serializers

from identities.models import Identity


class IdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Identity
        fields = ["user_id", "identity_type", "value", "created", "updated"]


class IdentityUserViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Identity
        fields = ["identity_type", "value"]
