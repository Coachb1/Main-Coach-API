from django.db import models

from skills.choices import CultureMapSkillTypeChoices
from tenants.models import TenantAwareModel
from tests.choices import ScenarioCaseChoices


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

class CompetencySkillAndClientMapping(TenantAwareModel):
    client_id = models.CharField(max_length=255)
    competency_skill = models.CharField(max_length=255)
    prompts	= models.TextField()
    output =  models.TextField()

    class Meta:
        db_table = 'competency_skill_and_client_mapping'
        unique_together = (
            ( 'deleted','tenant_id','client_id','competency_skill'),
        )


class CultureMapSkill(TenantAwareModel):
    skill = models.CharField("Cultural Skill Name", max_length=100)
    description = models.TextField("Description")
    skill_type = models.CharField("Skill Type", max_length=50, choices=CultureMapSkillTypeChoices)
    evaluation_criteria = models.JSONField("Evaluation Criteria", blank=True, null=True, default=dict)
    test_type = models.CharField("Test Type", max_length=30, choices=ScenarioCaseChoices, default=ScenarioCaseChoices.others)

    class Meta:
        db_table = 'culture_map_skills'

    def __str__(self):
        return f"{self.skill} ({self.skill_type} - {self.test_type})"