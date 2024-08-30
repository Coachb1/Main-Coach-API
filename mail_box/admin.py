from django.contrib import admin
from mail_box.models import MailBox, AuthorizedEmails, EmailConversation

@admin.register(MailBox)
class MailBoxAdmin(admin.ModelAdmin):
    list_display = ('uid', 'email', 'prompt', 'created', 'updated', 'deleted')
    search_fields = ('email', 'prompt')
    list_filter = ('created', 'updated', 'deleted', 'email')
    list_editable = ('email', 'prompt', 'deleted')

@admin.register(AuthorizedEmails)
class AuthorizedEmailsAdmin(admin.ModelAdmin):
    list_display = ('uid', 'email', 'user_id', 'is_black_list', 'created', 'updated', 'deleted')
    search_fields = ('email', 'user_id')
    list_filter = ('is_black_list', 'created', 'updated', 'deleted')
    list_editable = ('email', 'user_id', 'is_black_list', 'deleted')

@admin.register(EmailConversation)
class EmailConversationAdmin(admin.ModelAdmin):
    list_display = ('uid', 'mailbox_id', 'sender', 'subject', 'sent_at','responder' ,'created', 'updated', 'deleted')
    search_fields = ('mailbox_id', 'sender', 'subject')
    list_filter = ('sent_at', 'created', 'updated', 'deleted')
