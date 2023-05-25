from rest_framework import serializers

from tests.models import TestAttemptSession


class TestAttemptSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestAttemptSession
        fields = ["uid", "test_id", "participant_id", "test_invite_id", "expires_at", "started_at", "finished_at",
                  "skills_rating", "test_score", "created", "updated"]
