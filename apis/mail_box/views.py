from commons.viewset import ApiViewSet
from rest_framework import mixins, status
from rest_framework.response import Response
from mail_box.models import MailBox, AuthorizedEmails, EmailConversation, AccountabilityIntake
from apis.mail_box.serializers import MailBoxViewSerializer, AuthorizedEmailsSerializer, EmailConversationSerializer, AccountabilityIntakeSerializer
from clients.permissions import IsAuthenticatedClient
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from mail_box.choices import FollowupFreqType
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
        form_id = self.request.query_params.get('form_id')

        if uid:
            queryset = queryset.filter(uid=uid)
        elif email:
            queryset = queryset.filter(email=email)
        elif form_id:
            queryset = queryset.filter(intake_url__contains=form_id)
        
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
        mailbox_id = self.request.query_params.get('mailbox_id')
        
        if uid:
            queryset = queryset.filter(uid=uid)
        elif email:
            queryset = queryset.filter(email=email)

        if mailbox_id:
            queryset = queryset.filter(mailbox_id=mailbox_id)
        
        return queryset
    
    @action(methods=['GET','POST','PATCH'], detail=False, url_path='user-intake')
    def user_intake(self,request,*args,**kwargs):
        try:
            if request.method == 'GET':
                user_email = request.query_params.get('email')
                mailbox_id = request.query_params.get('mailbox_id')
                user = AuthorizedEmails.objects.filter(email=user_email,mailbox_id=mailbox_id).exclude(name=None).last()
                return Response(AuthorizedEmailsSerializer(user).data , status=status.HTTP_200_OK)
            
            elif request.method == 'POST':
                logger.info(f" creating intake : {request.data}")
                user_email = request.data.get('email')
                mailbox_id = request.data.get('mailbox_id')
                name = request.data.get('name')
                age = request.data.get('age')
                situation = request.data.get('situation')
                goal = request.data.get('goal')
                is_reward_email = request.data.get('is_reward_email', True)
                followup_freq = request.data.get('followup_freq', FollowupFreqType.never)
                followup_esc_email = request.data.get('followup_esc_email')

                user = AuthorizedEmails.objects.filter(email=user_email,mailbox_id=mailbox_id).last()
                if user:
                    user.name = name
                    user.age = age
                    user.situation = situation
                    user.goal = goal 
                    user.followup_escalation_email = followup_esc_email
                    user.followup_fequency = FollowupFreqType.get_choice(followup_freq)
                    user.reward_emails = is_reward_email

                    user.save()

                return Response({'msg': "successfully created"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"Got Error in user intake: {e}")
            return Response({'error': f"failed to perform user intake : {e}"}, status= status.HTTP_400_BAD_REQUEST)

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


class AccountabilityIntakeViewSet(ApiViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin):
    queryset = AccountabilityIntake.objects.filter(deleted=0)
    serializer_class = AccountabilityIntakeSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"

    def get_queryset(self):
        queryset = super().get_queryset()
        uid = self.request.query_params.get('uid')
        form_id = self.request.query_params.get('form_id')
        email_address = self.request.query_params.get('email_address')
        
        filters = {}
        if uid:
            filters['uid'] = uid
        elif form_id:
            filters['form_id'] = form_id
        if email_address:
            filters['email_address'] = email_address

        if not filters:
            return queryset

        queryset = queryset.filter(**filters)
        return queryset

    def perform_create(self, serializer):
        logger.info(f"Creating a new accountability intake with data: {serializer.validated_data}")
        try:
            serializer.save()
            logger.info("Accountability intake created successfully")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating accountability intake: {str(e)}")
            raise e