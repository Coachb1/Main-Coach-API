from django.db import models

from tenants.models import TenantAwareModel


class SkillIndex(TenantAwareModel):
    display = models.TextField()
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True, default="")

    class Meta:
        db_table = 'skills_index'
        unique_together = (
            ('tenant_id', 'name', 'deleted'),
        )


class SkillsRating(TenantAwareModel):
    # Default 0 value for all the skills
    participant_id = models.CharField(max_length=255, db_index=True)
    # skills_info
    skills_info = models.JSONField(null=True, blank=True, default=dict)
    # Total number of questions attempted
    total_questions_attempted = models.IntegerField(null=True, blank=True, default=0)
    # Total number of test
    total_tests_attempted = models.IntegerField(null=True, blank=True, default=0)

    class Meta:
        db_table = 'skills_rating'
        unique_together = (
            ('tenant_id', 'participant_id', 'deleted'),
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
