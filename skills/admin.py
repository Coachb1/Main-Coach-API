from django.contrib import admin

from .models import CharacteristicsAndPrompts
from import_export.admin import ExportActionMixin

class CharacteristicsAndPromptsAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'prompt','input_vars')
    search_fields = ('id','name')

admin.site.register(CharacteristicsAndPrompts,CharacteristicsAndPromptsAdmin)