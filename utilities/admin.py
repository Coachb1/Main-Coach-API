from django.contrib import admin

from .models import LLMMappingModels, SessionNotesRecommendations, DirectoryPageInfo, UserIDP ,\
        ScenarioCreationDetails, UserActionInfo, EmailSentDetails, CoachCoacheeJoiningPreviledge, LLMMappingTable, GlobalPrompts, GlobalSystemInstructions, \
            Widgets
from import_export.admin import ExportActionMixin

from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from users.models import SignatureBot, CoachCoacheeMentorMenteeProfile, UserAttribute, BotAttribute
from email_sender.helpers import send_email_with_html_template, send_welcome_email
from users.db import get_user_attribute,get_user_by_id,get_user_display_name
from users.choices import ProfileTypeChoice
import logging
from commons.cache_utils import  reset_cache_with_prefix
from users.models import ClientUserInfo
from users.helpers import get_client_info_from_user_detail
from tenants.admin import TenantAwareModelAdmin

logger = logging.getLogger(__name__)

class SessionNotesRecommendationsAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_display = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')
    search_fields = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')
    

class EmailSentDetailsAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_display = ('id','subject','status','sent_by', 'is_sent')
    search_fields = ('id', 'subject','status','sent_by', 'is_sent')
    list_filter = ('is_sent',)

class ClientNameFilter(admin.SimpleListFilter):
    title = _('Client Name')
    parameter_name = 'client_name'

    def lookups(self, request, model_admin):
        # Generate the list of client names to filter by
        client_names = set()
        clients = set(ClientUserInfo.objects.all().values_list('client_name',flat=True))
        for client_name in clients:
            client_names.add((client_name, client_name))
        return sorted(client_names)

    def queryset(self, request, queryset):
        if self.value():
            client = ClientUserInfo.objects.filter(client_name=self.value()).first()
            profiles = CoachCoacheeMentorMenteeProfile.objects.filter(email__in=client.member_emails.split(",") if client else [])
            return queryset.filter(profile_id__in=list(profiles.values_list('uid',flat=True)))
        return queryset

class DirectoryAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_per_page = 10
    list_display = (
        'id', 'client_name','name','description','profile_type', 'bot_type', 'skills', 'avatar_bot_id', 'avatar_bot_url',
        'expertise', 'avatar_snippit', 'feedback_wall', 'custom_user_bot_url', 'custom_user_bot_id',
        'department', 'timer_enabled', 'time_value_in_days', 'timer_reset',
        'visual_tag', 'ai_email', 'is_visible', 'is_approved'
    )
    list_filter = (
        ClientNameFilter, 'profile_type', 'expertise', 'status', 'department', 'is_visible', 'is_approved'
    )
    search_fields = (
        'name', 'profile_type', 'bot_type', 'department', 'is_approved', 'is_visible',
        'expertise', 'avatar_bot_id', 'custom_user_bot_id', 
    )
    list_editable = (
        'name', 'profile_type', 'bot_type', 'skills', 'avatar_bot_id', 'avatar_bot_url',
        'expertise', 'avatar_snippit', 'feedback_wall', 'custom_user_bot_url', 'custom_user_bot_id',
        'department', 'description', 'timer_enabled', 'time_value_in_days', 'timer_reset',
        'visual_tag', 'ai_email', 'is_visible', 'is_approved'
    )
    ordering = ['-id']

    def client_name(self, obj):
        profile = CoachCoacheeMentorMenteeProfile.objects.filter(uid=obj.profile_id).first()
        client_name = None
        if profile:
            client = get_client_info_from_user_detail(tenant_id=profile.tenant_id,
                                                    user_uid=profile.user_id
                                                    )
            client_name = client.client_name if client else None
        return client_name

    client_name.short_description = 'Client Name'

class CoachCoacheeJoiningPreviledAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_display = ('id','client_name','email',"can_join_as")
    list_filter = ('client_name','email',"can_join_as")
    search_fields = ('client_name','email',"can_join_as")
    list_editable = ('client_name','email',"can_join_as")



class IDPAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id','uid','user_id',"user_name","strengths","weakness","opportunities","threats","key_focus_areas","goals", 'priorities','learning_histories','key_skills',"skill_gap_for_development","leadership_skill_focus_area","book_recommendations","course_recommendations","recommended_hbr","recommended_ted_talk","recommended_scenarios","report","success")
    list_filter = ("uid","user_id","success")
    search_fields = ("uid","user_id","success")
    list_editable = ("strengths","weakness","opportunities","threats","key_focus_areas","goals", 'priorities','learning_histories','key_skills',"skill_gap_for_development","leadership_skill_focus_area","book_recommendations","course_recommendations","recommended_hbr","recommended_ted_talk","recommended_scenarios","success")


class ScenarioCreationDetailsAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_display = ('id','creator_id','status','input','output','reason_of_failure')
    
    
class GlobalPromptsAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_display = ('id','created_at', 'resourse_type', 'tag')
    search_fields = ('prompt',)
    list_editable = ('resourse_type', 'tag')
    
class GlobalSystemInstructionsAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_display = ('id','created_at', 'resourse_type', 'tag', 'instruction')
    search_fields = ('instruction',)
    list_editable = ('resourse_type', 'tag')
    
    
class WidgetsAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_display = ('id', 'title','bot_id', 'client_id', 'is_demo', 'allow_audio_interaction', 'snippet')
    search_fields = ('bot_id',)
    list_editable = ('is_demo', 'allow_audio_interaction','client_id','snippet', 'title')


admin.site.register(SessionNotesRecommendations, SessionNotesRecommendationsAdmin)
admin.site.register(DirectoryPageInfo, DirectoryAdmin)
admin.site.register(UserIDP, IDPAdmin)
admin.site.register(ScenarioCreationDetails, ScenarioCreationDetailsAdmin)
admin.site.register(UserActionInfo)
admin.site.register(EmailSentDetails, EmailSentDetailsAdmin)
admin.site.register(CoachCoacheeJoiningPreviledge, CoachCoacheeJoiningPreviledAdmin)

admin.site.register(GlobalPrompts, GlobalPromptsAdmin)
admin.site.register(GlobalSystemInstructions, GlobalSystemInstructionsAdmin)
admin.site.register(Widgets, WidgetsAdmin)


# @receiver(post_save, sender=Widgets)
# def generate_widget_snippet(sender, instance, **kwargs):
#     try:
#         widget = f"""
#             <script src="https://playground.coachbots.com/widget/coachbots-stt-widget.js"></script>
#             <div
#             data-client-id="{instance.client_id}"
#             data-allow-audio-interaction="{instance.allow_audio_interaction}"
#             data-is-demo="{instance.is_demo}"
#             data-bot-id="{instance.bot_id}"
#             ></div>
#         """
        
#         instance.snippet = widget
#         instance.save(update_fields=["snippet"])
#     except Exception as e:
#         logger.error(f"Failed to generate widget snippet: {e}")
#         return
    

@receiver(post_save, sender=DirectoryPageInfo)
def save_and_send_approval_email_post_save(sender, instance:DirectoryPageInfo, **kwargs):
    if kwargs['created']:
        return  
    
    # clear the related caches
    # reset_cache_with_prefix('user-directory')

    # Send email when is_approved is changed to True

    bot_id = instance.custom_user_bot_id if instance.profile_type == 'knowledge_bot' else (instance.deep_dive_bot_id if instance.profile_type == 'deep_dive' else instance.avatar_bot_id or instance.subject_specific_bot_id)
    print("#"*100)
    print('start//')
    print(kwargs)
    try:
        coach_profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,uid=instance.profile_id)
        updated_fields = []
        if instance.is_approved != coach_profile.is_approved:
            coach_profile.is_approved = instance.is_approved
            updated_fields.append('is_approved')

        if instance.profile_pic_url != coach_profile.profile_image_url:
            coach_profile.profile_image_url = instance.profile_pic_url
            updated_fields.append('profile_image_url')

        if instance.name != coach_profile.name:
            coach_profile.name = instance.name
            updated_fields.append('name')

        if instance.department != coach_profile.department:
            coach_profile.department = instance.department
            updated_fields.append('department')

        if instance.experience != coach_profile.experience:
            coach_profile.experience = instance.experience
            updated_fields.append('experience')

        if instance.expertise != coach_profile.area_domain:
            coach_profile.area_domain = instance.expertise
            updated_fields.append('area_domain')

        if instance.description != coach_profile.about:
            coach_profile.about = instance.description
            updated_fields.append('about')

        if updated_fields:
            coach_profile.save(update_fields=updated_fields)


    except: 
        coach_profile = None

    if instance.profile_type in ['coachee','mentee']:
        return

    signature_bot = SignatureBot.objects.filter(deleted=False,bot_id=bot_id)
    if instance.is_approved:
            try:
                subject = 'Your profile has been approved'
                emails = ["coachbots@googlegroups.com"]
                
                bot_owner = get_user_by_id(coach_profile.user_id if coach_profile else instance.profile_id)
                bot_owner_name = get_user_display_name(bot_owner)
                bot_owner_email = UserAttribute.objects.get(user_id=bot_owner.uid).attributes.get('email')
                emails.append(bot_owner_email)

                msg = 'Your request for creating a new profile/avatar/guide/bot is processed and is now live. You can check it listed on Coachbot!'
                if instance.profile_type in ['knowledge_bot', 'deep_dive']:
                    bot_name = BotAttribute.objects.get(bot_id=signature_bot.first().uid).bot_name
                    if instance.profile_type == 'knowledge_bot':
                        subject = 'Your Knowledge bot has been approved'
                        msg = f'Hey! Your knowledge bot titled "{bot_name}" is now approved and is available for the community to try on Coachbot. Please have a look!'
                    elif instance.profile_type == 'deep_dive':
                        subject = 'Your Deep Dive bot has been approved'
                        msg = f'Hey! Your Deep Dive bot titled "{bot_name}" is now approved and is available for the community to try on Coachbot. Please have a look!'


                html_content = f"""
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">{msg}</p>
                            """
                
                if (coach_profile and not coach_profile.is_approved_email_sent) or (instance.profile_type in ['knowledge_bot','deep_dive'] and not signature_bot.first().is_approval_email_sent):
                    if coach_profile:
                            coach_profile.is_approved_email_sent = True
                            coach_profile.save(update_fields=["is_approved_email_sent"])
                    else:
                        bot = signature_bot.first()
                        bot.is_approval_email_sent = True
                        bot.save(update_fields=["is_approval_email_sent"])

                    for email in emails:
                        logger.info(f"Sending email to {email}")
                        if instance.profile_type in [ProfileTypeChoice.coach, ProfileTypeChoice.mentor, ProfileTypeChoice.coach_mentor]:
                            send_welcome_email(
                                profile_type=ProfileTypeChoice.coach,
                                user_email= email,
                                user_name=bot_owner_name
                            )
                        else:
                            send_email_with_html_template(subject=subject,html_content=html_content,to_email=email,title=f'Hey! {bot_owner_name}')

                        logger.info(f"Email sent to {email}")

            except Exception as e:
                logger.info(f"failed to send email: {e}")
        
    # else: 
    #     if coach_profile:
    #         coach_profile.is_approved_email_sent = False
    #         coach_profile.save(update_fields=["is_approved_email_sent"])

    #     if instance.profile_type == 'knowledge_bot':
    #         bot = signature_bot.first()
    #         bot.is_approval_email_sent = False
    #         bot.save(update_fields=["is_approval_email_sent"])

    if signature_bot.count() > 0:
        signature_bot = signature_bot.first()
        signature_bot.is_approved = instance.is_approved
        signature_bot.save(update_fields=["is_approved"])
        

    print("end" )
    print("*"*100)
    

post_save.connect(save_and_send_approval_email_post_save, sender=DirectoryPageInfo)
# post_save.connect(generate_widget_snippet, sender=Widgets)





class LLMMappingModelsInline(admin.TabularInline):
    model = LLMMappingModels
    extra = 0
    fields = ("llm_type", "model_order")


@admin.register(LLMMappingTable)
class LLMMappingTableAdmin(TenantAwareModelAdmin):
    list_display = ("bot_type", "tenant_id", "llm1", "llm2", "llm3")
    list_filter = ("bot_type", "tenant_id")
    search_fields = ("bot_type",)
    inlines = [LLMMappingModelsInline]


@admin.register(LLMMappingModels)
class LLMMappingModelsAdmin(admin.ModelAdmin):
    list_display = ("mapping", "llm_type", "model_order")
    list_filter = ("llm_type",)
    search_fields = ("model_order",)

