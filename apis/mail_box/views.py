from commons.viewset import ApiViewSet
from rest_framework import mixins, status
from rest_framework.response import Response
from mail_box.models import MailBox, AuthorizedEmails, EmailConversation, AccountabilityIntake
from rest_framework import serializers
from apis.mail_box.serializers import MailBoxViewSerializer, AuthorizedEmailsSerializer, EmailConversationSerializer, AccountabilityIntakeSerializer
from clients.permissions import IsAuthenticatedClient
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from mail_box.choices import FollowupFreqType
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer
import logging

logger = logging.getLogger("main")

@extend_schema(tags=["Mailbox"])
@extend_schema_view(
    list=extend_schema(
        summary="List Mailboxes",
        description="Fetches a list of all mailboxes. You can filter the results using the query parameters below.",
        parameters=[
            OpenApiParameter("uid", str, description="Filter by the unique identifier (UID) of the mailbox."),
            OpenApiParameter("email", str, description="Filter by the email address associated with the mailbox."),
            OpenApiParameter("form_id", str, description="Filter by the form ID found within the intake URL."),
        ]
    ),
    retrieve=extend_schema(
        summary="Retrieve a Mailbox",
        description="Fetches details of a specific mailbox by its UID."
    ),
    create=extend_schema(summary="Create a Mailbox", description="Creates a new mailbox."),
    update=extend_schema(summary="Update a Mailbox", description="Updates an existing mailbox."),
    partial_update=extend_schema(
        summary="Partially Update a Mailbox",
        description="Partially updates an existing mailbox."
    ),
)
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

@extend_schema(tags=["Mailbox - Authorized Emails"])
@extend_schema_view(
    list=extend_schema(
        summary="List Authorized Emails",
        description="Fetches a list of authorized emails. Use query parameters to filter specific users.",
        parameters=[
            OpenApiParameter("uid", str, description="Filter by the unique identifier (UID) of the authorized email entry."),
            OpenApiParameter("email", str, description="Filter by the user's email address."),
            OpenApiParameter("mailbox_id", str, description="Filter by the associated Mailbox UID."),
        ]
    ),
    retrieve=extend_schema(
        summary="Retrieve an Authorized Email",
        description="Fetches details of a specific authorized email by its UID."
    ),
    create=extend_schema(summary="Create an Authorized Email", description="Authorizes a new email for a mailbox."),
    update=extend_schema(summary="Update an Authorized Email", description="Updates an existing authorized email."),
    partial_update=extend_schema(
        summary="Partially Update an Authorized Email",
        description="Partially updates an existing authorized email."
    ),
)
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
    
    @extend_schema(
        summary="Manage User Intake",
        description="**GET**: Retrieve user intake data using `email` and `mailbox_id`.\n\n**POST/PATCH**: Create or update user intake information. Note: The user must already exist (matched by email and mailbox_id) for the update to take effect.",
        parameters=[
            OpenApiParameter("email", str, description="User's email address (Required for GET)", location=OpenApiParameter.QUERY),
            OpenApiParameter("mailbox_id", str, description="Mailbox UID (Required for GET)", location=OpenApiParameter.QUERY),
        ],
        request=inline_serializer(
            name='UserIntakeRequest',
            fields={
                'email': serializers.EmailField(help_text="The email address of the user."),
                'mailbox_id': serializers.CharField(help_text="The UID of the mailbox."),
                'name': serializers.CharField(required=False, help_text="The name of the user."),
                'age': serializers.IntegerField(required=False, help_text="The age of the user."),
                'situation': serializers.CharField(required=False, help_text="Current situation or context."),
                'goal': serializers.CharField(required=False, help_text="User's goal."),
                'is_reward_email': serializers.BooleanField(default=True, help_text="Whether to send reward emails."),
                'followup_freq': serializers.CharField(default='never', help_text="Frequency of follow-up emails (e.g., 'daily', 'weekly')."),
                'followup_esc_email': serializers.EmailField(required=False, help_text="Email for escalation."),
            }
        ),
        responses={
            200: AuthorizedEmailsSerializer,
            201: {"description": "Successfully created/updated user intake."},
            400: {"description": "Failed to perform user intake."}
        }
    )
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

@extend_schema(tags=["Mailbox - Email Conversations"])
@extend_schema_view(
    list=extend_schema(
        summary="List Email Conversations",
        description="Fetches a list of email conversations. Supports filtering by various fields.",
        parameters=[
            OpenApiParameter("uid", str, description="Filter by Conversation UID."),
            OpenApiParameter("mailbox_id", str, description="Filter by Mailbox UID."),
            OpenApiParameter("subject", str, description="Filter by email subject."),
            OpenApiParameter("email", str, description="Filter by sender's email address."),
        ]
    ),
    retrieve=extend_schema(
        summary="Retrieve an Email Conversation",
        description="Fetches details of a specific email conversation by its UID."
    ),
    create=extend_schema(summary="Create an Email Conversation", description="Logs a new email conversation."),
    update=extend_schema(summary="Update an Email Conversation", description="Updates an existing email conversation."),
    partial_update=extend_schema(
        summary="Partially Update an Email Conversation",
        description="Partially updates an existing email conversation."
    ),
)
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
        sender = self.request.query_params.get('email')

        
        filters = {}
        if uid:
            filters['uid'] = uid
        elif mailbox_id:
            filters['mailbox_id'] = mailbox_id
        if subject:
            filters['subject'] = subject
        if sender:
            filters['sender'] = sender

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

@extend_schema(tags=["Mailbox - Accountability Intake"])
@extend_schema_view(
    list=extend_schema(
        summary="List Accountability Intakes",
        description="Fetches a list of accountability intakes. You can filter by UID, form ID, or email address.",
        parameters=[
        OpenApiParameter(
            name="uid",
            description="Unique identifier of the accountability intake",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="form_id",
            description="Filter intakes by form ID",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="email_address",
            description="Filter intakes by submitter email address",
            required=False,
            type=str,
        ),
    ]
    ),
    retrieve=extend_schema(
        summary="Retrieve an Accountability Intake",
        description="Fetches details of a specific accountability intake by its UID."
    ),
    create=extend_schema(
        summary="Create or Update an Accountability Intake",
        description="Creates a new accountability intake. \n\n**Upsert Behavior**: If an intake with the same `email_address` and `form_id` already exists, the existing entry will be updated with the new data."
    ),
    update=extend_schema(summary="Update an Accountability Intake", description="Updates an existing accountability intake."),
    partial_update=extend_schema(
        summary="Partially Update an Accountability Intake",
        description="Partially updates an existing accountability intake."
    ),
)
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


    def create(self, request, *args, **kwargs):
        logger.info(f"Received data: {request.data}")

        # Validate the incoming data using the serializer

        try:
            # Check if an entry with the same email_address, form_id, and deleted status exists
            existing_intake = AccountabilityIntake.objects.filter(
                email_address=request.data['email_address'],
                form_id=request.data['form_id'],
                deleted=False
            ).first()

            if existing_intake:
                updated_intake = self.serializer_class(existing_intake, data=request.data)
                updated_intake.is_valid(raise_exception=True)
                updated_intake.save()
                logger.info(f"Updated accountability intake for email: {request.data['email_address']}")
                return Response(updated_intake.data, status=status.HTTP_200_OK)

            else:
                # Create a new entry if no existing entry found
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)

                self.perform_create(serializer)
                logger.info("Created a new accountability intake")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Error creating or updating accountability intake: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer, instance):
        # This method is responsible for updating the instance with new data
        serializer.update(instance, serializer.validated_data)
        logger.info(f"Accountability intake updated with new data: {serializer.validated_data}")

    def perform_create(self, serializer):
        logger.info(f"Creating a new accountability intake with data: {serializer.validated_data}")
        try:
            serializer.save()
            logger.info("Accountability intake created successfully")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating accountability intake: {str(e)}")
            raise e