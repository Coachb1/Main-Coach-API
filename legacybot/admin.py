from django.contrib import admin
from .models import LegacyBot, LegacyBotUser, Thread, ChatConversation

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

