from django.db import models
from commons.db.model import MyModel
from legacybot.choices import RoleType, RoleAndPermissionType

# Create your models here.

class LegacyBotRoleAndPermissions(MyModel):
    role = models.CharField(
        max_length=125, 
        choices=RoleAndPermissionType,
        help_text="Select the role for the bot."
    )
    max_session = models.IntegerField(
        null=True, 
        blank=True, 
        default=10,
        help_text="Maximum number of sessions. Set to -1 for unlimited sessions."
    )
    
    class Meta:
        db_table = 'legacy_bot_role_and_permission'
        unique_together = (
            ('role', 'deleted'),
        )

    def __str__(self):
        return f"{self.role}"


class LegacyBot(MyModel):
    domain = models.CharField(max_length=100)
    bot_identifier = models.CharField(max_length=255, default=None)
    assistant_id = models.CharField(max_length=100)
    vector_store_id = models.CharField(max_length=100, default=None, null=True, blank=True)
    assitant_type = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True, default=None)
    image_url = models.CharField(max_length=255,null=True, blank=True, default=None)
    prompt = models.TextField(null=True, blank=True, default=None)
    att = models.JSONField(null=True,blank=True,default=None)
    asst_meta_data = models.JSONField(null=True,blank=True,default=None)
    creator = models.ForeignKey(
        'LegacyBotUser',
        related_name="legacy_bot",
        null=True,
        blank=True,
        default=None,
        on_delete=models.CASCADE
    )


    class Meta:
        db_table = 'legacy_bot'
        unique_together = (
            ('domain','assistant_id' ,'deleted'),
        )
    def __str__(self):
        return f"{self.name} ({self.domain})"

class LegacyBotUser(MyModel):
    bot_id = models.CharField(max_length=100,default=None)
    email = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100, null=True,blank=True, default=None)
    last_name = models.CharField(max_length=100, null=True,blank=True, default=None)
    att = models.JSONField(null=True,blank=True, default=None)
    is_whitelist = models.BooleanField(null=True, default=False)
    preferences = models.CharField(max_length=255,null=True, blank=True, default=None)
    max_session = models.IntegerField(
        null=True, 
        blank=True, 
        default=10,
        help_text="Maximum number of sessions. Set to -1 for unlimited sessions."
    )
    session_per_conversation_step = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        default=10,
        help_text="This represents how many conv step a session will contain."
    )


    class Meta:
        db_table = 'legacy_bot_user'
        unique_together = (
            ('bot_id','email', 'deleted'),
        )

    def __str__(self):
        return f"{self.name} ({self.email})"
    
 

class Thread(MyModel):
    bot_id = models.CharField(max_length=100)
    thread_id = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    chat_topic = models.TextField()
    action_data = models.JSONField(null=True,blank=True,default=None)
    preferences = models.CharField(max_length=255,null=True, blank=True, default=None)


    class Meta:
        db_table = 'legacybot_thread'
        unique_together = (
            ('bot_id','thread_id','user_id', 'deleted'),
        )


class ChatConversation(MyModel):
    thread_id = models.CharField(max_length=100)
    role = models.CharField(max_length=100, choices=RoleType)
    content = models.TextField()
    # user_id = models.CharField(max_length=125, null=True, blank=True, default=None)
    # bot_id = models.CharField(max_length=125, null=True, blank=True, default=None)


    class Meta:
        db_table = 'chat_conversation'

