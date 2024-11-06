from rest_framework import serializers
from legacybot.models import LegacyBot, LegacyBotUser, Thread, ChatConversation
from commons.cloudinary import upload_image
from legacybot.helpers import generate_bot_identifier
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

        threads = list(Thread.objects.filter(user_id=instance.uid).values_list('uid', flat=True))
        conversation_count = ChatConversation.objects.filter(thread_id__in=threads).count()
        unlimited_session = True if instance.max_session < 0 else False
        data['qouta_exceeded'] = unlimited_session

        data["TotalSessionCount"] = conversation_count // (instance.session_per_conversation_step * 2)
        data["total_conversation_steps"]= conversation_count / 2


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
            conversation_count = ChatConversation.objects.filter(thread_id=instance.uid).count()

            unlimited_session = True if user.max_session < 0 else False
            data['qouta_exceeded'] = unlimited_session
            data["sessionCount"] = conversation_count // (user.session_per_conversation_step * 2)
            data["conversation_steps"]= conversation_count / 2
            data['qouta_exceeded'] = unlimited_session

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
            conversation_count = ChatConversation.objects.filter(thread_id=instance.thread_id).count()
            unlimited_session = True if user.max_session < 0 else False
            data['qouta_exceeded'] = unlimited_session
            data["sessionCount"] = conversation_count // (user.session_per_conversation_step * 2)
            data["conversation_steps"]= conversation_count / 2

        return data

    