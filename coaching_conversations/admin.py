from django.contrib import admin 
from import_export.admin import ExportActionMixin
from coaching_conversations.models import CoachingConversation
from tests.models import TestAttemptSession
from identities.models import Identity
import logging
from users.models import ClientUserInfo, SignatureBot
from tenants.admin import TenantAwareModelAdmin

logger = logging.getLogger(__name__)

class CoachingConversationAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id','user_email','client_id','bot_id','bot_type','coach_message_text','participant_message_text','created')
    search_fields = ['id']
    list_filter = ('tenant_id','status')
    all_sessions = TestAttemptSession.objects.all()
    all_identities = Identity.objects.all()
    all_client_infos =  ClientUserInfo.objects.filter(deleted=False)
    client = None
    bot = None
    session_id = None
    
    def get_bot_from_obj(self, obj):
        test_attempt_session = self.all_sessions.filter(uid=obj.test_attempt_session_id).last()
        bot = SignatureBot.objects.filter(uid=test_attempt_session.test_id).last()
        return bot
    
    def bot_id(self, obj):
        bot = self.get_bot_from_obj(obj)
        return bot.bot_id if bot else None
    
    def bot_name(self, obj):
        bot = self.get_bot_from_obj(obj)
        return bot.bot_id if bot else None
    
    def user_email(self, obj):
        try:
            # test_attempt_session = TestAttemptSession.objects.filter(uid=obj.test_attempt_session_id).last()
            # identity = Identity.objects.filter(user_id=test_attempt_session.participant_id).order_by('id').last()
            test_attempt_session = self.all_sessions.filter(uid=obj.test_attempt_session_id).last()
            identity = self.all_identities.filter(user_id=test_attempt_session.participant_id).order_by('id').last()
            return identity.value
        except Exception as e:
            logger.exception(f"Error getting user email: {e}")
            return "user_email"
    
    def bot_type(self, obj):
        bot = self.get_bot_from_obj(obj)
        return bot.bot_type if bot else None
    
    def client_id(self, obj):
        logger.info(f"((((((((((((((((((((( USER Email : {self.user_email(obj).lower()} )))))))))))))))))))))")
        client = ClientUserInfo.objects.filter(deleted=False,member_emails__contains=self.user_email(obj).lower()).last()
        return client.client_name if client else ""
    
    
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
        # print(f"((((((((((((((((((((( SEARCHK TEARM : {search_term},  )))))))))))))))))))))")
        if search_term:
            filtered_ids = []
            for obj in queryset:
                # print(f"((((((((((((((((((((( SEARCHK TEARM : {search_term}, email: {self.user_email(obj).lower()}, condition: {search_term.lower() in self.user_email(obj).lower()} )))))))))))))))))))))")
                if search_term.lower() in self.user_email(obj).lower():
                    filtered_ids.append(obj.id)
            queryset = queryset.filter(id__in=filtered_ids)
        
        return queryset, use_distinct
    
    
    
    
    
    
admin.site.register(CoachingConversation, CoachingConversationAdmin)
