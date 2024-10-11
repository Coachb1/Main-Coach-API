from django.db import models
from commons.db.model import MyModel
from legacybot.choices import RoleType

# Create your models here.
class LegacyBot(MyModel):
    domain = models.CharField(max_length=100)
    assistant_id = models.CharField(max_length=100)
    assitant_type = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True, default=None)
    prompt = models.TextField(null=True, blank=True, default=None)

    class Meta:
        db_table = 'single_bot'
        unique_together = (
            ('domain','assistant_id' ,'deleted'),
        )


class LegacyBotUser(MyModel):
    bot_id = models.CharField(max_length=100,default=None)
    email = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100, null=True,blank=True, default=None)
    last_name = models.CharField(max_length=100, null=True,blank=True, default=None)
    att = models.JSONField(null=True,blank=True, default=None)
    is_whitelist = models.BooleanField(null=True, default=False)

    class Meta:
        db_table = 'single_bot_user'
        unique_together = (
            ('bot_id','email', 'deleted'),
        )

class Thread(MyModel):
    bot_id = models.CharField(max_length=100)
    thread_id = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    chat_topic = models.TextField()
    action_data = models.JSONField(null=True,blank=True,default=None)

    class Meta:
        db_table = 'legacybot_thread'
        unique_together = (
            ('bot_id','thread_id','user_id', 'deleted'),
        )

class ChatConversation(MyModel):
    thread_id = models.CharField(max_length=100)
    role = models.CharField(max_length=100, choices=RoleType)
    content = models.TextField()

    class Meta:
        db_table = 'chat_conversation'

