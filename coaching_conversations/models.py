from django.db import models

from coaching_conversations.choices import CoachingConversationChoices
from tenants.models import TenantAwareModel


class CoachingConversation(TenantAwareModel):
    test_attempt_session_id = models.CharField(max_length=255, db_index=True)

    coach_message_text = models.TextField()
    coach_message_metadata = models.JSONField(null=True, blank=True, default=None)

    participant_message_url = models.TextField(null=True, blank=True, default=None)
    participant_message_text = models.TextField(null=True, blank=True, default=None)

    status = models.CharField(max_length=255, choices=CoachingConversationChoices,
                              default=CoachingConversationChoices.bot_message_saved)

    class Meta:
        db_table = "coaching_conversation"

        ordering = ("-id",)

class BotResponsePrompt(TenantAwareModel):
    name = models.CharField(max_length=50)
    prompt = models.TextField()
    normalized_name = models.CharField(max_length=255, editable=False, db_index=True)

    def save(self, *args, **kwargs):
        self.normalized_name = self.name.strip().lower().replace(" ", "_")
        super().save(*args, **kwargs)
    def __str__(self):
        return self.name


