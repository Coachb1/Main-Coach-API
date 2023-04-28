from rest_framework import serializers

from coaching_conversations.models import CoachingConversation


class InitializeCoachingConversationSerializer(serializers.Serializer):
    test_attempt_session_id = serializers.CharField()


class ReplyCoachingConversationSerializer(serializers.Serializer):
    participant_message_text = serializers.CharField(required=False, default="")
    participant_message_url = serializers.CharField(required=False, default="")

    def validate(self, attrs):
        if not attrs.get("participant_message_url") and not attrs.get("participant_message_text"):
            raise serializers.ValidationError("no response provided")

        return attrs


class CoachingConversationDisplaySerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachingConversation
        fields = ["uid",
                  "coach_message_text",
                  "participant_message_text",
                  "status",
                  "created",
                  "updated"]
