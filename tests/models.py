from django.db import models

from tenants.models import TenantAwareModel
from tests.choices import InteractionModeChoices
from tests.choices import QuestionForChoices
from tests.choices import QuestionTypeChoices
from tests.choices import TestAttemptSessionStatusChoices
from tests.choices import TestQuestionResponseEvaluationStatusChoices
from tests.choices import TestTypeChoices
from tests.choices import ScenarioCaseChoices


class Test(TenantAwareModel):
    creator_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField(null=True, blank=True, default=None)
    max_test_allowed = models.IntegerField(
        null=True, blank=True, default=None)
    interaction_mode = models.CharField(
        max_length=255, choices=InteractionModeChoices)
    test_type = models.CharField(
        max_length=255, choices=TestTypeChoices, default=TestTypeChoices.trainer)
    scenario_case = models.CharField(
        max_length=255, null=True, blank=True, choices=ScenarioCaseChoices, default=ScenarioCaseChoices.simulation)
    test_related_context = models.TextField(
        null=True, blank=True, default=None)
    gpt_prompt_override = models.TextField(null=True, blank=True, default=None)
    test_code = models.CharField(max_length=64, null=True)
    mindmap_doc_id = models.TextField(null=True, blank=True, default=None)
    flash_card_doc_id = models.TextField(null=True, blank=True, default=None)
    email_address_list = models.TextField(null=True, blank=True, default=None)
    send_only_to_email = models.BooleanField(
        default=False, null=True, blank=True)

    is_single_bot = models.BooleanField(default=False, null=True, blank=True)
    is_checkin_type = models.BooleanField(default=False, null=True, blank=True)
    is_learner_path = models.BooleanField(default=False, null=True, blank=True)
    is_email_type = models.BooleanField(default=False, null=True, blank=True)
    skills_to_evaluate = models.TextField(null=True, blank=True, default=None)
    tedtalk_and_hbr_case = models.TextField(
        null=True, blank=True, default=None)

    email_candidate = models.BooleanField(default=True, null=True, blank=True)
    candidate_type = models.CharField(
        null=True, blank=True, max_length=255, default=None)
    orchestrated_conversation_details = models.JSONField(
        null=True, blank=True, default=None)
    description_media = models.TextField(
        null=True, blank=True, default=None)

    class Meta:
        db_table = "test"
        ordering = ("-id",)

        unique_together = (
            ("tenant_id", "test_code", "deleted"),
        )


class TestQuestion(TenantAwareModel):
    test_id = models.CharField(max_length=255, db_index=True)
    question_number = models.PositiveSmallIntegerField(null=True, default=0)
    question_type = models.CharField(
        max_length=255, choices=QuestionTypeChoices)
    question_for = models.CharField(
        max_length=255, default=QuestionForChoices.user)
    media_link = models.TextField(null=True, blank=True)
    question = models.TextField(null=True, blank=True)
    can_be_skipped = models.BooleanField(default=False)
    is_view_only = models.BooleanField(default=False)
    subjective_answer = models.TextField(null=True, blank=True)
    objective_answer = models.TextField(null=True, blank=True)
    mcq_options = models.JSONField(null=True, blank=True)
    mcq_answer = models.TextField(null=True, blank=True)
    gpt_prompt_override = models.TextField(null=True, blank=True, default=None)
    key_learning_point = models.TextField(null=True, blank=True, default=None)
    key_learning_skills = models.TextField(null=True, blank=True, default=None)
    flash_card_doc_id = models.TextField(null=True, blank=True, default=None)
    loader_wait_text = models.TextField(null=True, blank=True, default=None)

    class Meta:
        db_table = "test_question"
        ordering = ("id",)


class TestInvite(TenantAwareModel):
    test_id = models.CharField(max_length=255, db_index=True)
    participant_id = models.CharField(max_length=255, db_index=True)
    expires_at = models.DateTimeField(null=True, default=None)
    is_expired = models.BooleanField(default=False)

    class Meta:
        db_table = "test_invite"


class TestAttemptSession(TenantAwareModel):
    test_id = models.CharField(max_length=255, db_index=True)
    participant_id = models.CharField(max_length=255, db_index=True)
    test_invite_id = models.CharField(max_length=255, null=True)

    expires_at = models.DateTimeField(null=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=255, choices=TestAttemptSessionStatusChoices,
                              default=TestAttemptSessionStatusChoices.in_progress)

    feedback_text = models.TextField(null=True, blank=True)
    report_doc_id = models.TextField(
        null=True, blank=True, default=None)
    skills_rating = models.JSONField(null=True, blank=True, default=None)
    test_score = models.FloatField(null=True, blank=True, default=None)
    avg_score = models.FloatField(null=True, blank=True, default=None)
    speech_score = models.JSONField(null=True, blank=True, default=None)
    culture_skills_rating = models.JSONField(
        null=True, blank=True, default=None)

    meeting_summary = models.TextField(null=True, blank=True, default=None)
    areas_of_improvement = models.TextField(
        null=True, blank=True, default=None)

    current_question_idx = models.IntegerField(
        null=True, blank=True, default=-1)
    next_question_idx = models.IntegerField(null=True, blank=True, default=1)

    report_url = models.TextField(null=True, blank=True, default=None)
    is_report_sent_to_whatsapp = models.BooleanField(
        null=True, blank=True, default=None)
    is_report_sent_to_email = models.BooleanField(
        null=True, blank=True, default=None)

    is_checkin_type = models.BooleanField(default=False, null=True, blank=True)

    class Meta:
        db_table = "test_attempt_session"
        ordering = ("-id",)
        indexes = [
            models.Index(fields=["tenant_id", "test_id", "test_score"]),
        ]


class TestQuestionResponse(TenantAwareModel):
    test_attempt_session_id = models.CharField(max_length=255, db_index=True)
    question_id = models.CharField(max_length=255, db_index=True)
    responder_type = models.CharField(
        max_length=255, default=QuestionForChoices.user)
    responder_display_name = models.TextField(
        null=True, blank=True, default=None)
    response_file = models.TextField(null=True, blank=True)
    response_text = models.TextField(null=True, blank=True)
    evaluation_status = models.CharField(max_length=255,
                                         choices=TestQuestionResponseEvaluationStatusChoices,
                                         default=TestQuestionResponseEvaluationStatusChoices.init)

    feedback_text = models.TextField(null=True, blank=True)
    skills_rating = models.JSONField(null=True, blank=True, default=None)
    avg_score = models.FloatField(null=True, blank=True, default=None)
    speech_metrics = models.JSONField(null=True, blank=True, default=None)
    metadata = models.JSONField(null=True, blank=True, default=None)
    relevance = models.BooleanField(null=True, blank=True, default=True )
    class Meta:
        db_table = "test_question_response"

        unique_together = (
            ("test_attempt_session_id", "question_id", "deleted"),)

        ordering = ("id",)
