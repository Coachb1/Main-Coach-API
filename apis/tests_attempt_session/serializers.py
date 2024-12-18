from rest_framework import serializers

from tests.models import TestAttemptSession, TestQuestionResponse


class TestAttemptSessionSerializer(serializers.ModelSerializer):
    is_signature_bot = serializers.BooleanField(default=False,required=False)
    is_idp_discussion_opted = serializers.BooleanField(default=False,required=False)
    class Meta:
        model = TestAttemptSession
        fields = ["uid", "test_id", "participant_id", "test_invite_id", "expires_at", "started_at", "finished_at",
                    "skills_rating", "current_question_idx", "next_question_idx", "test_score", "created", "updated",
                    "status", "is_signature_bot", "is_idp_discussion_opted"]

    def to_representation(self, instance:TestAttemptSession):
        data = super().to_representation(instance)

        que_response = TestQuestionResponse.objects.filter(
                                        test_attempt_session_id=instance.uid,
                                        deleted=False
                                    ).last()
        if que_response:
            data['next_question_text'] = que_response.question_text
        return data
        