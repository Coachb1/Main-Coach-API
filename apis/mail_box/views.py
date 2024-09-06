from commons.viewset import ApiViewSet
from rest_framework import mixins
from mail_box.models import MailBox, AuthorizedEmails, EmailConversation
from apis.mail_box.serializers import MailBoxViewSerializer, AuthorizedEmailsSerializer, EmailConversationSerializer
from clients.permissions import IsAuthenticatedClient
import logging

logger = logging.getLogger("main")

class MailBoxViewSet(ApiViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin):
    queryset = MailBox.objects.filter(deleted=0)
    serializer_class = MailBoxViewSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"
    

    def get_queryset(self):
        """
        Optionally restricts the returned queryset by filtering against
        a `uid` or `email` query parameter in the URL.
        """
        queryset = super().get_queryset()
        uid = self.request.query_params.get('uid')
        email = self.request.query_params.get('email')
        if uid:
            queryset = queryset.filter(uid=uid)
        elif email:
            queryset = queryset.filter(email=email)
        
        return queryset
    
    def perform_create(self, serializer):
        logger.info(f"Creating a new mailbox with data: {serializer.validated_data}")
        try:
            serializer.save()
            logger.info("mailbox created successfully")
        except Exception as e:
            logger.error(f"Error creating mailbox: {str(e)}")
            raise e

class AuthorizedEmailsViewSet(ApiViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin):
    queryset = AuthorizedEmails.objects.filter(deleted=0)
    serializer_class = AuthorizedEmailsSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"    

    def get_queryset(self):
        queryset = super().get_queryset()
        uid = self.request.query_params.get('uid')
        email = self.request.query_params.get('email')
        
        if uid:
            queryset = queryset.filter(uid=uid)
        elif email:
            queryset = queryset.filter(email=email)
        
        return queryset

class EmailConversationViewSet(ApiViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin):
    queryset = EmailConversation.objects.filter(deleted=0)
    serializer_class = EmailConversationSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"

    def get_queryset(self):
        queryset = super().get_queryset()
        uid = self.request.query_params.get('uid')
        mailbox_id = self.request.query_params.get('mailbox_id')
        subject = self.request.query_params.get('subject')
        
        filters = {}
        if uid:
            filters['uid'] = uid
        elif mailbox_id:
            filters['mailbox_id'] = mailbox_id
        if subject:
            filters['subject'] = subject

        if not filters:
            return queryset

        queryset = queryset.filter(**filters)
        return queryset

    def perform_create(self, serializer):
        logger.info(f"Creating a new email conversation with data: {serializer.validated_data}")
        try:
            serializer.save()
            logger.info("Email conversation created successfully")
        except Exception as e:
            logger.error(f"Error creating email conversation: {str(e)}")
            raise e
