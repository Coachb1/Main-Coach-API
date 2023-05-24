from django.db import models

from tenants.models import TenantAwareModel

class SkillsRating(TenantAwareModel):
    # Default 0 value for all the skills
    participant_id = models.CharField(max_length=255, db_index=True)
    teamwork_score = models.FloatField(null=True, blank=True, default=0)
    teamwork_question_count = models.IntegerField(null=True, blank=True, default=0)
    teamwork_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    leadership_score = models.FloatField(null=True, blank=True, default=0)
    leadership_question_count = models.IntegerField(null=True, blank=True, default=0)
    leadership_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    people_management_score = models.FloatField(null=True, blank=True, default=0)
    people_management_question_count = models.IntegerField(null=True, blank=True, default=0)
    people_management_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    conflict_management_score = models.FloatField(null=True, blank=True, default=0)
    conflict_management_question_count = models.IntegerField(null=True, blank=True, default=0)
    conflict_management_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    negotiation_score = models.FloatField(null=True, blank=True, default=0)
    negotiation_question_count = models.IntegerField(null=True, blank=True, default=0)
    negotiation_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    strategic_thinking_score = models.FloatField(null=True, blank=True, default=0)
    strategic_thinking_question_count = models.IntegerField(null=True, blank=True, default=0)
    strategic_thinking_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    project_management_score = models.FloatField(null=True, blank=True, default=0)
    project_management_question_count = models.IntegerField(null=True, blank=True, default=0)
    project_management_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    time_management_score = models.FloatField(null=True, blank=True, default=0)
    time_management_question_count = models.IntegerField(null=True, blank=True, default=0)
    time_management_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    adaptability_score = models.FloatField(null=True, blank=True, default=0)
    adaptability_question_count = models.IntegerField(null=True, blank=True, default=0)
    adaptability_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    engagement_score = models.FloatField(null=True, blank=True, default=0)
    engagement_question_count = models.IntegerField(null=True, blank=True, default=0)
    engagement_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    empathy_score = models.FloatField(null=True, blank=True, default=0)
    empathy_question_count = models.IntegerField(null=True, blank=True, default=0)
    empathy_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    communication_score = models.FloatField(null=True, blank=True, default=0)
    communication_question_count = models.IntegerField(null=True, blank=True, default=0)
    communication_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    confidence_score = models.FloatField(null=True, blank=True, default=0)
    confidence_question_count = models.IntegerField(null=True, blank=True, default=0)
    confidence_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    clarity_score = models.FloatField(null=True, blank=True, default=0)
    clarity_question_count = models.IntegerField(null=True, blank=True, default=0)
    clarity_average_score = models.FloatField(null=True, blank=True, default=0, db_index=True)
    
    # Total number of questions attempted
    total_questions_attempted = models.IntegerField(null=True, blank=True, default=0)
    # Total number of test
    total_tests_attempted = models.IntegerField(null=True, blank=True, default=0)

    class Meta:
        db_table = 'skills_rating'
        unique_together = (
            ('participant_id', 'tenant_id', 'deleted'),
        )

# example: {'tenant-id': '123', 'label':'Super Manager', 'required_rating': 'leadership > 90, conflict_management > 80'}
class CustomRatingForLabels(TenantAwareModel):
    tenant_id = models.CharField(max_length=255, db_index=True)
    label = models.CharField(max_length=255, db_index=True)
    # List of string of required skills and raiting for a label
    required_rating = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'custom_rating_for_labels'
        unique_together = (
            ('tenant_id', 'label', 'deleted'),
        )