from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter

from apis.coaching_conversations.filtersets import CoachingConversationFilterSet
from apis.coaching_conversations.serializers import CoachingConversationDisplaySerializer, \
    InitializeCoachingConversationSerializer, ReplyCoachingConversationSerializer, CoachingConversationReportDataSerializer
from clients.permissions import IsAuthenticatedClient
from coaching_conversations.helpers import initialize_coaching_conversation, continue_coaching_conversation
from coaching_conversations.models import CoachingConversation
from commons.viewset import ApiViewSet
from users.permissions import IsAuthenticatedUser
from tests.models import TestAttemptSession, Test
from users.models import User
from users.db import get_user_display_name, get_user_by_id


class CoachingConversationViewSet(ApiViewSet,
                                  mixins.ListModelMixin):
    queryset = CoachingConversation.objects.filter(deleted=0)
    permission_classes = (IsAuthenticatedClient, IsAuthenticatedUser)
    serializer_class = CoachingConversationDisplaySerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = CoachingConversationFilterSet
    ordering_fields = ("id", )
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    @action(methods=["POST"], detail=False, url_path="initialize")
    def initialize_coaching_conversation_view(self, request, *args, **kwargs):
        serializer = InitializeCoachingConversationSerializer(
            data=request.data)
        serializer.is_valid(raise_exception=True)

        test_attempt_session_id = serializer.validated_data["test_attempt_session_id"]

        next_conversation = initialize_coaching_conversation(
            tenant=request.tenant,
            test_attempt_session_id=test_attempt_session_id
        )

        return Response(
            data=CoachingConversationDisplaySerializer(
                instance=next_conversation).data,
            status=status.HTTP_201_CREATED
        )

    @action(methods=["POST"], detail=True, url_path="reply")
    def continue_coaching_conversation_view(self, request, *args, **kwargs):
        serializer = ReplyCoachingConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant_message_text = serializer.validated_data.get(
            "participant_message_text")
        participant_message_url = serializer.validated_data.get(
            "participant_message_url")

        next_conversation = continue_coaching_conversation(
            tenant=request.tenant,
            reply_to_conversation=self.get_object(),
            participant_message_text=participant_message_text,
            participant_message_url=participant_message_url,
        )

        return Response(
            data=CoachingConversationDisplaySerializer(
                instance=next_conversation).data,
            status=status.HTTP_201_CREATED
        )

    @action(methods=["GET"], detail=False, url_path="report-data")
    def get_coaching_conversation_report_data(self, request, *args, **kwargs):
        test_attempt_session_id = request.query_params.get(
            "test_attempt_session_id", None)

        if test_attempt_session_id is None:
            return Response(
                data={"detail": "test_attempt_session_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        conversations = self.queryset.filter(
            test_attempt_session_id=test_attempt_session_id, tenant_id=request.tenant.uid).order_by("-id")

        results = []

        for conversation in conversations:
            results.append({
                "uid": conversation.uid,
                "coach_message_text": conversation.coach_message_text,
                "participant_message_text": conversation.participant_message_text,
                "status": conversation.status,
                "created": conversation.created,
                "updated": conversation.updated
            })

        test_attempt_session = TestAttemptSession.objects.get(
            uid=test_attempt_session_id, tenant_id=request.tenant.uid)

        test_id = test_attempt_session.test_id
        participant_id = test_attempt_session.participant_id
        date = test_attempt_session.created

        test = Test.objects.get(uid=test_id, tenant_id=request.tenant.uid)

        test_title = test.title

        participant_name = get_user_display_name(
            get_user_by_id(participant_id))

        data = {
            "results": results,
            "test_title": test_title,
            "participant_name": participant_name,
            "date": date
        }

        return Response(data, status=status.HTTP_200_OK)
