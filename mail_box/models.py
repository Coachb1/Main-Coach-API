from django.db import models
from commons.db.model import MyModel
from mail_box.choices import FollowupFreqType
from commons.cache_utils import get_cache, set_cache

# Create your models here.
class MailBox(MyModel):
    email = models.CharField(max_length=255)
    prompt = models.TextField(null=True, blank=True, default=None)
    followup_prompt = models.TextField(null=True, blank=True, default=None)
    document_data = models.JSONField(null=True, blank=True, default=dict)
    followup_prompt2 = models.TextField(null=True, blank=True, default=None)
    followup_prompt3 = models.TextField(null=True, blank=True, default=None)
    reward_prompt1 = models.TextField(null=True, blank=True, default=None)
    reward_prompt2 = models.TextField(null=True, blank=True, default=None)
    welcome_email_template = models.TextField(null=True, blank=True, default=None)
    intake_reminder_email_template = models.TextField(null=True, blank=True, default=None)
    intake_required = models.BooleanField(blank=True,default=False)
    bot_name = models.CharField(max_length=255,default=None)
    intake_url = models.CharField(max_length=255,null=True,blank=True,default='https://chat.coachbots.com/66dc18ab01ef84e231427f7b')
    grant_id = models.CharField(max_length=255,default=None)
    knowledge_base = models.TextField(null=True, blank=True, default=None, help_text="Knowledge base for the mailbox, can be used to store pdf and docx url can be comma separated.")

    @staticmethod
    def get_mailbox_choices():
        choices = get_cache('mailbox_choices')
        if not choices:
            choices = [(mailbox.uid, mailbox.bot_name) for mailbox in MailBox.objects.all()]
            set_cache('mailbox_choices', choices, timeout=3600)  # Cache for 1 hour
        return choices
    
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
    is_intake_filled = models.BooleanField(blank=True,default=False)


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


class AccountabilityIntake(MyModel):
    form_id = models.CharField(max_length=50, null=True, blank=True, default=None)
    event_type = models.CharField(max_length=50, null=True, blank=True, default=None)
    submission_number = models.IntegerField()
    ip_address = models.GenericIPAddressField(null=True, blank=True, default=None)
    submission_id = models.CharField(max_length=50, null=True, blank=True, default=None)
    form_name = models.CharField(max_length=255, null=True, blank=True, default=None)

    name = models.CharField(max_length=255)
    email_address = models.EmailField()
    competency_level = models.CharField(max_length=50)
    follow_up_frequency = models.CharField(max_length=255,choices=FollowupFreqType,default=FollowupFreqType.nan)
    followup_escalation_email = models.CharField(max_length=255,null=True,blank=True,default=None)
    wants_rewards = models.BooleanField()
    overall_goals = models.TextField()
    situational_context = models.TextField()

    class Meta:
        unique_together = (('form_id','email_address','deleted'))

    def __str__(self):
        return f"{self.name} - {self.email_address}"
