from rest_framework import serializers

from tests.choices import InteractionModeChoices, QuestionTypeChoices, TestTypeChoices
from tests.models import Test, TestQuestion


class CreateTestQuestionSerializer(serializers.Serializer):
    question_type = serializers.ChoiceField(choices=QuestionTypeChoices)
    question = serializers.CharField()
    media_link = serializers.CharField(required=False)
    subjective_answer = serializers.CharField(required=False)
    objective_answer = serializers.CharField(required=False)
    mcq_options = serializers.JSONField(required=False)
    mcq_answer = serializers.CharField(required=False)


class CreateTestSerializer(serializers.Serializer):
    creator_id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    interaction_mode = serializers.ChoiceField(choices=InteractionModeChoices)
    test_type = serializers.ChoiceField(choices=TestTypeChoices)
    test_related_context = serializers.CharField(default=None)
    questions = CreateTestQuestionSerializer(many=True)


class TestQuestionDisplaySerializer(serializers.ModelSerializer):
    class Meta:
        model = TestQuestion
        fields = ["uid", "question_type", "media_link", "question", "mcq_options", "created", "updated"]


class TestDisplaySerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField(method_name="get_questions", read_only=True)

    class Meta:
        model = Test
        fields = ["uid", "title", "description", "test_related_context", "interaction_mode", "test_type", "questions", "created", "updated"]

    def get_questions(self, instance):
        return TestQuestionDisplaySerializer(instance=TestQuestion.objects.filter(test_id=instance.uid), many=True).data
