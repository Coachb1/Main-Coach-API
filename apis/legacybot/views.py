from rest_framework import viewsets, status
from legacybot.models import LegacyBot, LegacyBotUser, Thread, ChatConversation
from .serializers import LegacyBotSerializer, LegacyBotUserSerializer, ThreadSerializer, ChatConversationSerializer
from clients.permissions import IsAuthenticatedClient
from rest_framework.response import Response
from rest_framework.decorators import action
from collections import defaultdict
from legacybot.helpers import get_or_generate_action_data
import logging

logger = logging.getLogger("main")


class LegacyBotViewSet(viewsets.ModelViewSet):
    queryset = LegacyBot.objects.filter(deleted=False)
    serializer_class = LegacyBotSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"

    def get_queryset(self):
        queryset = super().get_queryset()
        domain = self.request.query_params.get('domain', None)
        bot_identifier = self.request.query_params.get('bot_identifier',None)
        
        if domain is not None:
            queryset = queryset.filter(domain=domain)
        if bot_identifier is not None:
            queryset = queryset.filter(bot_identifier=bot_identifier)

        return queryset
    

    @action(methods=['GET'], detail=False, url_path="threads-and-conversations")
    def get_threads_and_conversations(self, request, *args, **kwargs):
        bot_id = self.request.query_params.get('bot_id')
        if not bot_id:
            return Response({'detail': "Parameters 'bot_id' is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Validate the bot exists
            bot = LegacyBot.objects.get(uid=bot_id, deleted=False)
            
            response_data = self.get_thread_conversation_for_thread(bot_id=bot_id)

            return Response(response_data, status=status.HTTP_200_OK)

        except LegacyBot.DoesNotExist:
            return Response({'detail': f"No bot found with the id {bot_id}"}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.exception(f"Error in fetching threads and conversations: {e}")
            return Response({'error': f"Failed to fetch threads and conversations: {e}"}, status=status.HTTP_400_BAD_REQUEST)
    
    
    def get_thread_conversation_for_thread(self,bot_id):
        # Fetch threads associated with the bot
        threads = Thread.objects.filter(bot_id=bot_id, deleted=False)
        
        # Fetch all users for the threads and map them by user_id
        user_ids = {thread.user_id for thread in threads}
        users = LegacyBotUser.objects.filter(uid__in=user_ids, deleted=False)
        # user_data_map = {user.uid: LegacyBotUserSerializer(user).data for user in users}
        
        # Fetch conversations in bulk and group by thread_id
        conversations = ChatConversation.objects.filter(
            deleted=False, thread_id__in=[thread.uid for thread in threads]
        ).order_by('created')
        conversations_by_thread = defaultdict(list)
        for conversation in conversations:
            conversations_by_thread[conversation.thread_id].append(conversation)
        
        logger.info(f"conversations: {conversations_by_thread}")
        # Prepare the response data
        response_data = {user.uid: {'user_info': LegacyBotUserSerializer(user).data, 'threads': {}} for user in users}
        for thread in threads:
            temp_info = {
                "thread_info": ThreadSerializer(thread).data,
                "conversations": ChatConversationSerializer(conversations_by_thread[thread.uid], many=True).data
            }

            logger.info(f"user-thread_info: {temp_info}")
            response_data[thread.user_id]['threads'][thread.uid] = temp_info

        return response_data


class LegacyBotUserViewSet(viewsets.ModelViewSet):
    queryset = LegacyBotUser.objects.filter(deleted=False)
    serializer_class = LegacyBotUserSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"

    def get_queryset(self):
        queryset = super().get_queryset()
        email = self.request.query_params.get('email', None)
        bot_id = self.request.query_params.get('bot_id', None)
        user_id = self.request.query_params.get('user_id', None)

        if user_id:
            queryset = queryset.filter(uid=user_id)

        else:
            if email is not None and bot_id is not None:
                queryset = queryset.filter(email=email,bot_id=bot_id)
            elif email is not None:
                queryset = queryset.filter(email=email)
            elif bot_id is not None:
                queryset = queryset.filter(bot_id=bot_id)

        return queryset
    
    def create(self, request, *args, **kwargs):
        email = request.data.get('email')
        name = request.data.get('name')
        if not email or not name:
            return Response({"detail": "'email', 'name' are required."}, status=status.HTTP_400_BAD_REQUEST)
        # Check if the record already exists
        existing_user = LegacyBotUser.objects.filter(email=email,deleted=False).first()

        if existing_user:
            logger.info(f"User with email {email} already exists.")  # If existing_user is found
            # If it exists, return the existing record
            serializer = self.get_serializer(existing_user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        logger.info(f"Creating a new user with email {email}.")  # If creating a new user
        return super().create(request, *args, **kwargs)
    
    @action(methods=['GET'], detail=False, url_path="get-bot-by-user")
    def get_bot_by_user(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id', None)
        if not user_id:
            return Response({"detail": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = LegacyBotUser.objects.get(uid=user_id)
            bots = LegacyBot.objects.filter(creator=user, deleted=False)
            serializer = LegacyBotSerializer(bots, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error getting bot by user : {e}")
            return Response({'detail': f"Error getting bot by user"}, status=status.HTTP_400_BAD)
            



class ThreadViewSet(viewsets.ModelViewSet):
    queryset = Thread.objects.filter(deleted=False)
    serializer_class = ThreadSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"

    def get_queryset(self):
        queryset = super().get_queryset()
        thread_id = self.request.query_params.get('thread_id', None)
        asst_thread_id = self.request.query_params.get('asst_thread_id', None)
        bot_id = self.request.query_params.get('bot_id', None)
        user_id = self.request.query_params.get('user_id',None)

        if thread_id:
            queryset = queryset.filter(uid=thread_id)
        if asst_thread_id:
            queryset = queryset.filter(thread_id=asst_thread_id)
        if bot_id:
            queryset = queryset.filter(bot_id = bot_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset
    
    def create(self, request, *args, **kwargs):
        bot_id = request.data.get('bot_id')
        try:
            LegacyBot.objects.get(uid=bot_id)
        except Exception as e:
            logger.exception(f"no bot found : {e}")
            return Response({'detail': f"No bot found with the {bot_id}"}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    @action(methods=['POST'], detail=False, url_path="action-report-data")
    def action_report_data(self, request, *args, **kwargs):
        if request.method != 'POST':
            return Response({'error': 'Invalid request method.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        
        try:
            thread_id = request.data.get('thread_id')
            thread_ids = request.data.get('threads')
            user_id = request.data.get('user_id')

            if thread_id:
                return self._get_action_data_by_thread_id(thread_id)
            elif thread_ids:
                return self._get_action_data_by_thread_ids(thread_ids)
            elif user_id:
                bot_id = request.data.get('bot_id',None)
                return self._get_action_data_by_user_id(user_id,bot_id=bot_id)
            else:
                return Response({'error': 'Invalid or missing parameters.'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(f"Failed to process action_report_data: {e}")
            return Response({'error': f"Failed to process action_report_data: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_action_data_by_thread_id(self, thread_id):
        try:
            threads = Thread.objects.filter(deleted=False, uid=thread_id)
            data = get_or_generate_action_data(threads=threads)
            return Response({'data': data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Failed to get action data by thread_id: {e}")
            return Response({'error': f"Failed to get action data by thread_id: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    def _get_action_data_by_thread_ids(self, thread_ids):
        try:
            thread_ids_list = [th.strip() for th in thread_ids.split(',') if th.strip()]
            threads = Thread.objects.filter(deleted=False, uid__in=thread_ids_list)
            data = get_or_generate_action_data(threads=threads)
            return Response({'data': data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Failed to get action data by thread_ids: {e}")
            return Response({'error': f"Failed to get action data by thread_ids: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    def _get_action_data_by_user_id(self, user_id,bot_id=None):
        try:
            threads = Thread.objects.filter(deleted=False, user_id=user_id)
            if bot_id:
                threads = threads.filter(bot_id=bot_id)
            data = get_or_generate_action_data(threads=threads)
            return Response({'data': data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Failed to get action data by user_id: {e}")
            return Response({'error': f"Failed to get action data by user_id: {e}"}, status=status.HTTP_400_BAD_REQUEST)


class ChatConversationViewSet(viewsets.ModelViewSet):
    queryset = ChatConversation.objects.filter(deleted=False)
    serializer_class = ChatConversationSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"


    def list(self, request):
        queryset = self.queryset
        user_id = self.request.query_params.get('user_id', None)
        thread_id = self.request.query_params.get('thread_id', None)
        bot_id = self.request.query_params.get('bot_id',None)

        if user_id:
            # Filter chat conversations by user_id
            filter_data = {
                'user_id': user_id,
                'deleted': False

            }
            if bot_id:
                filter_data['bot_id'] = bot_id
            threads = Thread.objects.filter(**filter_data)
            
            # Format the response
            response_data = defaultdict(list)
            for thread in threads:
                
                conversations = ChatConversation.objects.filter(deleted=False,thread_id=thread.uid)
                response_data[thread.uid].append(
                    {
                        "thread_info": ThreadSerializer(thread).data,
                        "conversations": ChatConversationSerializer(conversations,many=True).data
                    }
                    )

            return Response({user_id:response_data}, status=status.HTTP_200_OK)
        
        elif thread_id:
            # Filter chat conversations by user_id
            thread = Thread.objects.get(uid=thread_id)
            conversations = queryset.filter(thread_id=thread.uid)
            # Format the response
            response_data = defaultdict(list)
            for conversation in conversations:
                response_data[conversation.thread_id].append(ChatConversationSerializer(conversation,many=True).data)

            return Response({thread.user_id:response_data}, status=status.HTTP_200_OK)

        return Response({"data":ChatConversationSerializer(queryset,many=True).data},status=status.HTTP_200_OK)

