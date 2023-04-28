from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apis.coaching_conversations.serializers import CoachingConversationDisplaySerializer, \
    InitializeCoachingConversationSerializer, ReplyCoachingConversationSerializer
from coaching_conversations.helpers import initialize_coaching_conversation, continue_coaching_conversation
from coaching_conversations.models import CoachingConversation
from commons.viewset import ApiViewSet


class CoachingConversationViewSet(ApiViewSet,
                                  mixins.ListModelMixin):
    queryset = CoachingConversation.objects.filter(deleted=0)
    serializer_class = CoachingConversationDisplaySerializer
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    @action(methods=["POST"], detail=False, url_path="initialize")
    def initialize_coaching_conversation_view(self, request, *args, **kwargs):
        serializer = InitializeCoachingConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_attempt_session_id = serializer.validated_data["test_attempt_session_id"]

        next_conversation = initialize_coaching_conversation(
            tenant=request.tenant,
            test_attempt_session_id=test_attempt_session_id
        )

        return Response(
            data=CoachingConversationDisplaySerializer(instance=next_conversation).data,
            status=status.HTTP_201_CREATED
        )

    @action(methods=["POST"], detail=True, url_path="reply")
    def continue_coaching_conversation_view(self, request, *args, **kwargs):
        serializer = ReplyCoachingConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant_message_text = serializer.validated_data.get("participant_message_text")
        participant_message_url = serializer.validated_data.get("participant_message_url")

        next_conversation = continue_coaching_conversation(
            tenant=request.tenant,
            reply_to_conversation=self.get_object(),
            participant_message_text=participant_message_text,
            participant_message_url=participant_message_url,
        )

        return Response(
            data=CoachingConversationDisplaySerializer(instance=next_conversation).data,
            status=status.HTTP_201_CREATED
        )
