from django.contrib import admin
from mail_box.models import MailBox, AuthorizedEmails, EmailConversation, AccountabilityIntake
from django.dispatch import receiver
from django.db.models.signals import post_save


@admin.register(MailBox)
class MailBoxAdmin(admin.ModelAdmin):
    list_display = ('uid', 'grant_id' ,'email', 'bot_name','prompt','followup_prompt',
                    'followup_prompt2', 'reward_prompt1', 'reward_prompt2',
                    'document_data' ,
                    'welcome_email_template', 'intake_reminder_email_template',
                    'intake_required',
                    'intake_url',
                    'created', 'updated', 'deleted')
    search_fields = ('email', 'prompt', 'grant_id')
    list_filter = ('created', 'updated', 'deleted', 'email')
    list_editable = ('email', 'prompt','followup_prompt','followup_prompt2', 'reward_prompt1', 'reward_prompt2', 
                     'welcome_email_template', 'intake_reminder_email_template',
                    'intake_required', 'bot_name',
                    'intake_url','deleted')

@admin.register(AuthorizedEmails)
class AuthorizedEmailsAdmin(admin.ModelAdmin):
    list_display = ('uid', 'mailbox_id', 'email', 'user_id', 'is_black_list', 'is_whitelist', 
                    'name','age','goal','situation','followup_fequency',
                  'followup_escalation_email','reward_emails',
                  'created', 'updated', 'deleted')
    search_fields = ('email', 'user_id','mailbox_id')
    list_filter = ('is_black_list','is_whitelist', 'created', 'updated', 'deleted')
    list_editable = ('email', 'user_id', 'is_black_list','is_whitelist', 
                     'name','age','goal','situation','followup_fequency',
                  'followup_escalation_email','reward_emails','deleted')

@admin.register(EmailConversation)
class EmailConversationAdmin(admin.ModelAdmin):
    list_display = ('uid', 'mailbox_id', 'sender', 'subject','body','sent_at','responder' ,'created', 'updated', 'deleted')
    search_fields = ('mailbox_id', 'sender', 'subject')
    list_filter = ('sent_at', 'created', 'updated', 'deleted')


@admin.register(AccountabilityIntake)
class AccountabilityIntakeAdmin(admin.ModelAdmin):
    list_display = ['uid', 'name', 'email_address']


@receiver(post_save, sender=AccountabilityIntake)
def update_status_after_intake_filled(sender, instance:AccountabilityIntake, created, **kwargs):
    if created:
        mailbox = MailBox.objects.filter(deleted=False,intake_url__contains=instance.form_id).first()
        if mailbox:
            users =  AuthorizedEmails.objects.filter(deleted=False,email=instance.email_address,mailbox_id=mailbox.uid) 
            for user in users:
                user.is_intake_filled = True
                user.save()