from rest_framework import serializers

from apis.tests.serializers import TestQuestionDisplaySerializer
from tests.models import TestQuestionResponse, TestQuestion


class TestQuestionResponseSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField(method_name="get_question", read_only=True)
    question_id = serializers.CharField(write_only=True)

    class Meta:
        model = TestQuestionResponse
        fields = ["uid",
                  "test_attempt_session_id",
                  "question_id",
                  "question",
                  "responder_type",
                  "responder_display_name",
                  "response_file",
                  "response_text",
                  "feedback_text",
                  "metadata",
                  "evaluation_status",
                  "question_text",
                  "created",
                  "updated"]

    def get_question(self, instance):
        return TestQuestionDisplaySerializer(instance=TestQuestion.objects.filter(uid=instance.question_id).last(), many=False).data
