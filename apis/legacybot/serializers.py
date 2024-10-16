from rest_framework import serializers
from legacybot.models import LegacyBot, LegacyBotUser, Thread, ChatConversation
from commons.cloudinary import upload_image

class LegacyBotSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(write_only=True, required=False)
    class Meta:
        model = LegacyBot
        fields = '__all__'
        read_only_fields = ['uid', 'created', 'updated']
    
    def create(self, validated_data):
        # Handle image separately and generate image_url
        image = validated_data.pop('image', None)
        legacy_bot = LegacyBot.objects.create(**validated_data)
        if image:
            legacy_bot.image_url = upload_image(image).get('secure_url')
            legacy_bot.save()
        return legacy_bot

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

class ThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Thread
        fields = '__all__'
        read_only_fields = ['uid', 'created', 'updated']

class ChatConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatConversation
        fields = '__all__'
        read_only_fields = ['uid', 'created', 'updated']

    