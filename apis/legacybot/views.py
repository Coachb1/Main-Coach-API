from rest_framework import viewsets, status
from legacybot.models import LegacyBot, LegacyBotUser, Thread, ChatConversation
from .serializers import LegacyBotSerializer, LegacyBotUserSerializer, ThreadSerializer, ChatConversationSerializer
from clients.permissions import IsAuthenticatedClient
from rest_framework.response import Response
from rest_framework.decorators import action
from collections import defaultdict
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
        if domain is not None:
            queryset = queryset.filter(domain=domain)
        return queryset

    

class LegacyBotUserViewSet(viewsets.ModelViewSet):
    queryset = LegacyBotUser.objects.filter(deleted=False)
    serializer_class = LegacyBotUserSerializer
    permission_classes = (IsAuthenticatedClient,)


    def get_queryset(self):
        queryset = super().get_queryset()
        email = self.request.query_params.get('email', None)
        bot_id = self.request.query_params.get('bot_id', None)

        if email is not None and bot_id is not None:
            queryset = queryset.filter(email=email,bot_id=bot_id)
        elif email is not None:
            queryset = queryset.filter(email=email)
        elif bot_id is not None:
            queryset = queryset.filter(bot_id=bot_id)

        return queryset


class ThreadViewSet(viewsets.ModelViewSet):
    queryset = Thread.objects.filter(deleted=False)
    serializer_class = ThreadSerializer
    permission_classes = (IsAuthenticatedClient,)

    def get_queryset(self):
        queryset = super().get_queryset()
        thread_id = self.request.query_params.get('thread_id', None)
        bot_id = self.request.query_params.get('bot_id', None)

        if thread_id:
            queryset = queryset.filter(thread_id=thread_id)
        if bot_id:
            queryset = queryset.filter(bot_id = bot_id)

        return queryset


class ChatConversationViewSet(viewsets.ModelViewSet):
    queryset = ChatConversation.objects.filter(deleted=False)
    serializer_class = ChatConversationSerializer
    permission_classes = (IsAuthenticatedClient,)

    def list(self, request):
        queryset = self.queryset
        user_id = self.request.query_params.get('user_id', None)
        thread_id = self.request.query_params.get('thread_id', None)

        if user_id:
            # Filter chat conversations by user_id
            threads = Thread.objects.filter(user_id=user_id)
            thread_ids = list(threads.values_list('uid',flat=True))
            conversations = queryset.filter(thread_id__in=thread_ids)
            

            # Format the response
            response_data = defaultdict(list)
            for conversation in conversations:
                response_data[conversation.thread_id].append(ChatConversationSerializer(conversation).data)

            return Response({user_id:response_data}, status=status.HTTP_200_OK)
        
        elif thread_id:
            # Filter chat conversations by user_id
            thread = Thread.objects.get(uid=thread_id)
            conversations = queryset.filter(thread_id=thread.uid)
            # Format the response
            response_data = defaultdict(list)
            for conversation in conversations:
                response_data[conversation.thread_id].append(ChatConversationSerializer(conversation).data)

            return Response({thread.user_id:response_data}, status=status.HTTP_200_OK)

        return Response({"data":ChatConversationSerializer(queryset,many=True).data},status=status.HTTP_200_OK)

