from django.db import models
from django.forms import ValidationError
from commons.db.model import MyModel
from tenants.models import TenantAwareModel
from users.choices import ProfileTypeChoice, BotTypeChoice, StatusChoice, LLMChoice
from utilities.choices import UserCanJoinAsChoices

class JotUrlSession(models.Model):
    email = models.CharField(max_length=255)
    session_id = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "joturl_session"

class SpecialTypeTests(models.Model):
    tenant_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255, null=True,blank=True,default=None)
    description = models.TextField(null=True, blank=True, default=None)
    test_code = models.CharField(max_length=64, null=True,blank=True)
    case_type = models.CharField(
        max_length=255, default=None,null=True,blank=True)
    category = models.CharField(
        max_length=255, default=None,null=True,blank=True)
    
    class Meta:
        db_table = "specail_case_tests"

class MentorDetails(models.Model):
    tenant_id = models.CharField(max_length=255, db_index=True)
    mentor_id = models.CharField(max_length=255)
    mentee_ids = models.TextField(default=None,null=True,blank=True)
    
    class Meta:
        db_table = "mentor_details"

class SessionNotesRecommendations(models.Model):
    tenant_id = models.CharField(max_length=255, db_index=True)
    created_date = models.DateTimeField()
    updated_date = models.DateTimeField(null=True,blank=True)
    mentor_id = models.CharField(max_length=255)
    mentee_id = models.CharField(max_length=255)
    session_notes = models.TextField(default=None,null=True,blank=True)
    recommendations = models.TextField(default=None,null=True,blank=True)
    simulation_codes = models.CharField(max_length=255,default=None,null=True,blank=True)

    class Meta:
        db_table = "session_notes_and_recommendations"

class BotQnA(TenantAwareModel):
    participant_id = models.CharField(max_length=255)
    bot_id = models.CharField(max_length=255,default=None,null=True,blank=True)
    participant_qna = models.JSONField(default=None,null=True,blank=True)
    is_positive = models.BooleanField(null=True,default=False)
    qna_type = models.CharField(max_length=255,default=None,null=True,blank=True) # choice can be 'feedback' and "fitment" and "initial_qna"
    fitment_score = models.JSONField(default=None,null=True,blank=True)
    intake_summary = models.TextField(default=None,null=True,blank=True)
    is_anonymous = models.BooleanField(null=True,default=False)


    class Meta:
        db_table = "bot_qna"


class UserActionInfo(TenantAwareModel):
    user_id = models.CharField(max_length=255)
    bot_id = models.CharField(max_length=255,default=None,null=True,blank=True)
    feedback_given = models.IntegerField(null=True,blank=True,default=0)
    feedback_recieved = models.IntegerField(null=True,blank=True,default=0)
    transcript_email_sent = models.IntegerField(null=True,blank=True,default=0)
    transcript_email_recieved = models.IntegerField(null=True,blank=True,default=0)
    chat_attempted = models.IntegerField(null=True,blank=True,default=0)
    interaction_attempted = models.IntegerField(null=True,blank=True,default=0)
    avatar_bot_count = models.IntegerField(null=True,blank=True,default=0)
    subject_matter_bot_count = models.IntegerField(null=True,blank=True,default=0)
    session_notes_count = models.IntegerField(null=True,blank=True,default=0)
    avatar_ids = models.TextField(null=True,blank=True,default=None)
    subject_matter_bot_ids = models.TextField(null=True,blank=True,default=None)
    knowledge_bot_ids = models.TextField(null=True,blank=True,default=None)
    deep_dive_bot_ids = models.TextField(null=True,blank=True,default=None)
    feedback_bot_ids = models.TextField(null=True,blank=True,default=None)
    avatar_chat_attempted = models.IntegerField(null=True,blank=True,default=0)
    subject_specific_chat_attempted = models.IntegerField(null=True,blank=True,default=0)
    subject_specific_bot_ids = models.TextField(null=True,blank=True,default=None)
    subject_matter_chat_attempted = models.IntegerField(null=True,blank=True,default=0)
    knowledge_chat_attempted = models.IntegerField(null=True,blank=True,default=0)
    deep_dive_chat_attempted = models.IntegerField(null=True,blank=True,default=0)


    class Meta:
        db_table = "user_action_info"
        unique_together = ('tenant_id', 'deleted','user_id')

class BotEngagement(TenantAwareModel):
    bot_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)
    interacted_on = models.DateField()
    num_of_clicked_button = models.IntegerField(null=True,blank=True,default=0)
    attempted_bot_questions = models.IntegerField(null=True,blank=True,default=0)
    num_of_bot_sessions = models.IntegerField(null=True,blank=True,default=0)

    class Meta:
        db_table = 'bot_engagements'
        unique_together = ('tenant_id', 'deleted', 'bot_id','user_id','interacted_on')

class UserIDP(TenantAwareModel):
    user_id = models.CharField(max_length=255)
    user_name = models.CharField(max_length=255, blank=True, null=True)
    strengths = models.TextField(null=True,blank=True,default=None)
    weakness = models.TextField(null=True,blank=True,default=None)
    opportunities = models.TextField(null=True,blank=True,default=None)
    threats = models.TextField(null=True,blank=True,default=None)
    key_focus_areas = models.TextField(null=True,blank=True,default=None)
    goals = models.TextField(null=True,blank=True,default=None)
    priorities = models.TextField(null=True,blank=True,default=None)
    learning_histories = models.TextField(null=True,blank=True,default=None)
    key_skills = models.TextField(null=True,blank=True,default=None)
    skill_gap_for_development = models.TextField(null=True,blank=True,default=None)
    leadership_skill_focus_area = models.TextField(null=True,blank=True,default=None)
    book_recommendations = models.TextField(null=True,blank=True,default=None)
    course_recommendations = models.TextField(null=True,blank=True,default=None)
    recommended_hbr = models.TextField(null=True,blank=True,default=None)
    recommended_ted_talk = models.TextField(null=True,blank=True,default=None)
    recommended_scenarios = models.JSONField(null=True,blank=True,default=None)
    learning_communities = models.TextField(null=True,blank=True,default=None)
    report = models.TextField(null=True,blank=True,default=None)
    success = models.BooleanField(default=False, null=True,blank=True)
    total_scenarios_created = models.IntegerField(null=True, blank=True, default=0)


    class Meta:
        db_table = "user_idp_report"
        
        
class DirectoryPageInfo(models.Model):
    name = models.CharField(max_length=255)
    profile_id = models.CharField(max_length=255)
    department = models.CharField(max_length=255,null=True,blank=True,default=None)
    bot_type = models.CharField(max_length=255,choices=BotTypeChoice,null=True,blank=True,default=None)
    profile_pic_url = models.CharField(max_length=255,default=None,null=True,blank=True)
    profile_type = models.CharField(max_length=255, choices=ProfileTypeChoice)
    description = models.TextField()
    experience = models.CharField(max_length=255,default=None,null=True,blank=True)
    expertise = models.CharField(max_length=255,default=None,null=True,blank=True)
    status = models.CharField(max_length=255,null=True,blank=True,choices=StatusChoice,default=StatusChoice.available)
    avatar_bot_id = models.CharField(max_length=400,null=True,blank=True,default=None)
    feedback_wall = models.CharField(max_length=500,default=None,null=True,blank=True)
    skills = models.CharField(max_length=400,null=True,blank=True,default="communication skills")
    is_visible = models.BooleanField(blank=True,default=False)
    is_approved = models.BooleanField(blank=True,default=False)
    avatar_snippit = models.TextField(default=None,null=True,blank=True)
    avatar_bot_url = models.TextField(default=None,null=True,blank=True)
    custom_user_bot_url = models.TextField(null=True,blank=True,default=None)
    custom_user_bot_id = models.TextField(null=True,blank=True,default=None)
    timer_enabled = models.BooleanField(null=True,default=False)
    time_value_in_days = models.CharField(max_length=255,null=True,blank=True,default=None)
    timer_reset = models.BooleanField(null=True,default=False)
    visual_tag = models.CharField(max_length=255,null=True,blank=True,default=None)
    ai_email = models.CharField(max_length=255,null=True,blank=True,default=None)
    _previous_is_approved = models.BooleanField(null=True,default=False)
    subject_specific_bot_url = models.CharField(max_length=255,null=True,blank=True,default=None)
    subject_specific_bot_id = models.CharField(max_length=255,null=True,blank=True,default=None)
    subject_specific_bot_snippit = models.TextField(null=True,blank=True,default=None)
    deep_dive_bot_url = models.TextField(null=True,blank=True,default=None)
    deep_dive_bot_id = models.TextField(null=True,blank=True,default=None)

    class Meta:
        db_table = "directory_information"


    
class ScenarioCreationDetails(models.Model):
    tenant_id = models.CharField(max_length=255, db_index=True)
    creator_id = models.CharField(max_length=255)
    input = models.TextField(null=True,blank=True,default=None)
    output = models.TextField(null=True,blank=True,default=None)
    status = models.CharField(max_length=255)
    reason_of_failure = models.TextField(null=True,blank=True,default=None)
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scenario_creation_details"



class CoachCoacheeJoiningPreviledge(TenantAwareModel):
    email = models.CharField(max_length=255)
    client_name = models.CharField(max_length=255)
    can_join_as = models.CharField(max_length=255, choices=UserCanJoinAsChoices, default=UserCanJoinAsChoices.coachee)
    deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "coach_coachee_joining_previledge"
        unique_together = ('email', 'client_name', 'tenant_id')
        
        
        
class EmailSentDetails(TenantAwareModel):
    bot_name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.CharField(max_length=255)
    sent_to = models.CharField(max_length=255)
    status = models.CharField(max_length=255)
    is_sent = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "email_sent_details"


# Table to store llm name to be used in different sections
class LLMMappingTable(TenantAwareModel):
    bot_type = models.CharField(
        max_length=255,
        choices=BotTypeChoice,
        help_text="Select the bot type this mapping applies to.",
        null=True, 
        blank=True,
        default=None
    )

    llm1 = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        choices=LLMChoice,
        default=LLMChoice.gemini,
        help_text="First preference LLM provider."
    )
    llm2 = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        choices=LLMChoice,
        default=LLMChoice.anthropic,
        help_text="Second preference LLM provider."
    )
    llm3 = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        choices=LLMChoice,
        default=LLMChoice.gpt,
        help_text="Third preference LLM provider."
    )
    FEATURE_TYPE_CHOICES = [
        ('scenario_generation', 'Scenario Generation'),
    ]
    feature_type = models.CharField(
        max_length=255,
        choices=FEATURE_TYPE_CHOICES,
        null=True, 
        blank=True,
        default=None
    )

    class Meta:
        db_table = "llm_mapping_table"

    def clean(self):
        super().clean()

        # ✅ Require at least one of bot_type or feature_type
        if not self.bot_type and not self.feature_type:
            raise ValidationError("At least one of 'feature_type' or 'bot_type' must be provided.")

        # ✅ Ensure feature_type uniqueness per tenant
        if self.feature_type:
            exists = (
                LLMMappingTable.objects.filter(
                    deleted=False,
                    tenant_id=self.tenant_id,
                    feature_type=self.feature_type,
                )
                .exclude(id=self.id)
                .exists()
            )
            if exists:
                raise ValidationError(
                    {"feature_type": "Feature type must be unique per tenant."}
                )

        # ✅ Ensure bot_type uniqueness per tenant
        if self.bot_type:
            exists = (
                LLMMappingTable.objects.filter(
                    deleted=False,
                    tenant_id=self.tenant_id,
                    bot_type=self.bot_type,
                )
                .exclude(id=self.id)
                .exists()
            )
            if exists:
                raise ValidationError(
                    {"bot_type": "Bot type must be unique per tenant."}
                )

    def __str__(self):
        return f"{self.bot_type or self.feature_type} LLM ORDER"


class LLMMappingModels(MyModel):
    mapping = models.ForeignKey(
        LLMMappingTable,
        related_name="models",
        on_delete=models.CASCADE,
        help_text="Link to the LLM Mapping Table entry."
    )
    llm_type = models.CharField(
        max_length=55,
        choices=LLMChoice,
        default=LLMChoice.gemini
    )
    model_order = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        default="gpt-4o-mini",
        help_text="Model names (comma separated, in order)"
    )

    class Meta:
        db_table = "llm_mapping_models"

    def __str__(self):
        return f"{self.llm_type} Models for {self.mapping.bot_type}"

class GlobalPrompts(TenantAwareModel):
    resourse_id = models.CharField(max_length=64, null=True,blank=True)
    resourse_type = models.CharField(max_length=255,choices=BotTypeChoice)
    tag = models.CharField(max_length=255, null=True,blank=True)
    prompt = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    
class GlobalSystemInstructions(TenantAwareModel):
    resourse_id = models.CharField(max_length=64, null=True,blank=True)
    resourse_type = models.CharField(max_length=255,choices=BotTypeChoice)
    tag = models.CharField(max_length=255, null=True,blank=True)
    instruction = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    
    

class Widgets(models.Model):
    bot_id = models.CharField(max_length=255)
    client_id=models.CharField(max_length=255,blank=True,null=True)
    allow_audio_interaction=models.BooleanField(default=False)
    is_demo=models.BooleanField(default=False)
    snippet=models.TextField(blank=True,null=True)
    title = models.TextField(blank=True,null=True,default=None)

    class Meta:
        db_table = "widgets"
        
    def save(self, *args, **kwargs):
        widget = f"""
            <script src="https://playground.coachbots.com/widget/coachbots-stt-widget.js"></script>
            <div
            data-client-id="{self.client_id if self.client_id else ''}"
            data-allow-audio-interaction="{"true" if self.allow_audio_interaction else "false"}"
            data-is-demo="{ "true" if self.is_demo else "false"}"
            class="coachbots-coachscribe"
            data-bot-id="{self.bot_id}"
            ></div>
        """
        
        self.snippet = widget
        super().save(*args, **kwargs)