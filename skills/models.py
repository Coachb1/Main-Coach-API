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


class CustomRating(TenantAwareModel):
    tenant_id = models.CharField(max_length=255, db_index=True)
    custom_rating = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        db_table = 'custom_rating'
        unique_together = (
            ('tenant_id', 'deleted'),
        )


class CharacteristicsAndPrompts(TenantAwareModel):
    name = models.CharField(max_length=255)
    positive_prompt = models.TextField()
    negitive_prompt = models.TextField()

    class Meta:
        db_table = 'characteristics_and_prompts'
        unique_together = (
            ('uid', 'deleted','tenant_id','name'),
        )
