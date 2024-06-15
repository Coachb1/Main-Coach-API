from django.contrib import admin 
from import_export.admin import ExportActionMixin
from coaching_conversations.models import CoachingConversation
from tests.models import TestAttemptSession
from identities.models import Identity
import logging

logger = logging.getLogger(__name__)

class CoachingConversationAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id','user_email','client_id','bot_type','coach_message_text','participant_message_text')
    search_fields = ['id']
    list_filter = ('tenant_id','status')
    
    def user_email(self, obj):
        try:
            test_attempt_session = TestAttemptSession.objects.filter(uid=obj.test_attempt_session_id).last()
            identity = Identity.objects.filter(user_id=test_attempt_session.participant_id).order_by('id').last()
            return identity.value
        except Exception as e:
            logger.exception(f"Error getting user email: {e}")
            return "user_email"
    
    def bot_type(self, obj):
        return "bot_type"
    
    def client_id(self, obj):
        return "client_id"
    
    
    # def get_search_results(self, request, queryset, search_term):
    #     print(f"((((((((((((((((((((( SEARCHK TEARM : {search_term} )))))))))))))))))))))")
    #     queryset, use_distinct = super().get_search_results(request, queryset, search_term)
    #     try:
    #         pass
    #         # test_attempt_session = TestAttemptSession.objects.filter(uid=obj.test_attempt_session_id).first()
    #         # identity = Identity.objects.filter(user_id=test_attempt_session.participant_id).order_by('id').last()
    #         # queryset |= self.model.objects.filter(age=search_term_as_int)
    #     except:
    #         pass
    #     return queryset, use_distinct
    
    
    def get_search_results(self, request, queryset, search_term):
        # Get initial search results from superclass method
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        queryset = CoachingConversation.objects.all()
        
        # Filter by user_email if a search term is provided
        print(f"((((((((((((((((((((( SEARCHK TEARM : {search_term},  )))))))))))))))))))))")
        if search_term:
            filtered_ids = []
            for obj in queryset:
                print(f"((((((((((((((((((((( SEARCHK TEARM : {search_term}, email: {self.user_email(obj).lower()}, condition: {search_term.lower() in self.user_email(obj).lower()} )))))))))))))))))))))")
                if search_term.lower() in self.user_email(obj).lower():
                    filtered_ids.append(obj.id)
            queryset = queryset.filter(id__in=filtered_ids)
        
        return queryset, use_distinct
    
    
    
    
    
    
admin.site.register(CoachingConversation, CoachingConversationAdmin)