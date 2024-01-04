from rest_framework import serializers

from tests.models import TestAttemptSession


class TestAttemptSessionSerializer(serializers.ModelSerializer):
    is_signature_bot = serializers.BooleanField(default=False,required=False)
    class Meta:
        model = TestAttemptSession
        fields = ["uid", "test_id", "participant_id", "test_invite_id", "expires_at", "started_at", "finished_at",
                  "skills_rating", "current_question_idx", "next_question_idx", "test_score", "created", "updated", "status", "is_signature_bot"]
