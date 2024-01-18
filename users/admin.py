from django.contrib import admin

from .models import BotAttribute, SignatureBot, ClientUserInfo, CoachCoacheeMentorMenteeProfile

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



admin.site.register(CoachCoacheeMentorMenteeProfile, CoachCoacheeMentorMenteeProfileAdmin)
admin.site.register(BotAttribute)
admin.site.register(SignatureBot, SignatureBotAdmin)
admin.site.register(ClientUserInfo)