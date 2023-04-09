from rest_framework import serializers

from tests.models import TestQuestionResponse


class TestQuestionResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestQuestionResponse
        fields = ["uid", "test_attempt_session_id", "question_id", "response_file", "response_text", "feedback_text",
                  "evaluation_status", "created", "updated"]
