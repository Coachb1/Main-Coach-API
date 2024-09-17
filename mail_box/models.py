from django.db import models
from commons.db.model import MyModel
from mail_box.choices import FollowupFreqType

# Create your models here.
class MailBox(MyModel):
    email = models.CharField(max_length=255)
    prompt = models.TextField(null=True, blank=True, default=None)
    followup_prompt = models.TextField(null=True, blank=True, default=None)
    document_data = models.JSONField(null=True, blank=True, default=dict)
    followup_prompt2 = models.TextField(null=True, blank=True, default=None)
    reward_prompt1 = models.TextField(null=True, blank=True, default=None)
    reward_prompt2 = models.TextField(null=True, blank=True, default=None)
    grant_id = models.CharField(max_length=255,null=True,blank=True,default=None)


    class Meta:
        db_table = 'mail_box'
        unique_together = (
            ('email', 'deleted'),
        )


class AuthorizedEmails(MyModel):
    mailbox_id = models.CharField(max_length=255,default=None)
    email = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255, null=True, blank=True, default=None)
    is_black_list = models.BooleanField(null=True, default=False)
    is_whitelist = models.BooleanField(null=True, default=False)
    name = models.CharField(max_length=255, null=True, blank=True, default=None)
    age = models.CharField(max_length=255, null=True, blank=True, default=None)
    goal = models.CharField(max_length=255, null=True, blank=True, default=None)
    situation = models.TextField(null=True, blank=True, default=None)
    followup_fequency = models.CharField(max_length=255,choices=FollowupFreqType,null=True,blank=True,default=FollowupFreqType.never)
    followup_escalation_email = models.CharField(max_length=255,null=True,blank=True,default=None)
    reward_emails = models.BooleanField(null=True, default=True)

    class Meta:
        db_table = 'authorized_emails'
        unique_together = (
            ('mailbox_id','email', 'deleted'),
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

