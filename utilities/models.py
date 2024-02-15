from django.db import models
from tenants.models import TenantAwareModel
from users.choices import ProfileTypeChoice, BotTypeChoice, StatusChoice

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

    class Meta:
        db_table = "session_notes_and_recommendations"

class BotQnA(TenantAwareModel):
    participant_id = models.CharField(max_length=255)
    bot_id = models.CharField(max_length=255)
    participant_qna = models.JSONField(default=None,null=True,blank=True)
    is_positive = models.BooleanField(null=True,default=False)
    qna_type = models.CharField(max_length=255,default=None,null=True,blank=True)
    fitment_score = models.JSONField(default=None,null=True,blank=True)

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

    class Meta:
        db_table = "user_action_info"


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
    report = models.TextField(null=True,blank=True,default=None)
    success = models.BooleanField(default=False, null=True,blank=True)
    total_scenarios_created = models.IntegerField(null=True, blank=True, default=0)


    class Meta:
        db_table = "user_idp_report"
        
        
class DirectoryPageInfo(models.Model):
    name = models.CharField(max_length=255)
    profile_id = models.CharField(max_length=255)
    department = models.CharField(max_length=255)
    bot_type = models.CharField(max_length=255,choices=BotTypeChoice)
    profile_pic_url = models.CharField(max_length=255,default=None,null=True,blank=True)
    profile_type = models.CharField(max_length=255, choices=ProfileTypeChoice)
    description = models.TextField()
    experience = models.CharField(max_length=255,default=None,null=True,blank=True)
    expertise = models.CharField(max_length=255,default=None,null=True,blank=True)
    status = models.CharField(max_length=255,null=True,blank=True,choices=StatusChoice,default=StatusChoice.available)
    avatar_bot_id = models.CharField(max_length=400,null=True,blank=True,default='avatar')
    feedback_wall = models.CharField(max_length=500,default=None,null=True,blank=True)
    skills = models.CharField(max_length=400,null=True,blank=True,default="communication skills")
    is_visible = models.BooleanField(blank=True,default=False)
    is_approved = models.BooleanField(blank=True,default=False)
    avatar_snippit = models.TextField(default=None,null=True,blank=True)
    avatar_bot_url = models.TextField(default=None,null=True,blank=True)
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