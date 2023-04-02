from rest_framework import serializers

from tests.models import TestInvite


class TestInviteCreateSerializer(serializers.Serializer):
    test_id = serializers.CharField()
    participant_id = serializers.CharField()
    expires_at = serializers.DateTimeField()


class TestInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestInvite
        fields = ["uid", "test_id", "participant_id", "expires_at", "is_expired", "created", "updated"]
