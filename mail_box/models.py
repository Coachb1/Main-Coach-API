from django.db import models
from commons.db.model import MyModel

# Create your models here.
class MailBox(MyModel):
    email = models.CharField(max_length=255)
    prompt = models.TextField(null=True, blank=True, default=None)
    followup_prompt = models.TextField(null=True, blank=True, default=None)
    document_data = models.JSONField(null=True, blank=True, default=dict)

    class Meta:
        db_table = 'mail_box'
        unique_together = (
            ('email', 'deleted'),
        )


class AuthorizedEmails(MyModel):
    email = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255, null=True, blank=True, default=None)
    is_black_list = models.BooleanField(null=True, default=False)
    is_whitelist = models.BooleanField(null=True, default=False)


    class Meta:
        db_table = 'authorized_emails'
        unique_together = (
            ('email', 'deleted'),
        )


class EmailConversation(MyModel):
    mailbox_id = models.CharField(max_length=255)
    sender = models.CharField(max_length=255)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    responder = models.CharField(max_length=100, default='user')
    sent_at = models.DateTimeField()

    class Meta:
        db_table = 'email_conversation'

