from django.db import models
from tenants.models import TenantAwareModel

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

    class Meta:
        db_table = "user_action_info"
