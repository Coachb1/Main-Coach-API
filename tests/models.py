from django.db import models

from tenants.models import TenantAwareModel
from tests.choices import InteractionModeChoices, TestAttemptSessionStatusChoices, TestTypeChoices
from tests.choices import QuestionTypeChoices
from tests.choices import TestQuestionResponseEvaluationStatusChoices


class Test(TenantAwareModel):
    creator_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255, db_index=True)
    description = models.CharField(max_length=255)
    interaction_mode = models.CharField(max_length=255, choices=InteractionModeChoices)
    test_type = models.CharField(max_length=255, choices=TestTypeChoices, default=TestTypeChoices.trainer)
    test_related_context = models.TextField(null=True, blank=True, default=None)
    gpt_prompt_override = models.TextField(null=True, blank=True, default=None)
    test_code = models.CharField(max_length=64, null=True)

    class Meta:
        db_table = "test"
        ordering = ("-id",)

        unique_together = (
            ("tenant_id", "test_code", "deleted"),
        )


class TestQuestion(TenantAwareModel):
    test_id = models.CharField(max_length=255, db_index=True)
    question_type = models.CharField(max_length=255, choices=QuestionTypeChoices)
    media_link = models.TextField(null=True, blank=True)
    question = models.TextField(null=True, blank=True)
    subjective_answer = models.TextField(null=True, blank=True)
    objective_answer = models.TextField(null=True, blank=True)
    mcq_options = models.JSONField(null=True, blank=True)
    mcq_answer = models.TextField(null=True, blank=True)
    gpt_prompt_override = models.TextField(null=True, blank=True, default=None)
    key_learning_point = models.TextField(null=True, blank=True, default=None)
    key_learning_skills = models.TextField(null=True, blank=True, default=None)
    flash_card_doc_id = models.TextField(null=True, blank=True, default=None)

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

    class Meta:
        db_table = "test_attempt_session"
        ordering = ("-id",)


class TestQuestionResponse(TenantAwareModel):
    test_attempt_session_id = models.CharField(max_length=255, db_index=True)
    question_id = models.CharField(max_length=255, db_index=True)
    response_file = models.TextField(null=True, blank=True)
    response_text = models.TextField(null=True, blank=True)
    evaluation_status = models.CharField(max_length=255,
                                         choices=TestQuestionResponseEvaluationStatusChoices,
                                         default=TestQuestionResponseEvaluationStatusChoices.init)

    feedback_text = models.TextField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        db_table = "test_question_response"

        unique_together = (("test_attempt_session_id", "question_id", "deleted"),)

        ordering = ("id",)
