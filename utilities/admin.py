from django.contrib import admin

from .models import SessionNotesRecommendations
from import_export.admin import ExportActionMixin

class SessionNotesRecommendationsAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')
    search_fields = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')

admin.site.register(SessionNotesRecommendations, SessionNotesRecommendationsAdmin)