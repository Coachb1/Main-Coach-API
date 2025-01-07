from django.db import models

from tenants.models import TenantAwareModel
from tests.choices import InteractionModeChoices
from tests.choices import QuestionForChoices
from tests.choices import QuestionTypeChoices
from tests.choices import TestAttemptSessionStatusChoices
from tests.choices import TestQuestionResponseEvaluationStatusChoices
from tests.choices import TestTypeChoices
from tests.choices import ScenarioCaseChoices
from commons.db.model import MyModel
from django.utils.crypto import get_random_string
import string


## psychometric section
# class PsychometricItem(MyModel):    
#     # Fields for Section and Subsection
#     section = models.CharField(max_length=255)
#     subsection = models.CharField(max_length=255, blank=True, null=True)

#     parameters = models.JSONField(blank=True, null=True, default=dict)

#     # Fields for Ranges
#     range_values = models.JSONField(blank=True, null=True, default=dict)

#     average_value = models.TextField(blank=True, null=True, default=None)

#     def __str__(self):
#         return f"{self.id} -{self.section} : {self.subsection}"
    
#     class Meta:
#         db_table = "psychometric_item"

class Psychometric(MyModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True, default=None)
    items = models.ManyToManyField("PsychometricItem", related_name='psychometrics', blank=True)  # Many-to-many relationship
    tenant_id = models.CharField(max_length=125, null=True, blank=True, default=None)


    def __str__(self):
        return self.name
    
    class Meta:
        db_table = "psychometric"
        unique_together = (
            ("name", "tenant_id", "deleted"),)

class PsychometricItem(MyModel):    
    # Fields for Section and Subsection
    # Link to Psychometric
    psychometric = models.ForeignKey(
        "Psychometric", 
        on_delete=models.CASCADE, 
        related_name="psy_items",
        default=45
    )

    section = models.CharField(max_length=255)
    subsection = models.CharField(max_length=255, blank=True, null=True)

    parameters = models.JSONField(blank=True, null=True, default=dict)

    # Fields for Ranges
    range_values = models.JSONField(blank=True, null=True, default=dict)

    average_value = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return f"{self.id} -{self.section} : {self.subsection}"
    
    class Meta:
        db_table = "psychometric_item"

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
    is_self_created = models.BooleanField(default=False, null=True, blank=True)
    is_repeat = models.BooleanField(default=True, null=True, blank=True)
    is_game_type = models.BooleanField(default=False, null=True, blank=True)
    is_immersive = models.BooleanField(default=False, null=True, blank=True)
    is_free = models.BooleanField(default=False, null=True, blank=True)
    is_checkin_type = models.BooleanField(default=False, null=True, blank=True)
    is_learner_path = models.BooleanField(default=False, null=True, blank=True)
    is_email_type = models.BooleanField(default=False, null=True, blank=True)
    skills_to_evaluate = models.TextField(null=True, blank=True, default=None)
    source = models.TextField(null=True, blank=True, default="CoachBot")
    image_url = models.TextField(null=True, blank=True, default=None)
    rating = models.TextField(null=True, blank=True, default="Not Rated")
    tedtalk_and_hbr_case = models.TextField(
        null=True, blank=True, default=None)

    email_candidate = models.BooleanField(default=True, null=True, blank=True)
    candidate_type = models.CharField(
        null=True, blank=True, max_length=255, default=None)
    orchestrated_conversation_details = models.JSONField(
        null=True, blank=True, default=None)
    certificate_details = models.JSONField(
        null=True, blank=True, default=None)
    ui_information = models.JSONField(
        null=True, blank=True, default=None)
    media_props = models.JSONField(
        null=True, blank=True, default=None)
    description_media = models.TextField(
        null=True, blank=True, default=None)
    client_name = models.CharField(max_length=255,default='Demo',null=True,blank=True)
    goals = models.TextField(null=True, blank=True, default=None)
    course = models.CharField(max_length=255, null=True, blank=True, default=None)
    industry = models.CharField(max_length=255, null=True, blank=True, default=None)
    exp_level = models.CharField(max_length=255, null=True, blank=True, default=None)
    total_question = models.IntegerField(null=True, blank=True, default=None)
    is_micro = models.BooleanField(default=False, null=True, blank=True)
    is_logged_in = models.BooleanField(default=False, null=True, blank=True)
    is_transcript_only = models.BooleanField(default=False, null=True, blank=True)
    is_pitch = models.BooleanField(default=False, null=True, blank=True)
    articles = models.TextField(null=True, blank=True, default=None)
    bot_name = models.CharField(max_length=255, null=True, blank=True, default=None)
    competency_group = models.CharField(max_length=255, null=True, blank=True, default=None)
    creator_user_id = models.CharField(max_length=255, null=True, blank=True, default=None)
    area_domain = models.CharField(max_length=255, null=True, blank=True, default=None)
    tab_category = models.CharField(max_length=255, null=True, blank=True, default=None)
    is_recommended = models.BooleanField(default=False, null=True, blank=True)
    visual_tags = models.CharField(max_length=255, null=True, blank=True, default=None)
    page_name = models.CharField(max_length=255, null=True, blank=True, default=None)
    scenario_summary = models.TextField(null=True, blank=True, default=None)
    creator_email = models.CharField(max_length=255, null=True, blank=True, default=None)
    is_assigned = models.BooleanField(default=False, null=True, blank=False)
    assigned_to = models.CharField(max_length=255, null=True, blank=True, default=None)
    assigned_by = models.CharField(max_length=64, null=True, blank=True, default=None)
    web_page_url = models.CharField(max_length=500, null=True, blank=True, default=None)
    sub_tab_category = models.CharField(max_length=255, null=True, blank=True, default=None)
    calculate_culture = models.BooleanField(default=True, null=True)
    snippet_url = models.CharField(max_length=500, null=True, blank=True, default=None)
    pshycometric_sections = models.JSONField(null=True, blank=True, default=None)
    psychometric= models.ForeignKey(
        Psychometric,
        related_name='tests',
        on_delete=models.SET_NULL,
        to_field='uid',  # Reference the UID field
        blank=True,
        null=True,  # Allow null if a test can exist without a psychometric set
        default=None
    )
    report_description = models.TextField(null=True, blank=True, default=None)
    category = models.CharField(max_length=255, null=True, blank=True, default=None)
    is_single_select = models.BooleanField(default=False, null=True, blank=True)
    
    class Meta:
        db_table = "test"
        ordering = ("-id",)

        unique_together = (
            ("tenant_id", "test_code", "deleted"),
        )

    def __str__(self):
        return f"{self.title} ({self.test_code})"


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
    mcq_path = models.TextField(null=True, blank=True,default=None)
    snippet_url = models.TextField(null=True, blank=True,default=None)

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
    skills_explanation = models.JSONField(null=True, blank=True, default=None)
    test_score = models.FloatField(null=True, blank=True, default=None)
    avg_score = models.FloatField(null=True, blank=True, default=None)
    speech_score = models.JSONField(null=True, blank=True, default=None)
    culture_skills_rating = models.JSONField(
        null=True, blank=True, default=None)
    culture_skills_explanation = models.JSONField(null=True, blank=True, default=None)

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
    feedback_summary = models.TextField(null=True,blank=True, default=None)
    culture_and_skill_summary = models.TextField(null=True,blank=True, default=None)
    mcq_summary = models.TextField(null=True,blank=True, default=None)
    competency_data = models.JSONField(null=True, blank=True,default=None)
    language_skills = models.TextField(null=True, blank=True, default=None)
    is_idp_discussion_opted = models.BooleanField(
        null=True, blank=True, default=False)
    intake_id = models.CharField(max_length=255, null=True, blank=True, default=None)
    conversation_summary = models.TextField(null=True, blank=True, default=None)
    related_previous_conversation_summary = models.TextField(null=True, blank=True, default=None)
    is_signature_bot = models.BooleanField(
            null=True, blank=True, default=False)
    pshycometric_data = models.JSONField(null=True, blank=True, default=None)

    

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
    kls_klp = models.JSONField(null=True, blank=True, default=None)
    mcq_skill = models.JSONField(null=True, blank=True, default=None)
    response_rating = models.TextField(null=True, blank=True,default=None)
    question_text = models.TextField(null=True, blank=True, default=None) # We are going to use this in case of unfixed question in dynamic (quesiton_id will be useless here)
    
    class Meta:
        db_table = "test_question_response"

        unique_together = (
            ("test_attempt_session_id", "question_id", "deleted"),)

        ordering = ("id",)



class UserTestConfigs(TenantAwareModel):
    user_email = models.EmailField(
        help_text="Enter the email address of the user. Ensure it is valid."
    )
    test_code = models.CharField(
        max_length=12,
        help_text="Enter the unique code for the test (maximum 12 characters)."
    )
    test_title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default=None,
        help_text="Optional: Enter the title of the test. It will be auto-populated if left blank."
    )
    access_code = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        default=None,
        help_text="Optional: Enter or generate a unique access code for the test."
    )
    user_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default=None,
        help_text="Optional: Enter the user ID associated with the user email."
    )
    report_on = models.BooleanField(
        help_text="Toggle this to enable or disable reporting for the test.",
        null=True,
        blank=True
    )

    class Meta:
        db_table = "user_test_configs"
        unique_together = (
            ('user_id', 'test_code', 'deleted')
        )

    def save(self, *args, **kwargs):
        # Auto-generate access_code if blank
        if not self.access_code:
            self.access_code = self.get_unique_access_code()

        super().save(*args, **kwargs)

    def get_unique_access_code(self) -> str:
        USER_TEST_ACCESS_CODE = 6
        access_code = self.generate_access_code(USER_TEST_ACCESS_CODE)
        retries = 0

        while UserTestConfigs.objects.filter(access_code=access_code).exists():
            if retries >= 4:
                USER_TEST_ACCESS_CODE += 1
                retries = 0
            access_code = self.generate_access_code(USER_TEST_ACCESS_CODE)
            retries += 1

        return access_code

    def generate_access_code(self, user_test_accesscode) -> str:
        """Helper to generate a prefixed random string."""
        prefix = ""
        if len(self.client_name.split()) == 1:
            prefix = self.client_name[:4].upper()
        else:
            prefix = ''.join(word[0] for word in self.client_name.split()).upper()
        STRING_ASCII_DIGITS = (string.ascii_uppercase + string.digits)
        return f"{prefix}_{get_random_string(length=user_test_accesscode, allowed_chars=STRING_ASCII_DIGITS)}"


    def __str__(self):
        return f"{self.test_code} ({self.user_email})"
    


# class UserTestAttempts(TenantAwareModel):
#     """Model to store user test attempts."""
#     session_id = models.CharField(max_length=100)
#     user_email = models.CharField(max_length=30)
#     test_code = models.CharField(max_length=10)
#     test_title = models.CharField(max_length=100)
#     test_id = models.models.CharField(max_length=100)