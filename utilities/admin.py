from django.contrib import admin

from .models import SessionNotesRecommendations, DirectoryPageInfo, UserIDP, ScenarioCreationDetails, UserActionInfo, EmailSentDetails, CoachCoacheeJoiningPreviledge
from import_export.admin import ExportActionMixin

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from users.models import SignatureBot, CoachCoacheeMentorMenteeProfile, UserAttribute
from email_sender.helpers import send_email_with_html_template
from users.db import get_user_attribute,get_user_by_id,get_user_display_name
import logging

logger = logging.getLogger(__name__)

class SessionNotesRecommendationsAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')
    search_fields = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')
    

class EmailSentDetailsAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('id','subject','status','sent_by', 'is_sent')
    search_fields = ('id', 'subject','status','sent_by', 'is_sent')
    list_filter = ('is_sent',)

class DirectoryAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id','name','profile_type',"bot_type","skills","avatar_bot_id","avatar_bot_url","expertise","avatar_snippit","feedback_wall",'custom_user_bot_url', 'department','description','timer_enabled','time_value_in_days','timer_reset','visual_tag','ai_email','is_visible',"is_approved")
    list_filter = ('profile_type',"expertise",'status','department','is_visible',"is_approved")
    search_fields = ('name',"profile_type","bot_type","department","is_approved","is_visible","expertise")
    list_editable = ('name','profile_type',"bot_type","skills","avatar_bot_id","avatar_bot_url","expertise","avatar_snippit","feedback_wall",'custom_user_bot_url', 'department','description','timer_enabled','time_value_in_days','timer_reset','visual_tag','ai_email','is_visible',"is_approved")
    ordering = ['-id']

class CoachCoacheeJoiningPreviledAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('id','client_name','email',"can_join_as")
    list_filter = ('client_name','email',"can_join_as")
    search_fields = ('client_name','email',"can_join_as")
    list_editable = ('client_name','email',"can_join_as")

class IDPAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id','uid','user_id',"user_name","strengths","weakness","opportunities","threats","key_focus_areas","goals", 'priorities','learning_histories','key_skills',"skill_gap_for_development","leadership_skill_focus_area","book_recommendations","course_recommendations","recommended_hbr","recommended_ted_talk","recommended_scenarios","report","success")
    list_filter = ("uid","user_id","success")
    search_fields = ("uid","user_id","success")
    list_editable = ("strengths","weakness","opportunities","threats","key_focus_areas","goals", 'priorities','learning_histories','key_skills',"skill_gap_for_development","leadership_skill_focus_area","book_recommendations","course_recommendations","recommended_hbr","recommended_ted_talk","recommended_scenarios","success")


class ScenarioCreationDetailsAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('id','creator_id','status','input','output','reason_of_failure')

admin.site.register(SessionNotesRecommendations, SessionNotesRecommendationsAdmin)
admin.site.register(DirectoryPageInfo, DirectoryAdmin)
admin.site.register(UserIDP, IDPAdmin)
admin.site.register(ScenarioCreationDetails, ScenarioCreationDetailsAdmin)
admin.site.register(UserActionInfo)
admin.site.register(EmailSentDetails, EmailSentDetailsAdmin)
admin.site.register(CoachCoacheeJoiningPreviledge, CoachCoacheeJoiningPreviledAdmin)

@receiver(post_save, sender=DirectoryPageInfo)
def save_and_send_approval_email_post_save(sender, instance, **kwargs):
    if kwargs['created']:
        return  

    # Send email when is_approved is changed to True
    bot_id = instance.custom_user_bot_id if instance.profile_type == 'knowledge_bot' else instance.avatar_bot_id
    print("#"*100)
    print('start//')
    print(kwargs)
    try:
        coach_profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,uid=instance.profile_id)
        if instance.is_approved:
            coach_profile.is_approved = instance.is_approved
            coach_profile.save(update_fields=["is_approved"])
    except: 
        coach_profile = None

    signature_bot = SignatureBot.objects.filter(bot_id=bot_id)
    if instance.is_approved:
            try:
                subject = 'Your profile has been approved'
                emails = ["info@coachbots.com"]
                
                bot_owner = get_user_by_id(coach_profile.user_id if coach_profile else instance.profile_id)
                bot_owner_name = get_user_display_name(bot_owner)
                bot_owner_email = UserAttribute.objects.get(user_id=bot_owner.uid).attributes.get('email')
                emails.append(bot_owner_email)


                html_content = f"""
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                                <tr>
                                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey! {bot_owner_name}</p>
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Your request for creating a new profile/avatar/guide/bot is processed and is now live. You can check it listed on Coachbots! </p>

                                        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
                                    </td>
                                    </tr>
                                </table>
                            """
                
                if (coach_profile and not coach_profile.is_approved_email_sent) or instance.profile_type == 'knowledge_bot':
                    for email in emails:
                        logger.info(f"Sending email to {email}")
                        send_email_with_html_template(subject=subject,html_content=html_content,to_email=email)
                        logger.info(f"Email sent to {email}")
                        if coach_profile:
                            coach_profile.is_approved_email_sent = True
                            coach_profile.save(update_fields=["is_approved_email_sent"])
            except Exception as e:
                logger.info(f"failed to send email: {e}")
        
    if signature_bot.count() > 0:
        signature_bot = signature_bot.first()
        signature_bot.is_approved = instance.is_approved
        signature_bot.save(update_fields=["is_approved"])
        

    print("end" )
    print("*"*100)
    

post_save.connect(save_and_send_approval_email_post_save, sender=DirectoryPageInfo)
