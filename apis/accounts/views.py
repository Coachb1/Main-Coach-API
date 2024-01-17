import datetime
from rest_framework import mixins
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
import logging
from django.db.models import Subquery
from django.utils import timezone

from apis.accounts.aggregator import create_user_account
from apis.accounts.dtos import UserCreateContextDto, IdentityCreateContextDto
from apis.accounts.serializers import AccountSerializer, UserAttributesUserContextSerializer
from apis.accounts.serializers import SetupAccountSerializer, CoachCoacheeMentorMenteeProfileSerializer
from clients.permissions import IsAuthenticatedClient
from tests.models import TestAttemptSession, Test
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from identities.helpers import get_user_via_identity
from pdf_generator.helpers import get_participant_report
from users.helpers import upsert_user_attributes
from users.models import CoachCoacheeMentorMenteeProfile, User, UserAttribute
from tenants.models import Tenant
from tests.choices import TestAttemptSessionStatusChoices
from users.models import SignatureBot, BotAttribute, ClientUserInfo


from identities.models import Identity
from skills.models import SkillsRating
from utilities.models import BotQnA
from users.db import get_user_by_id,get_user_display_name
import json
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from utilities.helpers import extract_fields

logger = logging.getLogger(__name__)

class AccountsViewSet(ApiViewSet,
                      mixins.ListModelMixin):
    queryset = User.objects.filter(deleted=0)
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticatedClient, IsAuthenticatedUser)
    lookup_field = "uid"
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        """
        Create a user account.

        Args:
            request (object): The HTTP request object containing the user and identity data.

        Returns:
            object: The HTTP response object containing the serialized user account data.
        """
        serializer = SetupAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_context = serializer.validated_data["user_context"]
        identity_context = serializer.validated_data["identity_context"]


        try:
            i_context=IdentityCreateContextDto(**identity_context)

            identity = Identity.objects.get(
                tenant_id=request.tenant.uid,
                identity_type=i_context.identity_type,
                value=i_context.value,
                deleted=0
                )

            user = User.objects.get(
                tenant_id=request.tenant.uid,
                uid=identity.user_id,
                deleted=0
            )
            logger.info("got user")
        except Exception as e:
            logger.info("creating user")
            user = create_user_account(tenant=request.tenant,
                                user_context=UserCreateContextDto(
                                    **user_context),
                                identity_context=IdentityCreateContextDto(**identity_context))

        return Response(AccountSerializer(instance=user).data, status=status.HTTP_201_CREATED)

    @action(methods=["GET"],
            detail=False,
            url_path=r"identities/(?P<identity_type>[^\s]+)/(?P<identity_value>[^\s]+)")
    def get_account_via_identity(self, request, identity_type, identity_value, *args, **kwargs):
        """
        Retrieves a user account based on the provided identity type and identity value.

        :param request: The HTTP request object.
        :param identity_type: The type of identity to search for.
        :param identity_value: The value of the identity to search for.
        :return: The HTTP response object containing the serialized user account data.
        """
        user = get_user_via_identity(
            tenant=request.tenant,
            identity_type=identity_type,
            identity_value=identity_value
        )
        return Response(AccountSerializer(instance=user).data, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=True, url_path="upsert-attributes")
    def upsert_user_attributes_view(self, request, *args, **kwargs):
        """
        Update or insert user attributes in the database.

        :param request: The HTTP request object.
        :type request: HttpRequest
        :param args: Additional positional arguments.
        :type args: tuple
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The HTTP response object containing the serialized user account data.
        :rtype: HttpResponse
        """
        serializer = UserAttributesUserContextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tag = serializer.validated_data["tag"]
        attributes = serializer.validated_data["attributes"]

        user = self.get_object()

        user_attribute = upsert_user_attributes(user=user,
                                                tag=tag,
                                                attributes=attributes)

        return Response(AccountSerializer(instance=user).data, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="participant-report")
    def get_participant_report_pdf_view(self, request, *args, **kwargs):
        user = self.get_object()

        report_url = get_participant_report(user)

        return Response({"report_url": report_url})

    @action(methods=["GET"], detail=True, url_path="participant-report-data")
    def get_participant_report_frontend(self, request, *args, **kwargs):
        user = self.get_object()

        data = get_participant_report(user, only_data=True)

        return Response({"data": data, "status": "completed"})


    @action(methods=["GET"], detail=False, url_path="get-workspace-users")
    def get_workspace_users(self, request, *args, **kwargs):
        """
        Retrieves a list of workspace users who have attempted tests.

        Args:
            request (object): The HTTP request object.

        Returns:
            dict: A dictionary containing the names and IDs of workspace users who have attempted tests.

        """
        try:
            included_users = self.get_queryset().filter(is_excluded=0).values('uid')
            users = UserAttribute.objects.filter(user_id__in=Subquery(included_users))

            user_data = {}
            for user in users:
                try:
                    skills_rating = SkillsRating.objects.get(participant_id=user.user_id)
                    if skills_rating.total_tests_attempted > 0:
                        user_data[f"{user.attributes['real_name']} - {user.attributes['name']}"] = user.attributes['id']
                except:
                    pass

            return Response(user_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error({"!!!! Error":e},exc_info=True)


    @action(methods=['GET'], detail=False, url_path="get_is_repeat_status")
    def get_is_repeat_status(self, request, *args, **kwargs):
        """
        Retrieves the repeat status of a participant for a given tenant.

        This method calculates the number of tests the participant has attempted in the current month and compares it to the maximum number of tests allowed per month.
        It returns the repeat status and the remaining number of tests for the month.

        :param request: The HTTP request object.
        :param participant_id: The ID of the participant for whom the repeat status is being checked.
        :return: A dictionary containing the tenant ID, repeat status, and the remaining number of tests for the month.
        """

        tenant = self.request.tenant
        participant_id = request.query_params.get("participant_id")

        try:
            test_per_month = tenant.test_per_month
            current_month = timezone.now().month
            # date_month_ago = timezone.make_aware(date_month_ago, timezone.get_current_timezone())
            sessions = TestAttemptSession.objects.filter(participant_id = participant_id,tenant_id=tenant.uid, status=TestAttemptSessionStatusChoices.completed)
            this_month_sessions = []
            for session in sessions:
                if session.created.month == current_month:
                    this_month_sessions.append(session)
            total_test_attempted = len(this_month_sessions)
        except Exception as e:
            logger.error({"!!!!!!!!!! Error": e}, exc_info=True)
            total_test_attempted = 0

        data = {"tenant_id": tenant.uid, "is_repeat": tenant.is_repeat, "monthly_remaining_tests": test_per_month - total_test_attempted}
        return Response(data, status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path="get-user-type")
    def get_user_type(self,request,*args, **kwargs):
        """
            Retrieves the role of a user based on their user ID.
        """
        user_id = request.query_params.get('user_id')

        user = User.objects.get(uid=user_id)

        user_role = user.role

        return Response({"user_role":user_role}, status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path="get-mobile-number-restriction-list-whatsapp")
    def get_mobile_number_res_list_whatsapp(self,request,*args, **kwargs):
        """
        Only for Whatsapp use.
        Retrive restricted mobile numbers from db
        """
        tenant = self.request.tenant
        number_list = []

        if tenant.mobile_number_restriction_whatsapp:
            number_list = tenant.mobile_number_list.split(',')
            number_list = [number.strip() for number in number_list]

        return Response({"mobile_numbers": number_list,'active': tenant.mobile_number_restriction_whatsapp},status=status.HTTP_200_OK)


    @action(methods=['GET'], detail=False, url_path="get-test-codes-for-web")
    def get_test_codes_for_web(self,request,*args, **kwargs):
        '''
            Retrives all testcode json for web environment(deepchat)
        '''

        tenant = self.request.tenant
        logger.info({'tenant': tenant,"test_code_json":tenant.web_test_code_json})


        test_code_json = tenant.web_test_code_json

        return Response({"data":test_code_json},status=status.HTTP_200_OK)
    
    @action(methods=['GET','POST'],detail=False, url_path="get-my-lib-data")
    def get_my_lib_data(self,request,*args, **kwargs):
        """
        Retrieves library data based on a group name.

        Args:
            request (object): The HTTP request object.
            group (string): The name of the group to filter tests.

        Returns:
            Dictionary: A dictionary containing the library data grouped by domain. Each domain key maps to a list of test items, where each item contains the title, description, domain, test code, and interaction mode.
        """
        # test_codes = request.query_params.get('test_codes').split(',')
        group_name = request.query_params.get('group')
        tests = Test.objects.filter(deleted=0,client_name=group_name)
        data = []
        for item in tests:
            title_parts = item.title.split(':')
            key = title_parts[0].strip().capitalize()
        
            data.append({"title": item.title,"description": item.description, "domain": key,
                            "test_code": item.test_code, "interaction_mode": item.interaction_mode, "is_micro": item.is_micro})

        group_data = {}
        for item in data:
            domain = item['domain']
            if domain in group_data:
                group_data[domain].append(item)
            else:
                group_data[domain] = [item]

        return Response({"data":group_data},status=status.HTTP_200_OK)


    @action(methods=['GET'],detail=False, url_path="get-bot-details")
    def get_bot_details(self,request,*args, **kwargs):
        """
        Retrieves details of a bot based on the provided bot ID.

        :param request: The HTTP request object.
        :param bot_id: The ID of the bot to retrieve details for.
        :return: A dictionary containing the bot details with keys 'faqs', 'attributes', 'bot_details', and 'recommended_codes'.
        :rtype: dict
        """
        bot_id = request.query_params.get('bot_id')

        try:
            signature_bot = SignatureBot.objects.get(bot_id=bot_id)
        except:
            return Response({"error": "Bot not found"},status=status.HTTP_404_NOT_FOUND)

        data = {}
        data['faqs'] = signature_bot.faqs
        data['attributes'] = signature_bot.attributes
        data['bot_details'] = signature_bot.bot_details
        data['recommended_codes'] = signature_bot.recommended_codes
        data['bot_type'] = signature_bot.bot_type
        data['user_id'] = signature_bot.user_id
        data['is_fitment_analysis'] = signature_bot.is_fitment_analysis
        data['is_strict_fitment'] = signature_bot.is_strict_fitment
        try:
            bot_att = BotAttribute.objects.get(bot_id=signature_bot.uid)
            if bot_att.fitment_data:
                data['fitment_qna'] = bot_att.fitment_data['mentee_que']
            if bot_att.fitment_data:
                data['fitment_options'] = bot_att.fitment_data['options']
            
            if bot_att.feedback_questions:
                data['feedback_qna'] = bot_att.feedback_questions
            if bot_att.initial_qnas:
                data['initial_qna'] = bot_att.initial_qnas
        except Exception as e:
            logger.exception(e)


        return Response({"data":data},status=status.HTTP_200_OK)


    @action(methods=['GET'], detail=False, url_path="get-client-information")
    def get_client_informations(self,request,*args, **kwargs):

        try:
            mode = request.query_params.get('for',None)  # can be my_lib, user_info
            user_id = request.query_params.get('user_id',None)
            email = request.query_params.get('email',None)
            mob_number = request.query_params.get('mob_number',None)
            tenant = self.request.tenant

            logger.info(f"for: {mode}, user_id: {user_id},email: {email},mob_number: {mob_number}")
            client_info = ClientUserInfo.objects.filter(tenant_id = tenant.uid,deleted = 0)
            data = {}

            if mode == 'my_lib':
                client_and_emails_map = []

                for client in client_info:
                    client_and_emails_map.append({"group": client.client_name,
                                                "emails": [email for email in client.member_emails.split(',')]
                                                })
                
                data['my_lib'] = client_and_emails_map
            
            elif mode == 'user_info':
                user = ''
                if user_id:
                    user = client_info.filter(member_user_ids__contains = user_id)
                if email:
                    user = client_info.filter(member_emails__contains = email)
                if mob_number:
                    user = client_info.filter(member_mob_numbers__contains = mob_number)

                user_info = []

                for u in user:
                    user_info.append({
                        "client_name": u.client_name,
                        "avatar_bot_creation": u.avatar_bot_creation,
                        "feedback_bot_creation": u.feedback_bot_creation,
                        "subject_matter_bot_creation": u.subject_matter_bot_creation,
                        "monthly_conversation_limit": u.number_of_conversation_per_month,
                        "required_form_details": extract_fields(u.required_form_fields) if u.required_form_fields else None,
                    })

                data['user_info'] = user_info

            return Response({"data":data },status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"got error: {e}")
            return Response({"error":e},status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'], detail=False, url_path="get-user-feedback-data")
    def get_user_feedback_data(self,request,*args, **kwargs):
        try:
            method = request.query_params.get('method',None)
            bot_id = request.query_params.get('bot_id',None)
            data = {}
            try:
                signature_bot = SignatureBot.objects.get(tenant_id = self.request.tenant.uid,bot_id=bot_id)
            except Exception as e:
                logger.exception(e)
                return Response({"error":"bot not found"},status=status.HTTP_400_BAD_REQUEST)
            if method.lower() == 'get':
                # try:
                #     feedback_bot_id = SignatureBot.objects.get(tenant_id = self.request.tenant.uid,user_id=signature_bot.user_id,bot_type='feedback_bot').uid
                #     print(feedback_bot_id)
                # except Exception as e:
                #     logger.exception(f"Feedback bot not found {e}")
                #     data['positive_msgs'] = []
                #     return Response(data,status=status.HTTP_200_OK)
                
                feedback_data = BotQnA.objects.filter(tenant_id = self.request.tenant.uid,bot_id=signature_bot.uid)
                positive_msg_data = []
                for feed in feedback_data:
                    participant_name = get_user_display_name(
                        get_user_by_id(feed.participant_id))
                    if feed.is_positive:
                        positive_msg_data.append({
                            "participant_name": participant_name,
                            "date": feed.created,
                            "msg": feed.participant_qna
                        })
                
                data['positive_msgs'] = positive_msg_data

            elif method.lower() == 'post':
                participant_id = request.query_params.get('user_id',None)
                feedback_qna = request.query_params.get('qna',None)
                is_positive = request.query_params.get('is_positive',None)
                qna_type = request.query_params.get('qna_type',None)

                BotQnA.objects.create(
                    tenant_id = self.request.tenant.uid,
                    participant_id = participant_id,
                    participant_qna = json.loads(feedback_qna),
                    is_positive = is_positive,
                    bot_id = signature_bot.uid,
                    qna_type = qna_type,
                )
                data['message'] = "created"

            return Response(data,status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.exception(f"got error: {e}")
            return Response({"error":e},status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET','POST','PATCH'], detail=False, url_path="coach-coachee-mentor-mentee-profile")
    def coach_coachee_mentor_mentee_profile(self,request,*args, **kwargs):
        """
        Retrieves or creates a coach-coachee-mentor-mentee profile for a user.

        Args:
            request (object): The HTTP request object.

        Returns:
            dict: A dictionary containing the coach-coachee-mentor-mentee profile data.
        """


        # return Response({"data":data},status=status.HTTP_200_OK)
        if request.method == 'GET':
            profile_id = request.query_params.get('profile_id',None)
            if profile_id:
                profile = CoachCoacheeMentorMenteeProfile.objects.get(uid=profile_id)
                return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profile).data },status=status.HTTP_200_OK)
            else:
                profiles = CoachCoacheeMentorMenteeProfile.objects.all()
                profile_type = request.query_params.get('profile_type',None)
                if profile_type:
                    profiles = profiles.filter(profile_type=profile_type)
                return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profiles,many=True).data },status=status.HTTP_200_OK)

        if request.method == 'PATCH':
            profile_id = request.query_params.get('profile_id',None)
            profile = CoachCoacheeMentorMenteeProfile.objects.get(uid=profile_id)
            data = request.data.copy()
            data['tenant_id'] = self.request.tenant.uid
            serializer = CoachCoacheeMentorMenteeProfileSerializer(profile,data=data,partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profile).data },status=status.HTTP_200_OK)

        if request.method == 'POST':
            logger.info(f"************************************** request files : {request}**************************************************************************** request data: {request.data}")
            data = request.data.copy()
            data['tenant_id'] = self.request.tenant.uid
            serializer = CoachCoacheeMentorMenteeProfileSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            logger.info(f"serializer data: {serializer.validated_data}")
            created_profile = serializer.save()
            return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(created_profile).data },status=status.HTTP_200_OK)

