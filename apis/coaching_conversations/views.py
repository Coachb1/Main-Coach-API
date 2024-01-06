from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter

from apis.coaching_conversations.filtersets import CoachingConversationFilterSet
from apis.coaching_conversations.serializers import CoachingConversationDisplaySerializer, \
    InitializeCoachingConversationSerializer, ReplyCoachingConversationSerializer, CoachingConversationReportDataSerializer
from clients.permissions import IsAuthenticatedClient
from coaching_conversations.helpers import initialize_coaching_conversation, continue_coaching_conversation, get_bot_conversation_data_user
from coaching_conversations.models import CoachingConversation
from commons.viewset import ApiViewSet
from users.permissions import IsAuthenticatedUser
from tests.models import TestAttemptSession, Test
from users.models import User, SignatureBot
from users.db import get_user_display_name, get_user_by_id


class CoachingConversationViewSet(ApiViewSet,
                                  mixins.ListModelMixin):
    """
    This code defines a `CoachingConversationViewSet` class that is a subclass of `ApiViewSet` and `mixins.ListModelMixin`. 
    It provides various methods for managing coaching conversations, such as initializing a conversation, replying to a conversation, and retrieving conversation report data.

    Example Usage:
        # Initialize a coaching conversation
        POST /coaching-conversations/initialize
        Request Body:
        {
        "test_attempt_session_id": "12345"
        }
        Response Body:
        {
        "uid": "67890",
        "coach_message_text": "Hello, how can I help you?",
        "participant_message_text": null,
        "status": "bot_message_saved",
        "created": "2022-01-01T00:00:00Z",
        "updated": "2022-01-01T00:00:00Z"
        }

        # Reply to a coaching conversation
        POST /coaching-conversations/{conversation_uid}/reply
        Request Body:
        {
        "participant_message_text": "I have a question.",
        "participant_message_url": ""
        }
        Response Body:
        {
        "uid": "67891",
        "coach_message_text": "Sure, what's your question?",
        "participant_message_text": "I have a question.",
        "status": "participant_message_saved",
        "created": "2022-01-01T00:01:00Z",
        "updated": "2022-01-01T00:01:00Z"
        }

        # Get coaching conversation report data
        GET /coaching-conversations/report-data?test_attempt_session_id=12345
        Response Body:
        {
        "results": [
            {
            "uid": "67890",
            "coach_message_text": "Hello, how can I help you?",
            "participant_message_text": null,
            "status": "bot_message_saved",
            "created": "2022-01-01T00:00:00Z",
            "updated": "2022-01-01T00:00:00Z"
            },
            {
            "uid": "67891",
            "coach_message_text": "Sure, what's your question?",
            "participant_message_text": "I have a question.",
            "status": "participant_message_saved",
            "created": "2022-01-01T00:01:00Z",
            "updated": "2022-01-01T00:01:00Z"
            }
        ],
        "test_title": "Sample Test",
        "participant_name": "John Doe",
        "date": "2022-01-01T00:00:00Z",
        "logo": "https://example.com/logo.png"
        }

    Main functionalities:
    - Initialize a coaching conversation by providing a test attempt session ID.
    - Reply to a coaching conversation by providing a participant message text and optional participant message URL.
    - Get coaching conversation report data for a specific test attempt session.

    Methods:
    - `get_queryset()`: Overrides the base method to filter the queryset based on the current tenant ID.
    - `initialize_coaching_conversation_view()`: Initializes a coaching conversation by calling the `initialize_coaching_conversation()` function and returns the created conversation.
    - `continue_coaching_conversation_view()`: Continues a coaching conversation by calling the `continue_coaching_conversation()` function and returns the next conversation.
    - `get_coaching_conversation_report_data()`: Retrieves coaching conversation report data for a specific test attempt session.

    Fields:
    - `queryset`: The queryset for the coaching conversations, filtered to exclude deleted conversations.
    - `permission_classes`: The permission classes required to access the view.
    - `serializer_class`: The serializer class used for serializing/deserializing coaching conversations.
    - `filter_backends`: The filter backends used for filtering the coaching conversations.
    - `filterset_class`: The filter set class used for filtering the coaching conversations.
    - `ordering_fields`: The fields that can be used for ordering the coaching conversations.
    - `lookup_field`: The field used for looking up individual coaching conversations.
    """


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
        """
        Initializes a coaching conversation by calling the `initialize_coaching_conversation` function and returns the created conversation.

        Args:
            request (Request): The request object containing the POST data.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: The response object containing the serialized data of the created conversation.

        """
        serializer = InitializeCoachingConversationSerializer(
            data=request.data)
        serializer.is_valid(raise_exception=True)

        test_attempt_session_id = serializer.validated_data["test_attempt_session_id"]
        is_signature_bot = serializer.validated_data.get("is_signature_bot", False)

        next_conversation = initialize_coaching_conversation(
            tenant=request.tenant,
            test_attempt_session_id=test_attempt_session_id,
            is_signature_bot=is_signature_bot,
        )

        return Response(
            data=CoachingConversationDisplaySerializer(
                instance=next_conversation).data,
            status=status.HTTP_201_CREATED
        )

    @action(methods=["POST"], detail=True, url_path="reply")
    def continue_coaching_conversation_view(self, request, *args, **kwargs):
        """
        Handles the POST request to reply to a coaching conversation.

        Args:
            request (Request): The request object containing the POST data.
            *args (tuple): Additional positional arguments.
            **kwargs (dict): Additional keyword arguments.

        Returns:
            Response: The response object containing the serialized data of the updated conversation.
        """
        serializer = ReplyCoachingConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant_message_text = serializer.validated_data.get(
            "participant_message_text")
        participant_message_url = serializer.validated_data.get(
            "participant_message_url")
        is_signature_bot = serializer.validated_data.get("is_signature_bot", False)


        next_conversation = continue_coaching_conversation(
            tenant=request.tenant,
            reply_to_conversation=self.get_object(),
            participant_message_text=participant_message_text,
            participant_message_url=participant_message_url,
            is_signature_bot=is_signature_bot,
        )

        return Response(
            data=CoachingConversationDisplaySerializer(
                instance=next_conversation).data,
            status=status.HTTP_201_CREATED
        )

    @action(methods=["GET"], detail=False, url_path="report-data")
    def get_coaching_conversation_report_data(self, request, *args, **kwargs):
        """
        Retrieves coaching conversation report data for a specific test attempt session.

        Args:
            request (Request): The request object containing the GET data.
            test_attempt_session_id (str): The ID of the test attempt session for which to retrieve the coaching conversation report data.

        Returns:
            Response: A response object containing the coaching conversation report data.

        Expected output:
            {
              "results": [
                {
                  "uid": "67890",
                  "coach_message_text": "Hello, how can I help you?",
                  "participant_message_text": null,
                  "status": "bot_message_saved",
                  "created": "2022-01-01T00:00:00Z",
                  "updated": "2022-01-01T00:00:00Z"
                },
                {
                  "uid": "67891",
                  "coach_message_text": "Sure, what's your question?",
                  "participant_message_text": "I have a question.",
                  "status": "participant_message_saved",
                  "created": "2022-01-01T00:01:00Z",
                  "updated": "2022-01-01T00:01:00Z"
                }
              ],
              "test_title": "Sample Test",
              "participant_name": "John Doe",
              "date": "2022-01-01T00:00:00Z",
              "logo": "https://example.com/logo.png"
            }
        """
        test_attempt_session_id = request.query_params.get(
            "test_attempt_session_id", None)

        if test_attempt_session_id is None:
            return Response(
                data={"detail": "test_attempt_session_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        conversations = self.queryset.filter(
            test_attempt_session_id=test_attempt_session_id, tenant_id=request.tenant.uid).order_by("id")

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
            "date": date,
            "logo": request.tenant.logo,
        }

        return Response(data, status=status.HTTP_200_OK)
    
    @action(methods=["GET"], detail=False, url_path="bot-conversation-data")
    def bot_conversation_data(self, request, *args, **kwargs):

        tenant = self.request.tenant
        mode = request.query_params.get('for',None)
        user_id = request.query_params.get('user_id',None)

        if mode == 'admin':
            try:
                bot = SignatureBot.objects.get(user_id=user_id)
            except:
                return Response({"Bot not Found"}, status=status.HTTP_404_NOT_FOUND)

            bot_id = bot.uid
            sessions = TestAttemptSession.objects.filter(tenant_id=tenant.uid,deleted=0,test_id = bot_id)
            participant_ids = list(set(sessions.values_list('participant_id',flat=True)))

            data= []
            for participant_id in participant_ids:
                bot_sessions = sessions.filter(participant_id=participant_id)
                data_cov = get_bot_conversation_data_user(bot_sessions,tenant,participant_id)
                data.append(data_cov)

            return Response(data, status=status.HTTP_200_OK)


        elif mode == 'user':
            bot_ids = list(set(SignatureBot.objects.filter(deleted=0).values_list('uid',flat=True)))
            sessions = TestAttemptSession.objects.filter(deleted=0,tenant_id=tenant.uid,test_id__in=bot_ids,participant_id=user_id)
            data = get_bot_conversation_data_user(sessions,tenant,user_id)
            return Response(data, status=status.HTTP_200_OK)
        
        else:
            return Response({"Error: For parameter doesn't exits please check"}, status=status.HTTP_400_BAD_REQUEST)

