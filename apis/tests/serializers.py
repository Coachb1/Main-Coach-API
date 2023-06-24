from rest_framework import serializers

from tests.choices import InteractionModeChoices, QuestionTypeChoices, TestTypeChoices, QuestionForChoices
from tests.models import Test, TestQuestion


class CreateTestQuestionSerializer(serializers.Serializer):
    question_type = serializers.ChoiceField(choices=QuestionTypeChoices)
    question_for = serializers.CharField(default=QuestionForChoices.user)
    question = serializers.CharField()
    question_number = serializers.IntegerField(default=0)
    can_be_skipped = serializers.BooleanField(default=False)
    is_view_only = serializers.BooleanField(default=False)
    loader_wait_text = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, default=""
    )
    media_link = serializers.CharField(required=False)
    gpt_prompt_override = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    subjective_answer = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    objective_answer = serializers.CharField(required=False)
    mcq_options = serializers.JSONField(required=False)
    mcq_answer = serializers.CharField(required=False)
    key_learning_point = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    key_learning_skills = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)


class OrchestratedConversationDetails(serializers.Serializer):
    test_main_context = serializers.CharField()
    test_user_persona = serializers.CharField()
    objective = serializers.CharField()
    initial_messages = serializers.ListField(
        child=serializers.CharField()
    )


class CreateTestSerializer(serializers.Serializer):
    creator_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    title = serializers.CharField()
    description = serializers.CharField()
    email_address_list = serializers.CharField(required=False, default=None)
    send_only_to_email = serializers.BooleanField(
        required=False, default=False)
    interaction_mode = serializers.ChoiceField(choices=InteractionModeChoices)
    test_type = serializers.ChoiceField(choices=TestTypeChoices)
    test_related_context = serializers.CharField(default=None)
    questions = CreateTestQuestionSerializer(many=True)
    gpt_prompt_override = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    email_candidate = serializers.BooleanField(default=True, required=False)
    candidate_type = serializers.CharField(default=None, required=False)
    orchestrated_conversation_details = OrchestratedConversationDetails(
        required=False, allow_null=True)


class TestQuestionDisplaySerializer(serializers.ModelSerializer):
    class Meta:
        model = TestQuestion
        fields = ["uid",
                  "question_type",
                  "media_link",
                  "question_for",
                  "question",
                  "question_number",
                  "key_learning_point",
                  "key_learning_skills",
                  "gpt_prompt_override",
                  "mcq_options",
                  "created",
                  "updated"]


class TestDisplaySerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField(
        method_name="get_questions", read_only=True)

    class Meta:
        model = Test
        fields = ["uid",
                  "test_code",
                  "title",
                  "description",
                  "email_address_list",
                  "send_only_to_email",
                  "email_candidate",
                  "candidate_type",
                  "gpt_prompt_override",
                  "test_related_context",
                  "interaction_mode",
                  "test_type",
                  "orchestrated_conversation_details",
                  "questions",
                  "created",
                  "updated"]

    def get_questions(self, instance):
        return TestQuestionDisplaySerializer(instance=TestQuestion.objects.filter(test_id=instance.uid), many=True).data


class LearnerPathSerializer(serializers.ModelSerializer):
    objective = serializers.CharField()
    candidate_type = serializers.CharField(default=None, required=False)
    candidate_id = serializers.CharField()

    class Meta:
        model = Test
        fields = ["objective",
                  "candidate_type",
                  "candidate_id",
                  "created",
                  "updated"]
