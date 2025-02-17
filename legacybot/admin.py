from django.contrib import admin
from .models import LegacyBot, LegacyBotUser, Thread, ChatConversation, LegacyBotRoleAndPermissions, LegacyBotUserMapping
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from commons.cloudinary import upload_image
from django import forms

class LegacyBotImageUploadForm(forms.ModelForm):
    image = forms.ImageField(required=False, help_text="This Field is only to create image_url")

    class Meta:
        model = LegacyBot
        fields = '__all__'


@admin.register(LegacyBot)
class LegacyBotAdmin(admin.ModelAdmin):
    form = LegacyBotImageUploadForm

    list_display = ('id','uid','domain', 'bot_identifier','assistant_id', 'assitant_type', 'name', 'description')
    search_fields = ('domain', 'assistant_id', 'name')
    list_filter = ('assitant_type','name')
    list_editable = ('domain','bot_identifier','assitant_type','name', 'description')

    def save_model(self, request, obj, form, change):
        # Check if an image file is in the form data
        image = request.FILES.get('image')
        if image:
            obj.image_url = upload_image(image).get('secure_url')
        super().save_model(request, obj, form, change)

@admin.register(LegacyBotUser)
class LegacyBotUserAdmin(admin.ModelAdmin):
    list_display = ('id','uid', 'is_active', 'role', 'bot_id', 'email', 'name','first_name', 'last_name')
    search_fields = ('email', 'name', 'bot_id')
    list_filter = ('role','is_active','bot_id')
    list_editable = ('bot_id', 'is_active', 'role', 'email', 'name', 'first_name', 'last_name')


# @admin.register(LegacyBotRoleAndPermissions)
# class LegacyRoleAndPermissionAdmin(admin.ModelAdmin):
#     list_display = ('id','role', 'max_session', 'created' ,'deleted')
#     search_fields = ('role',)
#     list_editable = ('max_session','deleted')

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


@receiver(post_save, sender=ChatConversation)
def update_mapping_on_thread_or_conversation_save(sender, instance: ChatConversation, **kwargs):
    """Update the user-bot mapping when a thread or conversation is saved."""
    
    try:
        user, bot = instance.get_user_and_bot()
        
        mapping, created = LegacyBotUserMapping.objects.get_or_create(user=user, bot=bot)
        
        mapping.update_thread_and_conversation_info()
        if created:
            print(f"Created new mapping for user={user} and bot={bot}")
        else:
            print(f"Updated existing mapping for user={user} and bot={bot}")
    except Exception as e:
        print(f"Error updating mapping: {e}")
    
