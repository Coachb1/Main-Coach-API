from django.contrib import admin
from .models import LegacyBot, LegacyBotUser, Thread, ChatConversation
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

@admin.register(LegacyBot)
class LegacyBotAdmin(admin.ModelAdmin):
    list_display = ('id','uid','domain', 'assistant_id', 'assitant_type', 'name', 'description')
    search_fields = ('domain', 'assistant_id', 'name')
    list_filter = ('assitant_type','name')
    list_editable = ('domain','assitant_type','name', 'description')

@admin.register(LegacyBotUser)
class LegacyBotUserAdmin(admin.ModelAdmin):
    list_display = ('id','uid','bot_id', 'email', 'name','first_name', 'last_name', 'att')
    search_fields = ('email', 'name', 'bot_id')
    list_editable = ('bot_id', 'email', 'name', 'first_name', 'last_name', 'att')

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('id','uid','bot_id', 'thread_id', 'user_id', 'chat_topic')
    search_fields = ('bot_id', 'thread_id', 'user_id', 'chat_topic')
    list_editable = ('bot_id', 'thread_id', 'user_id', 'chat_topic')

@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('id','uid','thread_id', 'role', 'content')
    search_fields = ('thread_id', 'role', 'content')
    list_editable = ('thread_id', 'role', 'content')



@receiver(post_save, sender=ChatConversation)
def update_thread_on_conversation_save(sender, instance:ChatConversation, **kwargs):
    if kwargs['created']:
        thread = Thread.objects.filter(uid=instance.thread_id).first()
        if thread:
            thread.updated = instance.created
            thread.save(update_fields=['updated'])