from django.contrib import admin

from .models import SessionNotesRecommendations, DirectoryPageInfo
from import_export.admin import ExportActionMixin

class SessionNotesRecommendationsAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')
    search_fields = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')

class DirectoryAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('profile_type','name', 'department','description','is_visible',"is_approved")
    list_filter = ('profile_type','status','department','is_visible',"is_approved")
    search_fields = ('name',"profile_type","bot_type","department","is_approved")
    list_editable = ('is_visible',"is_approved",)

admin.site.register(SessionNotesRecommendations, SessionNotesRecommendationsAdmin)
admin.site.register(DirectoryPageInfo, DirectoryAdmin)