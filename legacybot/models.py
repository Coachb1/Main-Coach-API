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
    is_published = models.BooleanField(null=True, default=False)


    class Meta:
        db_table = 'legacy_bot'
        unique_together = (
            ('domain','assistant_id' ,'deleted'),
        )
    def __str__(self):
        return f"{self.name} ({self.domain})"

class LegacyBotUser(MyModel):
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
    bot_id = models.CharField(max_length=100,default=None,null=True,blank=True)


    class Meta:
        db_table = 'legacy_bot_user'
        unique_together = (
            ('email', 'deleted'),
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

    def get_user_and_bot(self):
        thread = Thread.objects.filter(uid=self.thread_id).first()
        user = LegacyBotUser.objects.filter(uid=thread.user_id).first()
        bot = LegacyBot.objects.filter(uid=thread.bot_id).first()

        print(user, bot)


        return user, bot




class LegacyBotUserMapping(models.Model):
    user = models.ForeignKey(
        'LegacyBotUser', 
        on_delete=models.CASCADE, 
        related_name="bot_mappings",
        help_text="Reference to the legacy bot user."
    )
    bot = models.ForeignKey(
        'LegacyBot', 
        on_delete=models.CASCADE, 
        related_name="user_mappings",
        help_text="Reference to the legacy bot."
    )
    thread_and_conversation_info = models.JSONField(
        null=True, 
        blank=True, 
        default=dict,
        help_text="Stores JSON data for threads and conversations associated with this user-bot mapping."
    )
    total_thread = models.PositiveIntegerField(
        default=0, 
        null=True, 
        blank=True, 
        help_text="Total count of threads for this user-bot mapping."
    )
    total_conversation = models.PositiveIntegerField(
        default=0, 
        null=True, 
        blank=True, 
        help_text="Total count of conversations for this user-bot mapping."
    )
    total_session = models.PositiveIntegerField(
        default=0, 
        null=True, 
        blank=True, 
        help_text="Total count of sessions for this user-bot mapping."
    )

    class Meta:
        db_table = "legacy_bot_user_mapping"
        verbose_name = "Legacy Bot User Mapping"
        verbose_name_plural = "Legacy Bot User Mappings"
        unique_together = ('user', 'bot')
        indexes = [
            models.Index(fields=['user', 'bot']),
        ]


    def update_thread_and_conversation_info(self):
        # Get all threads associated with the user and bot
        threads = Thread.objects.filter(deleted=False, user_id=self.user.id, bot_id=self.bot.id)

        # Count the total number of threads
        total_thread = threads.count()

        # Get all conversations associated with these threads
        conversations = ChatConversation.objects.filter(deleted=False, thread_id__in=threads.values('uid'))

        # Count the total number of conversations
        total_conversation = conversations.count()

        # Build the thread and conversation info as a dictionary
        thread_and_conversation_info = {
            "total_threads": total_thread,
            "total_conversations": total_conversation,
            "thread_details": [
                {"thread_id": thread.uid, "conversation_count": conversations.filter(thread_id=thread.uid).count()}
                for thread in threads
            ]
        }

        # Update the fields
        self.total_thread = total_thread
        self.total_conversation = total_conversation
        self.thread_and_conversation_info = thread_and_conversation_info


        if self.user.session_per_conversation_step > 0:
            self.total_session = total_conversation // self.user.session_per_conversation_step
        else:
            self.total_session = 0  # Set to 0 if session_per_conversation_step is zero or invalid

        self.save()
            
    def __str__(self):
        return f"Mapping for user {self.user.name} ({self.user.email}) and bot {self.bot.name} ({self.bot.domain})"
