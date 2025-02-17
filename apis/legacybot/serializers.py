from rest_framework import serializers
from legacybot.models import LegacyBot, LegacyBotUser, Thread, ChatConversation
from commons.cloudinary import upload_image
from legacybot.helpers import generate_bot_identifier, calculate_session_info
from legacybot.choices import RoleAndPermissionType

class LegacyBotSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(write_only=True, required=False)
    creator = serializers.SlugRelatedField(
        queryset=LegacyBotUser.objects.all(),
        slug_field='uid'
    )
    class Meta:
        model = LegacyBot
        fields = '__all__'
        read_only_fields = ['uid', 'created', 'updated']
    
    def create(self, validated_data):
        # Handle image separately and generate image_url
        try:
            image = validated_data.pop('image', None)
            validated_data['bot_identifier'] = generate_bot_identifier(
                validated_data['domain'],
                assistant_id=validated_data['assistant_id']
            )
            legacy_bot = LegacyBot.objects.create(**validated_data)
            updated_fields = []
            if image:
                legacy_bot.image_url = upload_image(image).get('secure_url')
                updated_fields.append('image_url')


            if len(updated_fields) >0:
                legacy_bot.save(update_fields=updated_fields)

            return legacy_bot
        except Exception as e:
            print(e)

    def update(self, instance, validated_data):
        # Handle image separately and generate image_url
        image = validated_data.pop('image', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if image:
            instance.image_url = upload_image(image).get('secure_url')
        instance.save()
        return instance

class LegacyBotUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegacyBotUser
        fields = '__all__'
        read_only_fields = ['uid', 'created', 'updated']

    def to_representation(self, instance:LegacyBotUser):
        data = super().to_representation(instance)

        threads = Thread.objects.filter(user_id=instance.uid,deleted=False)
        quota_exceeded, total_sessions, total_conversation, today_data = calculate_session_info(
                                                                                   user=instance,
                                                                                   thread_ids=list(threads.values_list('uid', flat=True))
                                                                                   )
        data['qouta_exceeded'] = quota_exceeded
        data["TotalSessionCount"] = total_sessions
        data["total_conversation_steps"]= total_conversation
        data["today_data"] = today_data

        # in user sessioncount contain all bots. to get session count for each bot we need use thread or convsetion api.

        if threads.count() >0:
            data['last_conversation_date'] = threads.order_by('-updated').first().updated.date()
        else:
            data['last_conversation_date'] = None


        return data

class ThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Thread
        fields = '__all__'
        read_only_fields = ['uid', 'created', 'updated']

    def to_representation(self, instance):
        data = super().to_representation(instance)

        user = LegacyBotUser.objects.get(uid=instance.user_id)
        
        if user:
            quota_exceeded, total_sessions, total_conversation, today_data = calculate_session_info(
                                                                                        user=user,
                                                                                        thread_ids=[instance.uid]
                                                                                        )
            data['qouta_exceeded'] = quota_exceeded
            data["sessionCount"] = total_sessions
            data["conversation_steps"]= total_conversation
            data["today_data"] = today_data

        return data

class ChatConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatConversation
        fields = '__all__'
        read_only_fields = ['uid', 'created', 'updated']

    def to_representation(self, instance):
        data = super().to_representation(instance)

        user_id = Thread.objects.get(uid=instance.thread_id).user_id
        user = LegacyBotUser.objects.get(uid=user_id)

        if user:
            quota_exceeded, total_sessions, total_conversation,today_data =calculate_session_info(user=user,thread_ids=[instance.thread_id])
            data['qouta_exceeded'] = quota_exceeded
            data["sessionCount"] = total_sessions
            data["conversation_steps"]= total_conversation
            data["today_data"] = today_data

        return data

    