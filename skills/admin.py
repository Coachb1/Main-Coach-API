from django.contrib import admin

from .models import CharacteristicsAndPrompts, CompetencySkillAndClientMapping, CultureMapSkill
from import_export.admin import ExportActionMixin
from users.models import ClientUserInfo
from tenants.admin import TenantAwareModelAdmin

class CharacteristicsAndPromptsAdmin(TenantAwareModelAdmin):
    list_display = ('id','tenant_id','name', 'positive_prompt','negitive_prompt')
    search_fields = ('id','name')

class CompetencySkillAndClientMappingAdmin(TenantAwareModelAdmin):
    list_display = ('id','tenant_id','client_id','client_name', 'competency_skill','prompts','output')
    search_fields = ('client_id','competency_skill','client_name')
    list_filter = ('client_id','competency_skill')
    list_editable = ('competency_skill','prompts','output')

    def client_name(self, obj):
        try:
            client = ClientUserInfo.objects.get(uid=obj.client_id)
            return client.client_name
        except Exception as e:
            print(e)
            return 'Unknown'

    client_name.short_description = 'Client Name'
        
@admin.register(CultureMapSkill)
class CultureMapSkillAdmin(TenantAwareModelAdmin):
    list_display = ('id',"skill", "skill_type", "test_type", "description", "evaluation_criteria")
    search_fields = ("skill", "skill_type", "test_type")
    list_editable = ("skill", "skill_type", "test_type", "description",'evaluation_criteria')
    list_filter = ("skill_type", "test_type")

admin.site.register(CharacteristicsAndPrompts,CharacteristicsAndPromptsAdmin)
admin.site.register(CompetencySkillAndClientMapping, CompetencySkillAndClientMappingAdmin)