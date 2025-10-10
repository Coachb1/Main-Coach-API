from rest_framework import serializers

from coaching_conversations.models import CoachingConversation


class InitializeCoachingConversationSerializer(serializers.Serializer):
    test_attempt_session_id = serializers.CharField()
    is_signature_bot = serializers.BooleanField(default=False,required=False)
    initial_qna = serializers.JSONField(default=False,required=False)


class ReplyCoachingConversationSerializer(serializers.Serializer):
    participant_message_text = serializers.CharField(
        required=False, default="", allow_null=True, allow_blank=True)
    participant_message_url = serializers.CharField(
        required=False, default="", allow_null=True, allow_blank=True)
    is_signature_bot = serializers.BooleanField(default=False,required=False)
    is_prompt_only = serializers.BooleanField(default=False,required=False)
    only_current_session = serializers.BooleanField(default=False,required=False)


    def validate(self, attrs):
        if not attrs.get("participant_message_url") and not attrs.get("participant_message_text"):
            raise serializers.ValidationError("no response provided")

        return attrs


class CoachingConversationDisplaySerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachingConversation
        fields = ["uid",
                  "coach_message_text",
                  "participant_message_text","coach_message_metadata",
                  "status",
                  "created",
                  "updated"]


class CoachingConversationReportDataSerializer(serializers.ModelSerializer):
    test_attempt_session_id = serializers.CharField()
