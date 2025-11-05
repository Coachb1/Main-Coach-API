from django.db import models

from tenants.models import TenantAwareModel
from users.choices import UserRoleChoice, ProfileTypeChoice, BotTypeChoice, CoachCoacheeConnectionStatusChoice
from coaching_conversations.choices import BotScenarioCaseChoice
from commons.db.model import MyModel
from django.utils.crypto import get_random_string
import string 



def get_unique_access_code(model, field_name, prefix, length=6):
    """Utility function to generate unique access code."""
    access_code = generate_access_code(prefix, length)
    retries = 0

    # Use the model directly to query the database
    while model.objects.filter(**{field_name: access_code}).exists():
        if retries >= 4:
            length += 1  # Increase length if retries exceed
            retries = 0
        access_code = generate_access_code(prefix, length)
        retries += 1

    return access_code


def generate_access_code(prefix, length=6):
    """Helper to generate a prefixed random string."""    
    STRING_ASCII_DIGITS = string.ascii_uppercase + string.digits
    return f"{prefix}_{get_random_string(length=length, allowed_chars=STRING_ASCII_DIGITS)}"


def default_competency_data():
        return dict({"1": "Communication Skills", "2": "Teamwork", "3": "Planning and Organizing", "4": "Client Focus"})

def get_default_values(choice:str):
    text = ''
    if choice == 'skills':
        # skills = []
        # text = ",".join(skills)
        text = None
    elif choice == 'department':
        department = [
              "Sales & Marketing",
              "Production",
              "Design",
              "Engineering",
              "HR & Training"]
        text = ",".join(department)

    elif choice == "expertise":
        expertise =  [
                "Leadership Development",
                "Stress Management",
                "Hiring & Recruitment",
                "People Management",
                "Diversity & Inclusion",
                "Career Navigation",
                "Culture Alignment",
                "Workplace Skills"
                ]
        text = ",".join(expertise)

    return text

def get_default_allowed_ips():
    return {"feedback_deep-dive":""}
def get_default_ui_information():
    return {
        'bottom_text': None,
        'header': None,
        'read_text': None,
    }

def get_default_library_bot_value(case):
    if case == 'bot_config':
        return {"coaching": {"show": "", "bot_id": ""}}
    elif case == "default_filters":
        return {"function": "", "industry": "", "business_outcome": "", "emerging_players": "", "unexpected_outcomes": "", "implementation_complexity": ""}
    
def get_default_help_text():
    help_text_json = {
        "network_directory": {
            "header_text": "",
            "join_the_network": "",
            "search_filter": "",
            "participant_listing": "",
            "first_coach_profile": "",
            "email": "",
            "reviews": "",
            "feedback": ""
        },
        "demo": {
            "user_demos": "",
            "system_demos": "",
            "coachTalk": "",
            "coachScribe": "",
            "manager_plus": ""
        },
        "libarary": {
            "nav_one": "",
            "nav_two": "",
            "test_category": "",
            "simulations": "",
            "coachTalk": "",
            "coachScribe": ""
        },
        "creator_studio": {
            "action_items": "",
            "learning_ideas": "",
            "scenario_creator": "",
            "team_connect": "",
            "deep_dive": "",
            "knowledge_bots": ""
        },
        "profile": {
            "session_reports": "",
            "personal_leaderboard": "",
            "kudos_board": "",
            "directory_profile": "",
            "my_connections": "",
            "action_plan_session_notes": "",
            "bot_conversations": "",
            "my_rewards": "",
            "competencies": "",
            "idp": "",
            "email_sign": ""
        }
    }

    return help_text_json
    
def get_default_signature_bot_page_information():
    return {
        "benefits": None,
        "how_it_works": None,
        "sample": {
            "Quick Match": "The quick match demonstrates fitment between participants based on pre-decided criteria."
        }
    }


class User(TenantAwareModel):
    name = models.TextField(blank=True, null=True, default="")
    role = models.CharField(max_length=255, choices=UserRoleChoice)
    password = models.TextField(null=True)
    is_root = models.BooleanField(null=True, default=None)
    is_excluded = models.BooleanField(null=True,default=False)
    is_repeat = models.BooleanField(default=None, null=True, blank=True)
    test_per_month = models.IntegerField(default=None, null=True, blank=True)

    def get_email(self):
        """Returns the email of the user."""
        user_attribute = UserAttribute.objects.filter(user_id=self.uid, deleted=False).first()
        if user_attribute and user_attribute.attributes:
            return user_attribute.attributes.get('email', None)
        return None

    def get_client(self):
        email = self.get_email()
        client = ClientUserInfo.objects.filter(deleted=False, tenant_id=self.tenant_id, member_emails__contains=email).first()
        return client
    
    def get_mob_number(self):
        """Returns the mobile number of the user."""
        user_attribute = UserAttribute.objects.filter(user_id=self.uid, deleted=False).first()
        if user_attribute and user_attribute.attributes:
            return user_attribute.attributes.get('mob_number', None)
        return None
    class Meta:
        db_table = "user"
        ordering = ("-id",)

    @property
    def can_login(self):
        return self.password is not None

    @property
    def is_active(self):
        return self.can_login
    
    def __str__(self):
        from identities.models import Identity  # avoid circular import

        identity = Identity.objects.filter(deleted=False, user_id=self.uid).first()
        identity_value = identity.value if identity else ""

        return f"{self.name} ({self.role}) - {identity_value}"


class UserAttribute(TenantAwareModel):
    user_id = models.CharField(max_length=255)
    tag = models.CharField(max_length=255)
    attributes = models.JSONField(null=True, blank=True, default=None)
    difficulty_level = models.CharField(max_length=255,default="Midium",null=True,blank=True)
    easy_feedback_prompt = models.TextField(null=True, blank=True, default="NOTE: Evaluate the candidate answer from a very liberal perspective and provide feedback in a friendly manner.")
    midium_feedback_prompt = models.TextField(null=True, blank=True, default=None)
    critical_feedback_prompt = models.TextField(null=True, blank=True, default="NOTE: Evaluate the candidate answer in a very strict manner and provide a critical feedback.")
    custom_feedback_prompt_1 = models.TextField(null=True, blank=True, default=None)
    custom_feedback_prompt_2 = models.TextField(null=True, blank=True, default=None)
    easy_skill_prompt = models.TextField(null=True, blank=True, default="NOTE: Evaluate the answers from a very liberal perspective and rate the skills.")
    midium_skill_prompt = models.TextField(null=True, blank=True, default=None)
    critical_skill_prompt = models.TextField(null=True, blank=True, default="NOTE: Evaluate the answers from a very critical perspective and rate the skills.")
    custom_skill_prompt_1 = models.TextField(null=True, blank=True, default=None)
    custom_skill_prompt_2 = models.TextField(null=True, blank=True, default=None)
    test_previlage = models.TextField(null=True,blank=True,default=None)
    competency_data = models.JSONField(null=True,blank=True,default=default_competency_data)
    evaluate_relevency = models.BooleanField(null=True, blank = True, default=True)
    allow_audio_interactions = models.BooleanField(null=True, default=False)
    prioritize_user_audio_interaction = models.BooleanField(null=True, default=False)
    restricted_pages = models.TextField(null=True,blank=True,default=None)
    restricted_features = models.TextField(null=True,blank=True,default=None)
    assigned_tests = models.JSONField(null=True, blank=True, default=dict)
    access_allowed = models.TextField(null=True,blank=True,default=None)
    access_denied = models.TextField(null=True,blank=True,default=None)
    preferences = models.JSONField(null=True, blank=True, default=dict)

    class Meta:
        db_table = "user_attribute"

        unique_together = (("tenant_id", "user_id", "tag"),)



class SignatureBot(TenantAwareModel):
    bot_id = models.CharField(max_length=255)
    bot_type = models.CharField(max_length=255, null=True, blank=True, choices=BotTypeChoice)
    bot_details = models.JSONField(null=True, blank=True, default=None)
    recommended_codes = models.CharField(max_length=255, null=True, blank=True, default=None)
    user_id = models.CharField(max_length=255)
    tag = models.CharField(max_length=255, null=True, blank=True, default=None)
    attributes = models.JSONField(null=True, blank=True, default=None)
    data = models.JSONField(null=True, blank=True, default=None)
    custom_prompt = models.TextField(null=True, blank=True, default=None)
    faqs = models.JSONField(null=True, blank=True, default=None)
    is_fitment_analysis = models.BooleanField(null=True,default=True)
    is_strict_fitment = models.BooleanField(null=True,default=True)
    is_approved = models.BooleanField(null=True,default=False)
    is_active = models.BooleanField(null=True,default=True)
    is_system_bot = models.BooleanField(null=True,default=False)
    is_sample_bot = models.BooleanField(null=True,default=False)
    use_google_context = models.BooleanField(null=True,default=False)
    use_personality_context = models.BooleanField(null=True,default=False)
    use_idp = models.BooleanField(null=True,default=False)
    bot_scenario_case = models.CharField(max_length=255, null=True, blank=True, choices=BotScenarioCaseChoice, default=BotScenarioCaseChoice.general)
    is_approval_email_sent = models.BooleanField(null=True,default=False)
    bot_expires_at = models.DateTimeField(null=True,default=None,blank=True)
    access_code = models.CharField(max_length=10, blank=True, null= True, default=None)
    page_informations = models.JSONField(null=True, blank=True, default=get_default_signature_bot_page_information)
    is_private = models.BooleanField(null=True,default=False)
    system_instructions = models.TextField(null=True, blank=True, default=None)
    allow_public_access = models.BooleanField(null=True,default=False)
    integratable_widget_snippet = models.TextField(null=True, blank=True, default=None)
    use_latest_simualation = models.BooleanField(null=True,default=False)
    send_bot_transcript = models.BooleanField(blank=True,default=True)
    email_address_list = models.TextField(null=True, blank=True, default=None)
    

    class Meta:
        db_table = "signature_bot"

        unique_together = (("tenant_id", "user_id", "tag"),)


class BotAttribute(TenantAwareModel):
    bot_id = models.CharField(max_length=255)
    bot_name = models.CharField(max_length=255)
    coach_name = models.CharField(max_length=255)
    coach_email = models.CharField(max_length=255)
    attached_data = models.TextField(null=True, blank=True, default=None)    
    attached_links = models.TextField(null=True, blank=True, default=None)
    client_name = models.CharField(max_length=255,null=True, blank=True, default=None)
    conversations_per_month = models.IntegerField(null=True, blank=True, default=None)
    fitment_answers = models.JSONField(null=True, blank=True, default=None)
    fitment_data = models.JSONField(null=True, blank=True, default=None)
    feedback_questions = models.JSONField(null=True, blank=True, default=None)
    attached_faqs_context = models.JSONField(null=True, blank=True, default=None)
    attached_files = models.FileField(null=True, blank=True, default=None)
    initial_qnas = models.JSONField(null=True, blank=True, default=None)
    is_audio_response = models.BooleanField(null=True,default=False)
    about = models.TextField(null=True, blank=True, default=None)
    admirer_ids = models.TextField(null=True, blank=True, default=None)
    ui_information = models.JSONField(null=True, blank=True, default=None)
    extracted_documents = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        db_table = "bot_attributes"
        verbose_name = "Signature Bot Attribute"
        verbose_name_plural = "Signature Bot Attributes"
        unique_together = (("tenant_id", "bot_id"),)


class BotAndUserMapping(TenantAwareModel):
    bot_id = models.CharField(max_length=255)
    participant_id = models.CharField(max_length=255)
    bot_owner_name = models.CharField(max_length=255,null=True, blank=True, default=None)
    bot_owner_email = models.CharField(max_length=255,null=True, blank=True, default=None)
    bot_owner_mob_number = models.CharField(max_length=255,null=True, blank=True, default=None)
    user_mob_number = models.CharField(max_length=255,null=True, blank=True, default=None)
    user_name = models.CharField(max_length=255,null=True, blank=True, default=None)
    user_email = models.CharField(max_length=255,null=True, blank=True, default=None)


    class Meta:
        db_table = "bot_and_user_mapping"
        unique_together = (("tenant_id", "bot_id","participant_id"),)


class ClientUserInfo(TenantAwareModel):
    client_name = models.CharField(max_length=255)
    owner_id = models.CharField(max_length=255,null=True, blank=True, default=None)
    attributes = models.JSONField(null=True, blank=True, default=None)
    member_emails = models.TextField(null=True, blank=True, default=None)
    member_mob_numbers = models.TextField(null=True, blank=True, default=None)
    member_user_ids = models.TextField(null=True, blank=True, default=None)
    avatar_bot_creation = models.BooleanField(null=True, default=False)
    feedback_bot_creation = models.BooleanField(null=True, default=False)

    subject_matter_bot_creation = models.BooleanField(null=True, default=False) # indicates that client member can create subject matter bot (not using)
    required_form_fields = models.JSONField(null=True, blank=True, default=None)
    
    restricted_ids = models.TextField(null=True, blank=True, default=None)
    number_of_conversation_per_month = models.IntegerField(null=True, blank=True, default=None)
    demo_ids = models.TextField(null=True, blank=True, default=None)
    accessed_bot_ids = models.TextField(null=True, blank=True, default=None)
    coach_skills = models.TextField(null=True, blank=True, default=get_default_values("skills"))
    coach_expertise = models.TextField(null=True, blank=True, default=get_default_values('expertise'))
    departments = models.TextField(null=True, blank=True, default=get_default_values("department"))
    coach_mentor_previledge = models.TextField(null=True, blank=True, default=None)
    is_coach_mentor_previledge = models.BooleanField(blank=True, default=False)
    restricted_pages = models.TextField(null=True, blank=True, default=None)
    restricted_features = models.TextField(null=True, blank=True, default=None)
    domain_name = models.CharField(max_length=255,null=True, blank=True, default=None)
    
    deepdive_accessed_emails = models.TextField(null=True, blank=True, default=None)
    
    allowed_ips = models.JSONField(null=True, blank=True, default=get_default_allowed_ips)
    allow_audio_interactions = models.BooleanField(blank=True, default=True)
    make_new_user_in_trail = models.BooleanField(blank=True, default=True)
    heading = models.CharField(max_length=255,null=True, blank=True, default=None)
    sub_heading = models.CharField(max_length=255,null=True, blank=True, default=None)
    tag_line = models.CharField(max_length=255,null=True, blank=True, default=None)
    ui_information = models.JSONField(null=True, blank=True, default=get_default_ui_information)
    widget_access_code = models.CharField(max_length=255,null=True, blank=True, default=None)
    help_text = models.JSONField(null=True, blank=True, default=get_default_help_text)
    allow_paste_answer = models.BooleanField(blank=True, default=False)
    webhook_url = models.CharField(max_length=255,null=True, blank=True, default=None)
    webhook_secret = models.CharField(max_length=255,null=True, blank=True, default=None)
    webhook_token = models.CharField(max_length=255,null=True, blank=True, default=None)
    webhook_enabled = models.BooleanField(blank=True, default=False)
    excluded_users = models.TextField(null=True, blank=True, default=None)
    use_skills_from_skill_bank = models.BooleanField(default=False, blank=True)
    send_profile_for_reapproval = models.BooleanField(default=False, blank=True)
    email_address_list = models.TextField(null=True, blank=True, default=None)
    allow_access_to_platform = models.BooleanField(default=True)
    allow_access_to_snippet = models.BooleanField(default=True)
    report_on = models.BooleanField(null=True,blank=True, help_text="to enable or disable reporting for the test.")
    show_recommendations = models.BooleanField(default=True)
    button_controls = models.JSONField(default=dict, blank=True, help_text='for eg: {"mode_button": {"show": true}, "mindmap_button": {"show": true}, "assessment_button": {"show": true}}')
    is_active = models.BooleanField(default=True, blank=True)
    assigned_tests = models.ManyToManyField('tests.Test', blank=True, related_name="client_users")
    assigned_bots = models.ManyToManyField(
        'coaching_conversations.BotResponsePrompt',
        related_name="client_users",
        blank=True,
    )
    # for snnipets
    ask_access_code = models.BooleanField(default=True)


    # for simulation bot
    is_repeat = models.BooleanField(default=None, null=True, blank=True)
    test_per_month = models.IntegerField(default=None, null=True, blank=True)


    # for coaching conversations
    coaching_credits_per_month = models.IntegerField(default=0, null=True, blank=True)

    # for library bot config
    leaderboard_report_protected = models.BooleanField(default=True, blank=True)
    leaderboard_report_password = models.CharField(max_length=25, default='demobook#12345')
    universal_bot_config = models.JSONField(default=dict, blank=True, help_text='for eg: {"coaching": {"show":true,  "bot_id": "xyz"},"simulation": {"show":true}}')

    class Meta:
        db_table = "client_user_info"
        unique_together = (("tenant_id", "client_name"),)

    def save(self, *args, **kwargs):
        # Auto-generate access_code if blank
        if not self.widget_access_code:
            self.widget_access_code = get_unique_access_code(
                ClientUserInfo, "widget_access_code", self.client_name[:3].upper(), length=6
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.client_name
    
class LibraryBotConfig(MyModel):
    client = models.OneToOneField(ClientUserInfo, on_delete=models.CASCADE, related_name="library_bot_config")
    bot_config = models.JSONField(default=dict, blank=True, help_text='for eg: {"coaching": {"show":true,  "bot_id": "xyz"},"simulation": {"show":true}}')
    show_certification_badge = models.BooleanField(default=True, blank=True, help_text="To show certification batch in library bot config")
    default_filters = models.JSONField(
        default=lambda: get_default_library_bot_value("default_filters"),
        blank=True,
        null=True,
        help_text="""Default filters for the library bot, e.g., {"function": "", "industry": "Banking", "business_outcome": "", "emerging_players": "", "unexpected_outcomes": "", "implementation_complexity": ""} emerging_player can be true/false/empty keep empty any field to ignore filter """
    )
    leaderboard_report_protected = models.BooleanField(default=True, blank=True)
    leaderboard_report_password = models.CharField(max_length=25, default='demobook#12345')
    

    class Meta:
        db_table = "library_bot_config"

    def __str__(self):
        return f"Library Bot Config - {self.client.client_name if self.client else 'No Client'}"

class SnippetAccessCode(MyModel):
    client = models.ForeignKey(ClientUserInfo, on_delete=models.CASCADE, related_name="snippet_access_code")
    access_code = models.CharField(max_length=255, unique=True, null=True, blank=True, default=None)
    is_active = models.BooleanField(default=True)
    is_temporary = models.BooleanField(default=False)
    max_test_attempts = models.IntegerField(null=True, blank=True, default=2)

    class Meta:
        db_table = "access_code"
        unique_together = (("deleted","client","access_code"),)


    def save(self, *args, **kwargs):
        # Auto-generate access_code if blank
        if self.access_code in [None, ""]:
            self.access_code = get_unique_access_code(
                SnippetAccessCode, "access_code", self.client.client_name[:3].upper(), length=6
            )

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.client.client_name} - {self.access_code}"

class AccessCodeLog(MyModel):
    access_code = models.ForeignKey(SnippetAccessCode, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="access_logs")
    session_attempted = models.IntegerField(null=True, blank=True, default=0)

    class Meta:
        db_table = "access_code_log"
        unique_together = (( "deleted","access_code","user"),)
        verbose_name = "Snippet Access Code Log"
        verbose_name_plural = "Snippet Access Code Logs"


    def __str__(self):
        return f"{self.access_code.access_code} - {self.user.uid}"


class ReportConfig(MyModel):
    client = models.OneToOneField(ClientUserInfo, on_delete=models.CASCADE, related_name="report_config")
    # Booleans for different sections
    skill_rating = models.BooleanField(default=True)
    culture_rating = models.BooleanField(default=True)
    competency_metrix = models.BooleanField(default=True)
    feedback_summary = models.BooleanField(default=True)
    rating_summary = models.BooleanField(default=True)
    flash_card = models.BooleanField(default=True)
    mindmap = models.BooleanField(default=True)
    speech_metrix = models.BooleanField(default=True)
    powerfiller_words = models.BooleanField(default=True)
    skill_explanation = models.BooleanField(default=True)
    culture_explanation = models.BooleanField(default=True)
    psychometric_culture_rating = models.BooleanField(default=True)
    psychometric_culture_explanation = models.BooleanField(default=True)

    def __str__(self):
        return f"Report Config for {self.client.client_name}"
    
    class Meta:
        unique_together = (("deleted", "client"),)
        verbose_name = "Client Report Config"
        verbose_name_plural = "Client Report Configs"

    def save(self, *args, **kwargs):
        self.skill_explanation = self.skill_rating
        self.culture_explanation = self.culture_rating
        self.psychometric_culture_explanation = self.psychometric_culture_rating
        if not self.skill_rating:
            self.rating_summary = False

        super(ReportConfig, self).save(*args, **kwargs)


class CoachCoacheeMentorMenteeProfile(TenantAwareModel):
    profile_type = models.CharField(max_length=255, choices=ProfileTypeChoice)
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    status = models.CharField(max_length=255, null=True, blank=True, default=None)
    speciality = models.CharField(max_length=255, null=True, blank=True, default=None)
    experience = models.CharField(max_length=255, null=True, blank=True, default=None)
    location = models.CharField(max_length=255, null=True, blank=True, default=None)
    favourite_simulation_codes = models.CharField(max_length=255, null=True, blank=True, default=None)
    about = models.TextField(null=True, blank=True, default=None)
    department = models.CharField(max_length=255, null=True, blank=True, default=None)
    unique_id = models.CharField(max_length=255, null=True, blank=True, default=None)
    user_id = models.CharField(max_length=255)
    bot_ids = models.TextField(null=True, blank=True, default=None)
    bot_urls = models.TextField(null=True, blank=True, default=None)
    profile_image_url = models.CharField(max_length=255, null=True, blank=True, default=None)
    hard_skill_areas = models.CharField(max_length=255, null=True, blank=True, default=None)
    area_domain = models.CharField(max_length=255, null=True, blank=True, default=None)
    provided_links = models.JSONField(null=True, blank=True, default=None)
    low_rating_characteristics = models.CharField(max_length=255, null=True, blank=True, default=None)
    high_rating_characteristics = models.CharField(max_length=255, null=True, blank=True, default=None)
    mentoring_preferences = models.CharField(max_length=255, null=True, blank=True, default=None)
    mentoring_frameworks = models.TextField(null=True, blank=True, default=None)
    dominant_point_of_view = models.TextField(null=True, blank=True, default=None)
    problem_solving_approach = models.TextField(null=True, blank=True, default=None)
    admired_leaders = models.TextField(null=True, blank=True, default=None)
    voice_sample = models.BooleanField(null=True, default=False)
    coaching_for_fitment = models.CharField(max_length=128, null=True, blank=True, default=None)
    coaching_level = models.CharField(max_length=128, null=True, blank=True, default=None)
    coach_same_department = models.BooleanField(null=True, default=False)
    supported_outcome = models.CharField(max_length=255, null=True, blank=True, default=None)
    coaching_style = models.CharField(max_length=255, null=True, blank=True, default=None)
    time_commitment = models.CharField(max_length=128, null=True, blank=True, default=None)
    is_approved = models.BooleanField(null=True, default=False)
    other_details = models.JSONField(null=True, blank=True, default=None)
    bot_snippets = models.JSONField(null=True, blank=True, default=None)
    mob_number = models.CharField(max_length=255, null=True, blank=True, default=None)
    allow_coachee_to_create_session = models.BooleanField(null=True, blank=True, default=False)
    is_mentor = models.BooleanField(null=True, blank=True, default=False)
    qna_for_coach_mentor = models.JSONField(null=True, blank=True, default=None)
    significant_challenges_and_solutions = models.TextField(null=True, blank=True, default=None)
    common_phrases_and_expressions = models.TextField(null=True, blank=True, default=None)
    admirer_user_ids = models.TextField(null=True, blank=True, default=None)
    journey_and_background = models.TextField(null=True, blank=True, default=None)
    mentorship_contribution = models.TextField(null=True, blank=True, default=None)
    is_approved_email_sent = models.BooleanField(null=True, blank=True, default=False)
    discussion_topic = models.TextField(null=True, blank=True, default=None)
    optional_file_data = models.JSONField(null=True, blank=True, default=None)
    problem_statement = models.TextField(null=True, blank=True, default=None)
    provide_answers_using_emojis = models.BooleanField(null=True, blank=True, default=False)
    additional_coachee_info = models.TextField(null=True, blank=True, default=None)
    use_coachee_info_in_prompt = models.BooleanField(null=True, blank=True, default=True)
    meeting_availability = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        db_table = "coach_coachee_mentor_mentee_profile"

        unique_together = (("tenant_id", "uid"),)
        

class CoachRecommendationsForUser(TenantAwareModel):
    user_profile = models.ForeignKey(
        'CoachCoacheeMentorMenteeProfile', 
        on_delete=models.CASCADE, 
        related_name='coach_recommendations'
    )
    coach_recommendations = models.TextField(null=True, blank=True, default=None)

    class Meta:
        db_table = "coach_recommendations_for_user"
        unique_together = (("tenant_id", "user_profile","deleted"),)
        indexes = [
            models.Index(fields=['user_profile']),
            models.Index(fields=['tenant_id', 'user_profile']),
        ]
        
class CoachCoacheeRating(TenantAwareModel):
    coach_id = models.CharField(max_length=255)
    coachee_id = models.CharField(max_length=255)
    rating = models.DecimalField(null=True, blank=True, default=None, max_digits=4, decimal_places=2)
    rating_type = models.CharField(max_length=255, null=True, blank=True, default=None)
    rating_comment = models.TextField(null=True, blank=True, default=None)
    is_deleted = models.BooleanField(null=True, default=False)
    is_active = models.BooleanField(null=True, default=True)
    
    class Meta:
        db_table = "coach_coachee_rating"

        unique_together = (("tenant_id", "coach_id", "coachee_id", "is_deleted"),)



class CoachCoacheeConnection(TenantAwareModel):
    coach_id = models.CharField(max_length=64,null=True, blank=True, default=None)
    coachee_id = models.CharField(max_length=64,null=True, blank=True, default=None)
    mentor_id = models.CharField(max_length=64,null=True, blank=True, default=None)
    mentee_id = models.CharField(max_length=64,null=True, blank=True, default=None)
    connection_type = models.CharField(max_length=255, null=True, blank=True,default=None)
    status = models.CharField(max_length=255, null=True, blank=True, choices=CoachCoacheeConnectionStatusChoice, default='pending')
    is_approved = models.BooleanField(null=True, default=False)
    is_rejected = models.BooleanField(null=True, default=False)
    is_blocked = models.BooleanField(null=True, default=False)
    is_deleted = models.BooleanField(null=True, default=False)
    is_removed = models.BooleanField(null=True, default=False)
    coach_avatar_bot_id = models.CharField(max_length=255, null=True, blank=True, default=None)


    class Meta:
        db_table = "coach_coachee_connection"

        unique_together = (("tenant_id", "coach_id", "coachee_id"), ("tenant_id", "mentor_id", "mentee_id"))

class UserMindmap(TenantAwareModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)  
    mindmap_links = models.TextField(help_text="Enter links separated by commas")

    def get_links_list(self):
        return [link.strip() for link in self.mindmap_links.split(",") if link.strip()]

    def __str__(self):
        return f"{self.user.name} - Mindmap"