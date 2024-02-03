from django.contrib import admin

from .models import CharacteristicsAndPrompts
from import_export.admin import ExportActionMixin

class CharacteristicsAndPromptsAdmin(admin.ModelAdmin):
    list_display = ('id','tenant_id','name', 'positive_prompt','negitive_prompt')
    search_fields = ('id','name')

admin.site.register(CharacteristicsAndPrompts,CharacteristicsAndPromptsAdmin)