from rest_framework import serializers

from tests.choices import InteractionModeChoices, QuestionTypeChoices, TestTypeChoices, QuestionForChoices, ScenarioCaseChoices
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
    email_address_list = serializers.CharField(
        required=False, default=None, allow_null=True, allow_blank=True)
    max_test_allowed = serializers.IntegerField(
        required=False, allow_null=True, default=None)
    send_only_to_email = serializers.BooleanField(
        required=False, default=False)
    is_single_bot = serializers.BooleanField(
        required=False, default=False)
    is_checkin_type = serializers.BooleanField(
        required=False, default=False)
    is_learner_path = serializers.BooleanField(
        required=False, default=False)
    is_email_type = serializers.BooleanField(
        required=False, default=False)
    is_game_type = serializers.BooleanField(
        required=False, default=False)
    skills_to_evaluate = serializers.CharField(required=False, default=None)
    image_url = serializers.CharField(required=False, default=None, allow_null=True, allow_blank=True)
    rating = serializers.CharField(required=False, default="Not Rated", allow_null=True, allow_blank=True)
    source = serializers.CharField(required=False, default="CoachBot", allow_null=True, allow_blank=True)
    tedtalk_and_hbr_case = serializers.CharField(
        required=False, default=None, allow_null=True, allow_blank=True)

    interaction_mode = serializers.ChoiceField(choices=InteractionModeChoices)
    test_type = serializers.ChoiceField(choices=TestTypeChoices)
    scenario_case = serializers.ChoiceField(
        choices=ScenarioCaseChoices, required=False, default=None, allow_null=True, allow_blank=True)
    test_related_context = serializers.CharField(default=None)
    questions = CreateTestQuestionSerializer(many=True)
    gpt_prompt_override = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    email_candidate = serializers.BooleanField(default=True, required=False)
    candidate_type = serializers.CharField(default=None, required=False)
    orchestrated_conversation_details = OrchestratedConversationDetails(
        required=False, allow_null=True, default=None)
    description_media = serializers.CharField(
        default=None, required=False, allow_null=True, allow_blank=True)


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
                  "is_single_bot",
                  "orchestrated_conversation_details",
                  "description_media",
                  "questions",
                  "created",
                  "updated",
                  "is_checkin_type",
                  "is_learner_path",
                  "skills_to_evaluate",
                  "tedtalk_and_hbr_case",
                  "is_email_type",
                  "scenario_case",
                  "is_game_type",
                  "image_url",
                  "source",
                  "rating",
                  "is_repeat"
                  ]

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


class TestFromObjectiveSerializer(serializers.ModelSerializer):
    objective = serializers.CharField()

    class Meta:
        model = Test
        fields = ["objective"]
