from rest_framework import serializers
from legacybot.models import LegacyBot, LegacyBotUser, Thread, ChatConversation


class LegacyBotSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegacyBot
        fields = '__all__'
        read_only_fields = ['uid', 'created', 'updated']

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

    