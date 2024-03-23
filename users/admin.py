from django.contrib import admin

from .models import BotAttribute, SignatureBot, ClientUserInfo, CoachCoacheeMentorMenteeProfile,BotAndUserMapping, CoachCoacheeConnection

class CoachCoacheeMentorMenteeProfileAdmin(admin.ModelAdmin):
    list_display = ('uid','profile_type','name', 'email', 'is_approved',)
    list_filter = ('profile_type','status','department','is_approved')
    search_fields = ('name', 'email', 'unique_id', 'user_id', 'low_rating_characteristics','high_rating_characteristics','mentoring_preferences'
                    ,'voice_sample','coaching_level',
                        'coach_same_department',
                        'coaching_style',
                        'time_commitment',
                        'is_approved',)
    list_editable = ('is_approved',)
    ordering = ('-uid',)


class SignatureBotAdmin(admin.ModelAdmin):
    list_display = ('uid','bot_id','bot_type','is_approved','is_system_bot','is_sample_bot','use_google_context','is_active')
    list_filter = ('is_approved','is_system_bot','is_sample_bot','use_google_context')
    search_fields = ('bot_name','bot_id')
    list_editable = ('is_approved','is_system_bot','is_sample_bot','use_google_context','is_active')
    ordering = ('-uid',)

class BotUserMappingAdmin(admin.ModelAdmin):
    list_display = ('id','bot_id','bot_owner_name','bot_owner_email','bot_owner_mob_number','user_mob_number','user_name','user_email')
    list_filter = ('bot_id','bot_owner_name','bot_owner_email','bot_owner_mob_number')
    search_fields = ('bot_owner_name','bot_id')
    ordering = ('-uid',)

class ClientUserInfoAdmin(admin.ModelAdmin):
    list_display = ('id','client_name','member_emails','member_mob_numbers','avatar_bot_creation','feedback_bot_creation','subject_matter_bot_creation','number_of_conversation_per_month','restricted_ids','demo_ids','accessed_bot_ids','coach_skills','coach_expertise','departments','restricted_pages','restricted_features')
    list_filter = ('client_name',)
    search_fields = ('client_name',)
    list_editable = ('client_name','member_emails','member_mob_numbers','avatar_bot_creation','feedback_bot_creation','subject_matter_bot_creation','number_of_conversation_per_month','restricted_ids','demo_ids','accessed_bot_ids','coach_skills','coach_expertise','departments','restricted_pages','restricted_features')
    ordering = ('-uid',)

admin.site.register(CoachCoacheeMentorMenteeProfile, CoachCoacheeMentorMenteeProfileAdmin)
admin.site.register(BotAttribute)
admin.site.register(SignatureBot, SignatureBotAdmin)
admin.site.register(BotAndUserMapping, BotUserMappingAdmin)
admin.site.register(ClientUserInfo,ClientUserInfoAdmin)