from django.contrib import admin

from .models import SessionNotesRecommendations, DirectoryPageInfo
from import_export.admin import ExportActionMixin

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from users.models import SignatureBot, CoachCoacheeMentorMenteeProfile

class SessionNotesRecommendationsAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')
    search_fields = ('id','mentor_id', 'mentee_id', 'session_notes', 'recommendations')

class DirectoryAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('id','name','profile_type',"bot_type","skills","avatar_bot_id","avatar_bot_url","avatar_snippit","feedback_wall", 'department','description','is_visible',"is_approved")
    list_filter = ('profile_type','status','department','is_visible',"is_approved")
    search_fields = ('name',"profile_type","bot_type","department","is_approved","is_visible")
    list_editable = ('name','profile_type',"bot_type","skills","avatar_bot_id","avatar_bot_url","avatar_snippit","feedback_wall", 'department','description','is_visible',"is_approved")

admin.site.register(SessionNotesRecommendations, SessionNotesRecommendationsAdmin)
admin.site.register(DirectoryPageInfo, DirectoryAdmin)

# @receiver(post_save, sender=DirectoryPageInfo)
# def send_approval_email(sender, instance, **kwargs):
#     if kwargs['created'] or not instance.is_approved:
#         return  # Ignore if the instance is being created or not approved

#     # Send email when is_approved is changed to True
#     if instance.is_approved:
#         subject = 'Your profile has been approved'
#         message = 'Congratulations! Your profile has been approved.'
#         print(subject)
#         # from_email = settings.DEFAULT_FROM_EMAIL
#         # recipient_list = [instance.email]

#         # send_mail(subject, message, from_email, recipient_list)

#     is_approved = instance.is_approved
#     bot_id = instance.avatar_bot
#     signature_bot = SignatureBot.objects.get(bot_id=bot_id,bot_type="avatar_bot")
#     feedback_bot = SignatureBot.objects.filter(user_id=signature_bot.user_id,bot_type="feedback_bot")
#     signature_bot.is_approved = is_approved
#     signature_bot.save()
#     for feed in feedback_bot:
#         feed.is_approved = is_approved
#         feed.save()
#     print("success")


# post_save.connect(send_approval_email, sender=DirectoryPageInfo)
