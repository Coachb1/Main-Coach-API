from django.db import models

from tenants.models import TenantAwareModel
from tests.choices import InteractionModeChoices, TestAttemptSessionStatusChoices
from tests.choices import QuestionTypeChoices
from tests.choices import TestQuestionResponseEvaluationStatusChoices


class Test(TenantAwareModel):
    creator_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255, db_index=True)
    description = models.CharField(max_length=255)
    interaction_mode = models.CharField(max_length=255, choices=InteractionModeChoices)
    is_trainer_mode_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = "test"


class TestQuestion(TenantAwareModel):
    test_id = models.CharField(max_length=255, db_index=True)
    question_type = models.CharField(max_length=255, choices=QuestionTypeChoices)
    media_link = models.TextField(null=True, blank=True)
    question = models.TextField(null=True, blank=True)
    subjective_answer = models.TextField(null=True, blank=True)
    objective_answer = models.TextField(null=True, blank=True)
    mcq_options = models.JSONField(null=True, blank=True)
    mcq_answer = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "test_question"


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

    class Meta:
        db_table = "test_attempt_session"


class TestQuestionResponse(TenantAwareModel):
    test_attempt_session_id = models.CharField(max_length=255, db_index=True)
    question_id = models.CharField(max_length=255, db_index=True)
    response_file = models.TextField(null=True, blank=True)
    response_text = models.TextField(null=True, blank=True)
    evaluation_status = models.CharField(max_length=255,
                                         choices=TestQuestionResponseEvaluationStatusChoices,
                                         default=TestQuestionResponseEvaluationStatusChoices.init)

    class Meta:
        db_table = "test_question_response"

        unique_together = (("test_attempt_session_id", "question_id"),)
