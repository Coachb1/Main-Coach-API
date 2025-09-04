from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
import json

from apis.coaching_conversations.filtersets import CoachingConversationFilterSet
from apis.coaching_conversations.serializers import CoachingConversationDisplaySerializer, GeminiPromptSerializer, \
    InitializeCoachingConversationSerializer, ReplyCoachingConversationSerializer, CoachingConversationReportDataSerializer
from clients.permissions import IsAuthenticatedClient
from coaching_conversations.helpers import get_bot_chat_history, initialize_coaching_conversation, continue_coaching_conversation, get_bot_conversation_data_user
from coaching_conversations.models import BotResponsePrompt, CoachingConversation
from commons.google_apis import gemini_streaming_completion
from commons.viewset import ApiViewSet
from users.permissions import IsAuthenticatedUser
from tests.models import TestAttemptSession, Test
from users.models import User, SignatureBot, BotAttribute, ClientUserInfo, UserAttribute, CoachCoacheeMentorMenteeProfile
from users.db import get_user_display_name, get_user_by_id
from coaching_conversations.helpers import create_user_profile_and_bot, save_coach_recommendation, fetch_user_profile_and_bot
import csv
from commons.notifications import send_error_notification
from identities.helpers import get_user_via_identity
from coaching_conversations.helpers import generate_team_connect_response
from commons.cache_utils import get_cache, set_cache, delete_cache, generate_cache_key, reset_cache_with_prefix
from utilities.models import BotQnA
import logging

logger = logging.getLogger(__name__)


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
        Handles the initialization of a coaching conversation view.

        This method validates the incoming request data using the 
        `InitializeCoachingConversationSerializer` and initializes a coaching 
        conversation based on the provided data. It then returns the serialized 
        representation of the next conversation.

        Args:
            request (Request): The HTTP request object containing the data for 
                initializing the coaching conversation.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A Response object containing the serialized data of the 
            initialized coaching conversation and a status code of HTTP 201 Created.

        Raises:
            ValidationError: If the provided data is invalid.

        Notes:
            - `test_attempt_session_id` is a required field in the request data.
            - `is_signature_bot` and `initial_qna` are optional fields.
            - Logs the `initial_qna` value for debugging purposes.
        """
        serializer = InitializeCoachingConversationSerializer(
            data=request.data)
        serializer.is_valid(raise_exception=True)

        test_attempt_session_id = serializer.validated_data["test_attempt_session_id"]
        is_signature_bot = serializer.validated_data.get("is_signature_bot", False)
        initial_qna = serializer.validated_data.get("initial_qna", None)

        logger.info("************************** initial_qna: {}".format(initial_qna))

        next_conversation = initialize_coaching_conversation(
            tenant=request.tenant,
            test_attempt_session_id=test_attempt_session_id,
            is_signature_bot=is_signature_bot,
            initial_qna = initial_qna
        )

        return Response(
            data=CoachingConversationDisplaySerializer(
                instance=next_conversation).data,
            status=status.HTTP_201_CREATED
        )

    @action(methods=["POST"], detail=True, url_path="reply")
    def continue_coaching_conversation_view(self, request, *args, **kwargs):
        """
        Handles the continuation of a coaching conversation.
        This view processes the participant's reply to a coaching conversation and 
        generates the next conversation step based on the provided input.
        Args:
            request: The HTTP request object containing the participant's reply data.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        Returns:
            Response: A Response object containing the serialized data of the next 
            coaching conversation step and a status code of HTTP 201 Created.
        Raises:
            ValidationError: If the provided data is invalid.
        Input Data:
            - participant_message_text (str): The text of the participant's message.
            - participant_message_url (str): The URL associated with the participant's message.
            - is_signature_bot (bool, optional): Indicates if the message is from a signature bot. Defaults to False.
            - is_prompt_only (bool, optional): Indicates if the response is prompt-only. Defaults to False.
        Logging:
            Logs the value of `is_prompt_only` for debugging purposes.
        Workflow:
            1. Validates the input data using `ReplyCoachingConversationSerializer`.
            2. Extracts relevant fields from the validated data.
            3. Calls `continue_coaching_conversation` to generate the next conversation step.
            4. Serializes the resulting conversation step using `CoachingConversationDisplaySerializer`.
            5. Returns the serialized data in the response.
        """
        
        serializer = ReplyCoachingConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant_message_text = serializer.validated_data.get(
            "participant_message_text")
        participant_message_url = serializer.validated_data.get(
            "participant_message_url")
        is_signature_bot = serializer.validated_data.get("is_signature_bot", False)
        is_prompt_only = serializer.validated_data.get("is_prompt_only", False)
        only_current_session = serializer.validated_data.get("only_current_session", False)

        
        logger.info("************************** is_prompt_only: {}".format(is_prompt_only))

        next_conversation = continue_coaching_conversation(
            tenant=request.tenant,
            reply_to_conversation=self.get_object(),
            participant_message_text=participant_message_text,
            participant_message_url=participant_message_url,
            is_signature_bot=is_signature_bot,
            is_prompt_only = is_prompt_only,
            only_current_session=only_current_session
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
        """
        Handles bot conversation data retrieval based on the request parameters.
        Args:
            request (Request): The HTTP request object containing query parameters.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        Returns:
            Response: A Response object containing bot conversation data or an error message.
        Functionality:
            - Retrieves tenant information from the request.
            - Extracts query parameters: 'for', 'user_id', and 'bot_id'.
            - Generates a cache key and checks for cached data.
            - If cached data exists, returns it with a 200 status.
            - Retrieves excluded user emails from ClientUserInfo objects.
            - Handles two modes:
                1. 'admin':
                    - Fetches bots associated with the tenant and user.
                    - Retrieves bot attributes and session data.
                    - Filters out excluded participants based on email.
                    - Constructs bot conversation data for each participant.
                    - Caches the data and returns it with a 200 status.
                2. 'user':
                    - Fetches bot IDs based on the user or all bots.
                    - Retrieves bot attributes and session data for the user.
                    - Constructs bot conversation data for the user.
                    - Caches the data and returns it with a 200 status.
            - Returns a 400 status if the 'for' parameter is invalid.
        """
        tenant = self.request.tenant
        mode = request.query_params.get('for', None)
        user_id = request.query_params.get('user_id', None)
        user_bot_id = request.query_params.get('bot_id', None)
        refresh = request.query_params.get('refresh', False)
        
        cache_key = generate_cache_key("bot-conversation-data",tenant_id=tenant.uid, mode=mode, user_id=user_id, user_bot_id=user_bot_id)
        cached_data = get_cache(cache_key)
        
        if cached_data and not refresh:
            logger.info(f"got cached data:  {cached_data}")
            return Response(cached_data, status=status.HTTP_200_OK)
        
        client_infos = ClientUserInfo.objects.all()
        excluded_users = ""
        for client_info in client_infos:
            if client_info and client_info.excluded_users:
                excluded_users += client_info.excluded_users
            
        excluded_emails = excluded_users.split(',') if excluded_users else []
        excluded_emails = [email.strip() for email in excluded_emails]

        if mode == 'admin':
            try:
                bots = SignatureBot.objects.filter(deleted=0, tenant_id=tenant.uid, user_id=user_id)
            except:
                return Response({"Bot not Found"}, status=status.HTTP_404_NOT_FOUND)
            data = []

            for bot in bots:
                bot_id = bot.uid
                bot_att = BotAttribute.objects.get(deleted=0, tenant_id=tenant.uid, bot_id=bot_id)
                sessions = TestAttemptSession.objects.filter(tenant_id=tenant.uid, deleted=0, test_id=bot_id)
                participant_ids = list(set(sessions.values_list('participant_id', flat=True)))

                for participant_id in participant_ids:
                    participant_attribute = UserAttribute.objects.filter(tenant_id=tenant.uid, user_id=participant_id).first()
                    if participant_attribute and participant_attribute.attributes:
                        participant_email = participant_attribute.attributes.get('email')
                        if participant_email in excluded_emails:
                            continue
                    bot_sessions = sessions.filter(participant_id=participant_id)
                    data_cov = get_bot_conversation_data_user(bot_sessions, tenant, participant_id)
                    data_cov['bot_name'] = bot_att.bot_name
                    data_cov['bot_id'] = bot.bot_id
                    data_cov['bot_type'] = bot.bot_type
                    data_cov['bot_scenario_case'] = bot.bot_scenario_case
                    data.append(data_cov)

            set_cache(cache_key, data)
            return Response(data, status=status.HTTP_200_OK)

        elif mode == 'user':
            bot_ids = []
            if user_bot_id:
                bot_ids = [SignatureBot.objects.get(deleted=False,bot_id=user_bot_id).uid]
            else:
                bot_ids = list(set(SignatureBot.objects.filter(deleted=0).values_list('uid', flat=True)))
            data = []
            
            for b_id in bot_ids:
                
                sessions = TestAttemptSession.objects.filter(deleted=0, tenant_id=tenant.uid, test_id=b_id,
                                                              participant_id=user_id)
                if sessions.count() == 0:
                    continue

                bot_att = BotAttribute.objects.get(deleted=0, tenant_id=tenant.uid, bot_id=b_id)
                signature_bot = SignatureBot.objects.get(deleted=False,uid=b_id)
                data_conv = get_bot_conversation_data_user(sessions, tenant, user_id)
                if len(data_conv['results']) > 0:
                    data_conv['bot_name'] = bot_att.bot_name
                    data_conv['bot_id'] = signature_bot.bot_id
                    data_conv['bot_type'] = signature_bot.bot_type
                    data_conv['bot_scenario_case'] = signature_bot.bot_scenario_case
                    data.append(data_conv)
            set_cache(cache_key,data)
            return Response(data, status=status.HTTP_200_OK)
        elif mode == 'user-chat-history':
            filtered_history = request.query_params.get('filtered_history', False)
            data = []
            bot_ids = []
            if user_bot_id:
                bot_ids = [SignatureBot.objects.get(deleted=False,bot_id=user_bot_id).uid]
            else:
                bot_ids = list(set(SignatureBot.objects.filter(deleted=0).values_list('uid', flat=True)))
            
            for b_id in bot_ids:
                
                sessions = TestAttemptSession.objects.filter(deleted=0, tenant_id=tenant.uid, test_id=b_id,
                                                              participant_id=user_id)
                if sessions.count() == 0:
                    continue

                bot_att = BotAttribute.objects.get(deleted=0, tenant_id=tenant.uid, bot_id=b_id)
                signature_bot = SignatureBot.objects.get(deleted=False,uid=b_id)
                data = get_bot_chat_history(sessions, tenant, b_id, filtered_history=filtered_history)
                # if len(data_conv) > 0:
                #     data_conv['bot_name'] = bot_att.bot_name
                #     data_conv['bot_id'] = signature_bot.bot_id
                #     data_conv['bot_type'] = signature_bot.bot_type
                #     data_conv['bot_scenario_case'] = signature_bot.bot_scenario_case
                #     data.append(data_conv)
            set_cache(cache_key,data)
            return Response(data, status=status.HTTP_200_OK)

        else:
            return Response({"Error: For parameter doesn't exist, please check"}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=False, url_path="save-ai-response")
    def save_ai_response(self, request, *args, **kwargs):
        """
    Saves an AI-generated response as the coach's message in an existing coaching conversation.

    This method updates a specific coaching conversation identified by a unique conversation ID with a new message generated by an AI. It logs the operation and handles errors by sending notifications if the specified conversation does not exist.

    Args:
        request (Request): The request object containing the POST data.
            - `conversation_id` (str): The unique identifier of the coaching conversation to be updated.
            - `ai_response` (str): The AI-generated message text to be saved as the coach's message in the conversation.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        Response: A response object indicating the success or failure of the operation.
            - On success, returns HTTP 200 with a message "Success: AI response saved".
            - On failure, particularly if the conversation is not found, returns HTTP 404 with an error message.

    Example:
        POST /coaching-conversations/save-ai-response
        Request Body:
        {
            "conversation_id": "12345",
            "ai_response": "Thank you for your question. Here's what I think..."
        }
        Response Body (Success):
        {
            "Success: AI response saved"
        }
        Response Body (Failure):
        {
            "Error: Conversation not found"
        }
    """
        conversation_id = request.data.get('conversation_id', None)
        ai_response = request.data.get('ai_response', None)
        
        logger.info(f"************************** conversation_id: {conversation_id}, ai_response: {ai_response}")

        try:
            conversation = CoachingConversation.objects.get(uid=conversation_id, deleted=0, tenant_id=request.tenant.uid)
        except Exception as e:
            send_error_notification("apis.coaching_conversations.views.save_ai_response", "Conversation not found", {"conversation_id": conversation_id})
            return Response({"Error: Conversation not found"}, status=status.HTTP_404_NOT_FOUND)

        conversation.coach_message_text = ai_response
        conversation.save()
        
        return Response({"Success: AI response saved"}, status=status.HTTP_200_OK)
    
    @action(methods=["POST",'GET'], detail=False, url_path="create-user-profile-and-bot")
    def create_user_profile_and_bot(self, request, *args, **kwargs):
        """
    Creates user profiles and bots based on the provided data in the request. This method processes multiple user and bot creation requests, formats the input data, and calls an external function to handle the creation process.

    The method logs the formatted data and handles any exceptions by logging the error and sending a notification. If successful, it returns a detailed response for each creation attempt, including whether the creation was successful, and any relevant identifiers or error messages.

    Args:
        request (Request): The Django REST framework request object that contains:
            - data (list of dict): A list of dictionaries where each dictionary represents the data required to create a user profile and bot.
            - Authorization (str): A string in the request headers used for authorization in the external API calls.

    Returns:
        Response: A Django REST framework response object that includes:
            - status (HTTP status code): The status code of the HTTP response.
            - data (list of dict): A list of dictionaries where each dictionary contains:
                - is_created (bool): Indicates if the user profile and bot were successfully created.
                - user_email (str): The email address of the created user.
                - bot_id (str): The unique identifier of the created bot.
                - user_id (str): The unique identifier of the created user.
                - profile_id (str): The unique identifier of the created profile.
                - Error (str): Any error message received during the creation process.

    Example:
        POST /coaching-conversations/create-user-profile-and-bot
        Request Headers:
        {
            "Authorization": "Bearer your_token_here"
        }
        Request Body:
        {
            "data": [
                {
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "about": "Experienced coach",
                    "experience": "10 years",
                    "area_domain": "Leadership",
                    "department": "HR",
                    "profile_type": "coach"
                }
            ]
        }
        Response Body:
        {
            "data": [
                {
                    "is_created": true,
                    "user_email": "john.doe@example.com",
                    "bot_id": "bot123",
                    "user_id": "user456",
                    "profile_id": "profile789",
                    "Error": null
                }
            ],
            "status": 200
        }
    """
        try:
            data = ""
            if request.method == 'POST':
                data = request.data.get('data')
                auth = request.headers.get('Authorization')
                logger.info(f"================data: {data}")
                tenant = request.tenant
                
                details = []
                for d in data:
                    formatted_dict = {key.strip().lower(): value for key, value in d.items()}
                    logger.info(f"===================== formatted_dict: {formatted_dict}")
                    is_created, user_data = create_user_profile_and_bot(formatted_dict,auth,tenant)
                    temp = {
                        "is_created": is_created,
                        "user_email": user_data.get('email'),
                        'bot_id' : user_data.get('bot_id'),
                        "user_id": user_data.get('user_id'),
                        "profile_id": user_data.get('profile_id'),
                        "Error": user_data.get('error')

                    }
                    
                    details.append(temp)

                return Response({'data': details},status=status.HTTP_200_OK)
            
            elif request.method == 'GET':
                filters = request.data.get('filters')
                details = fetch_user_profile_and_bot(self.request.tenant,filters)
                return Response({'data': details},status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f" Failed create_user_profile_and_bot with {e}")
            send_error_notification("apis.coaching_conversations.views.create_user_profile_and_bot", "Failed create_user_profile_and_bot", {"data": data})
            return Response({"msg": f"Failed with {e}"}, status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'], detail=False, url_path='get-deep-dive-create-access')
    def get_deep_dive_create_access(self, request, *args, **kwargs):
        """
        #### Method: `get_deep_dive_create_access`

        **Objective:**
        This method checks if a user has access to create deep dive content based on their role or membership in a client organization.

        **Process:**
        1. Checks if the request method is GET.
        2. Retrieves the user's email from the query parameters.
        3. Validates the email parameter.
        4. Retrieves the user based on the provided email using the `get_user_via_identity` function.
        5. Checks if the user's role is in a predefined list of roles or if they are a deep dive creator.
        6. Retrieves the client information and checks if the user's email is in the list of accessed emails.
        7. Returns a response indicating whether the user has access or not.

        **Input Requirements:**
        - `request`: Django REST framework request object.
        - `email`: Email address of the user to check access for.

        **Expected Output:**
        - If the email is missing: Returns a response with an error message "Email is required" and HTTP 400 status.
        - If the user has access: Returns a response with "has_access" set to True and HTTP 200 status.
        - If the user does not have access: Returns a response with "has_access" set to False and HTTP 200 status.
        - If any error occurs during the process: Returns an error response with details and HTTP 400 status.

        **Example:**
        GET /coaching-conversations/get-deep-dive-create-access?email=user@example.com
        Response Body (Success - User has access):
        {
            "has_access": true
        }
        Response Body (Success - User does not have access):
        {
            "has_access": false
        }
        Response Body (Error - Email missing):
        {
            "error": "Email is required"
        }
        Response Body (Error - Exception occurred):
        {
            "error": "Got error in deepdive-bot: <error_message>"
        }
        """
        try:
            if request.method == 'GET':
                tenant = request.tenant
                email = request.query_params.get('email')
                has_access = False


                if not email:
                    return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
                
                user = get_user_via_identity(
                    tenant=tenant,
                    identity_type= 'deepchat_unique_id',
                    identity_value=email
                )
                if user.role in ['admin', 'super_admin','client_admin', 'deep_dive_creator']:
                    return Response({"has_access": True}, status=status.HTTP_200_OK)

                client = ClientUserInfo.objects.filter(tenant_id=tenant.uid, deleted=False, member_emails__contains=email).first()
                if client:
                    
                    if client.deepdive_accessed_emails and (email in client.deepdive_accessed_emails):
                        has_access = True
                        

                return Response({"has_access": has_access}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Got error in deepdive-bot: {e}")
            return Response({"error": f"Got error in deepdive-bot: {e}"}, status=status.HTTP_400_BAD_REQUEST)



    @action(methods=["POST"], detail=False, url_path="save-response-style")
    def save_response_style(self, request, *args, **kwargs):
        """
        #### Method: `save_response_style`

        **Objective:**
        This method saves the preferred response style for a user by updating the `preferences` field in the `UserAttribute` model.

        **Process:**
        1. Retrieves the `user_id` and `response_style` from the request data.
        2. Validates the presence of both `user_id` and `response_style`.
        3. Retrieves the `UserAttribute` instance based on the `tenant_id`, `user_id`, and ensures it is not deleted.
        4. Updates the `preferences` field with the new `response_style`.
        5. Saves the changes to the `UserAttribute` instance.

        **Input Requirements:**
        - `request`: Django REST framework request object.
        - `user_id`: The unique identifier of the user.
        - `response_style`: The preferred response style to be saved.

        **Expected Output:**
        - On successful update, returns a response with a message "response style saved".
        - If either `user_id` or `response_style` is missing, returns an error response with details.
        - If any error occurs during the process, returns an error response indicating the issue.

        **Example:**
        POST /coaching-conversations/save-response-style
        Request Body:
        {
            "user_id": "12345",
            "response_style": "friendly"
        }
        Response Body (Success):
        {
            "message": "response style saved"
        }
        Response Body (Error - Missing Fields):
        {
            "error": "both user_id and response_style fields are required"
        }
        Response Body (Error - Exception):
        {
            "error": "something went wrong"
        }
        """
        try:
            user_id = request.data.get('user_id')
            response_style = request.data.get('response_style')
            
            if user_id is None or response_style is None:
                return  Response({"error": "both user_id and response_style fields are required"}, status=status.HTTP_400_BAD_REQUEST)
            
            user_attributes = UserAttribute.objects.get(tenant_id=request.tenant.uid,user_id=user_id,deleted=False)
            user_attributes.preferences = { 'response_style' : response_style}
            user_attributes.save()
            return Response({"message":"response style saved"})
        except Exception as e:
            logger.exception(e)
            return Response({"error": "something went wrong"}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['POST'], detail=False, url_path='team-connect')
    def team_connect(self, request, *args, **kwargs):
        """
        #### Method: `team_connect`

        **Objective:**
        This method generates a response for team connection based on user profiles and characteristics.

        **Process:**
        1. Receives the `tenant_id`, `user_ids`, and `question` as input.
        2. Retrieves user data and profiles based on the provided `user_ids`.
        3. Constructs a response message with user profile information and the input question.
        4. Generates a response using the constructed prompt and user data.
        5. Returns the response message along with any additional information.

        **Input Requirements:**
        - `tenant_id`: The ID of the tenant.
        - `user_ids`: Comma-separated user IDs for whom to generate the response.
        - `question`: The question for which the response is generated.

        **Expected Output:**
        - A response message containing the generated response for team connection.
        - Additional messages or information based on the user profiles.
        - Error messages if any input is missing or if an exception occurs.

        **Example:**
        POST /coaching-conversations/team-connect
        Request Body:
        {
            "user_id": "12345",
            "question": "How can we improve team collaboration?"
        }
        Response Body (Success):
        {
            "response": "Generated response for team connection",
            "message": "Additional message based on user profiles"
        }
        Response Body (Error - Missing Fields):
        {
            "error": "user_id is required"
        }
        Response Body (Error - Exception):
        {
            "error": "Got error in team_connect: <error_message>"
        }
        """
        try:
            if request.method == 'POST':
                tenant = request.tenant
                user_id = request.data.get('user_id')
                question = request.data.get('question')
                if not user_id:
                    return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
                response = generate_team_connect_response(
                    tenant_id=tenant.uid, 
                    user_ids=user_id,
                    question=question
                )
                return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Got error in team_connect: {e}")
            return Response({"error": f"Got error in team_connect: {e}"}, status=status.HTTP_400_BAD_REQUEST)


    @action(methods=['GET'], detail=False, url_path='analyze-bot-conversation')
    def analyze_bot_conversation(self, request, *args, **kwargs):
        """
        #### Method: `analyze_bot_conversation`

        **Objective:**
        This method aims to analyze bot conversations for a specific user in a test attempt session by retrieving relevant data.

        **Process:**
        1. Checks if the request method is GET.
        2. Retrieves the `tenant`, `user_id`, and `bot_id` from the query parameters.
        3. Validates the presence of both `user_id` and `bot_id`.
        4. Retrieves test attempt sessions based on the `tenant`, `user_id`, and `bot_id`.
        5. If no sessions are found, returns an error response.
        6. Calls the `get_bot_conversation_data_user` function to fetch conversation data.
        7. Returns a response with the conversation data if successful.

        **Input Requirements:**
        - `request`: Django REST framework request object.
        - `user_id`: The ID of the user for whom to analyze bot conversations.
        - `bot_id`: The ID of the bot associated with the conversations.

        **Expected Output:**
        - If successful, returns a response with the conversation data and HTTP 200 status.
        - If either `user_id` or `bot_id` is missing, returns an error response with details and HTTP 400 status.
        - If no conversations are found, returns an error response with details and HTTP 404 status.

        **Example:**
        GET /coaching-conversations/analyze-bot-conversation?user_id=12345&bot_id=67890
        Response Body (Success):
        {
            "results": [
                {
                    "uid": "conversation123",
                    "coach_message_text": "Hello, how can I help you?",
                    "participant_message_text": "I have a question.",
                    "status": "participant_message_saved",
                    "created": "2022-01-01T00:01:00Z",
                    "updated": "2022-01-01T00:01:00Z",
                    "session_id": "session456"
                }
            ],
            "participant_name": "John Doe",
            "participant_uid": "12345",
            "role": "user",
            "date": "2022-01-01T00:00:00Z"
        }
        Response Body (Error - Missing Fields):
        {
            "error": "user_id and bot_id are required"
        }
        Response Body (Error - No Conversation Found):
        {
            "error": "No conversation found"
        }
        Response Body (Error - Exception):
        {
            "error": "Got error in analyze_bot_conversation: <error_message>"
        }
        """
        ### :TODO: incomplete implementation
        try:
            if request.method == 'GET':
                tenant = request.tenant
                user_id = request.query_params.get('user_id')
                bot_id = request.query_params.get('bot_id')
                if not user_id or not bot_id:
                    return Response({"error": "user_id and bot_id are required"}, status=status.HTTP_400_BAD_REQUEST)
                sessions = TestAttemptSession.objects.filter(tenant_id=tenant.uid, deleted=0, test_id=bot_id, participant_id=user_id)
                if sessions.count() == 0:
                    return Response({"error": "No conversation found"}, status=status.HTTP_404_NOT_FOUND)
                data = get_bot_conversation_data_user(sessions, tenant, user_id)
                return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Got error in analyze_bot_conversation: {e}")
            return Response({"error": f"Got error in analyze_bot_conversation: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(methods=['GET','POST'], detail=False, url_path='get-or-save-coach-recommendations')
    def get_or_save_coach_recommendations(self, request, *args, **kwargs):
        """
        ### Method: `get_or_save_coach_recommendations`

        **Objective:**
        This method retrieves or saves coach recommendations for a user profile based on the request method. It aims to efficiently handle caching for recommendations retrieval and storage.

        **Process:**
        1. For GET requests:
            - Retrieves the `user_profile_id` from query parameters.
            - Generates a cache key for coach recommendations.
            - Tries to fetch data from the cache.
            - If cache miss, retrieves the user profile and associated recommendations.
            - Sets the retrieved data in the cache and returns the recommendations.

        2. For POST requests:
            - Extracts `user_profile_id` and `coach_recommendations` from the request data.
            - Validates the presence of both fields.
            - Calls the `save_coach_recommendation` function to save the recommendations.
            - Returns a success message if the saving is successful.

        **Input Requirements:**
        - For GET:
            - `user_profile_id`: The ID of the user profile to retrieve recommendations for.
        - For POST:
            - `user_profile_id`: The ID of the user profile to save recommendations for.
            - `coach_recommendations`: The recommendations to be saved.

        **Expected Output:**
        - For GET:
            - Returns coach recommendations data if found in cache or database.
        - For POST:
            - Success message if recommendations are saved successfully.

        **Example:**
        GET /coaching-conversations/get-or-save-coach-recommendations?user_profile_id=12345
        Response Body (Success - GET):
        {
            "data": ["Recommendation 1", "Recommendation 2"]
        }

        POST /coaching-conversations/get-or-save-coach-recommendations
        Request Body:
        {
            "user_profile_id": "12345",
            "coach_recommendations": "Recommendation 1, Recommendation 2"
        }
        Response Body (Success - POST):
        {
            "success": "coach recommendation saved for user_profile_id- 12345"
        }
        """
        try:
            if request.method == 'GET':
                user_profile_id = request.query_params.get('user_profile_id')
                cache_key = generate_cache_key('coach_recommendations', user_profile_id)

                # Try to get data from cache
                cached_data = get_cache(cache_key)
                if cached_data:
                    return Response({"data": cached_data}, status=status.HTTP_200_OK)
        
                try:
                    profile = CoachCoacheeMentorMenteeProfile.objects.get(
                        deleted=False,
                        tenant_id=request.tenant.uid,
                        uid=user_profile_id
                    )
                    recommendations = profile.coach_recommendations.all()
                    response_data = recommendations[0].coach_recommendations.split(',') if recommendations else []
                    
                    # Set data in cache
                    set_cache(cache_key, response_data)
                    
                    # Return the response
                    return Response({"data": response_data}, status=status.HTTP_200_OK)
                except Exception as e:
                    return Response({"error": f"Profile Not found for user_profile_id : {user_profile_id}, reason: {e}"}, status=status.HTTP_400_BAD_REQUEST)

            elif request.method == 'POST':
                user_profile_id = request.data.get('user_profile_id')
                coach_recommendations = request.data.get('coach_recommendations',None)
                logger.info(f"user_profile_id: {user_profile_id}, coach_recommendations: {coach_recommendations}")

                if not user_profile_id or not coach_recommendations:
                    return Response({'error': f"Either user_profile_id or coach_recommendations is missing!"},status=status.HTTP_400_BAD_REQUEST)
                
                msg, success = save_coach_recommendation(
                    user_profile_id=user_profile_id,
                    coach_recommendations=coach_recommendations
                )
                return Response(msg, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(f"Got error in get_or_save_coach_recommendations: {e}")
            return Response({"error": f"Got error in get_or_save_coach_recommendations: {e}"}, status=status.HTTP_400_BAD_REQUEST)


    @action(methods=['GET'], detail=False, url_path='get-attempted-bots')
    def get_attempted_bots(self,request, *args, **kwargs):
        """
        Retrieves a list of bots that a user has attempted, along with the participant's message, name, and date of the attempt.

        Args:
            request (Request): The request object containing the GET data.
            user_id (str): The ID of the user for whom to retrieve the attempted bots.
            only_feedback (bool, optional): A flag indicating whether to return only feedback bots. Defaults to False.

        Returns:
            Response: A response object containing a list of attempted bots.

        Example:
            GET /coaching-conversations/get-attempted-bots?user_id=12345

        Response Body:
        [
            {
                "participant_name": "John Doe",
                "date": "2022-01-01T00:00:00Z",
                "msg": "Hello, how can I help you?",
                "participant_id": "12345",
                "is_anonymous": false
            },
            {
                "participant_name": "Jane Doe",
                "date": "2022-01-02T00:00:00Z",
                "msg": "I have a question.",
                "participant_id": "56789",
                "is_anonymous": true
            }
        ]
        """

        try:
            if request.method == 'GET':
                data = []
                user_id = request.query_params.get('user_id')
                only_feedback_bots = request.query_params.get('only_feedback',False)
                only_feedback_bots = True if only_feedback_bots in ['True','true',True,0] else False
                if not user_id:
                    return Response({'error': 'User ID is missing'}, status=status.HTTP_400_BAD_REQUEST)
                
                if only_feedback_bots:
                    qnas = BotQnA.objects.filter(tenant_id=self.request.tenant.uid,deleted=False,participant_id=user_id,qna_type='feedback')
                    for qna in qnas:
                        try:
                            participant_name = get_user_display_name(
                                get_user_by_id(user_id))
                            bot = SignatureBot.objects.filter(uid=qna.bot_id,deleted=False).first()
                            coach_name = "Unknown"
                            if bot:
                                coach_name =  get_user_display_name(
                                    get_user_by_id(bot.user_id))
                            else:
                                logger.exception(f"Bot Not found: {qna.bot_id}")
                                continue
                        except: 
                            logger.exception(f"Error getting user name: {user_id}")
                            continue

                        data.append({
                                "participant_name": participant_name,
                                "date": qna.created,
                                "msg": qna.participant_qna,
                                "participant_id": qna.participant_id,
                                "is_anonymous": qna.is_anonymous,
                                "coach_name": coach_name,
                                "bot_uid": qna.bot_id,
                                "bot_id": bot.bot_id
                            })




                return Response(data,status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'msg': f'failed with error {e}'}, status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'], detail=False, url_path='get-response-style-list')
    def get_response_style_list(self, request, *args, **kwargs):
        try:
            names = BotResponsePrompt.objects.filter(
                deleted=False,
                tenant_id=request.tenant.uid
            ).values_list('name', 'normalized_name')

            data = {name: normalized for name, normalized in names}

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Error in get_response_style_list")
            return Response(
                {'msg': f'failed with error {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    @action(methods=['GET', 'POST'], detail=False, url_path='coaching-intake')
    def coaching_intake(self, request, *args, **kwargs):
        try:
            # here we will consider intake for a participant 
            if request.method == 'GET':
                user_id = request.query_params.get('user_id')
                if not user_id:
                    return Response(f"user_id required.", status=status.HTTP_400_BAD_REQUEST)

                qna = BotQnA.objects.filter(deleted=False, participant_id=user_id, qna_type='coaching_intake').first()
                if not qna:
                    return Response(f"Intake not found for the user- {user_id}!", status=status.HTTP_404_NOT_FOUND)
                data={
                    'qna': qna.participant_qna,
                    'intake_summary': qna.intake_summary,
                    'qna_type': 'coaching_intake'
                }
                return Response(data, status=status.HTTP_200_OK)
            elif request.method == 'POST':
                user_id = request.data.get('user_id')
                qna = request.data.get('qna')
                qna = BotQnA.objects.create(
                    tenant_id=request.tenant.uid,
                    participant_id=user_id,
                    qna_type='coaching_intake',
                    participant_qna=qna
                )
                return Response(f"coaching intake submitted!", status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.exception("Error in coaching_intake")
            return Response(
                {'msg': f'failed with error {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        


    @action(methods=["POST"], detail=False, url_path="generate")
    def generate_gemini_response(self, request, *args, **kwargs):
        """
        Generates a response from the Gemini API based on the user's prompt.

        Expects the following fields in the request data:
        - `prompt` (str, required): The text prompt to send to Gemini.
        - `model` (str, optional): The model to use (default "gemini-2.0-flash-001").
        - `instruction` (str, optional): Any system instruction to guide the model.

        Returns:
            Response: A JSON response containing the generated text.
        """
        serializer = GeminiPromptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prompt = serializer.validated_data["prompt"]
        model = serializer.validated_data.get("model", "gemini-2.0-flash-001")
        instruction = serializer.validated_data.get("instruction", None)

        logger.info(f"Generating Gemini response for prompt: {prompt}")

        # response_text = gemini_streaming_completion(
        #     prompt=prompt,
        #     model=model,
        #     instruction=instruction
        # )

        try:
            # join chunks into final string
            response_text = "".join(
                str(chunk) for chunk in gemini_streaming_completion(
                    prompt=prompt, model=model, instruction=instruction
                )
            )
        except Exception as e:
            logger.error(f"Error while generating response: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            data={"response": response_text},
            status=status.HTTP_201_CREATED
        )