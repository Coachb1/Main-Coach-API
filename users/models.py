from django.db import models

from tenants.models import TenantAwareModel
from users.choices import UserRoleChoice, ProfileTypeChoice, BotTypeChoice, CoachCoacheeConnectionStatusChoice
from coaching_conversations.choices import BotScenarioCaseChoice

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
              "Career Management",
              "Work Life Banlance",
              "Project Management",
              "Lateral Transfers",
           ]
        text = ",".join(expertise)

    return text
    


class User(TenantAwareModel):
    name = models.TextField(blank=True, null=True, default="")
    role = models.CharField(max_length=255, choices=UserRoleChoice)
    password = models.TextField(null=True)
    is_root = models.BooleanField(null=True, default=None)
    is_excluded = models.BooleanField(null=True,default=False)

    class Meta:
        db_table = "user"
        ordering = ("-id",)

    @property
    def can_login(self):
        return self.password is not None

    @property
    def is_active(self):
        return self.can_login


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
    competency_data = models.JSONField(null=True,blank=True,default=default_competency_data())
    


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
    owner_id = models.CharField(max_length=255)
    attributes = models.JSONField(null=True, blank=True, default=None)
    member_emails = models.TextField(null=True, blank=True, default=None)
    member_mob_numbers = models.TextField(null=True, blank=True, default=None)
    member_user_ids = models.TextField(null=True, blank=True, default=None)
    avatar_bot_creation = models.BooleanField(null=True, default=False)
    feedback_bot_creation = models.BooleanField(null=True, default=False)
    subject_matter_bot_creation = models.BooleanField(null=True, default=False)
    number_of_conversation_per_month = models.IntegerField(null=True, blank=True, default=None)
    required_form_fields = models.JSONField(null=True, blank=True, default=None)
    restricted_ids = models.TextField(null=True, blank=True, default=None)
    demo_ids = models.TextField(null=True, blank=True, default=None)
    accessed_bot_ids = models.TextField(null=True, blank=True, default=None)
    coach_skills = models.TextField(null=True, blank=True, default=get_default_values("skills"))
    coach_expertise = models.TextField(null=True, blank=True, default=get_default_values('expertise'))
    departments = models.TextField(null=True, blank=True, default=get_default_values("department"))
    coach_mentor_previledge = models.TextField(null=True, blank=True, default=None)
    is_coach_mentor_previledge = models.BooleanField(null=True, default=False)
    restricted_pages = models.TextField(null=True, blank=True, default=None)
    restricted_features = models.TextField(null=True, blank=True, default=None)




    class Meta:
        db_table = "client_user_info"

        unique_together = (("tenant_id", "client_name"),)



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


    
    

    class Meta:
        db_table = "coach_coachee_mentor_mentee_profile"

        unique_together = (("tenant_id", "uid"),)
        
        
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