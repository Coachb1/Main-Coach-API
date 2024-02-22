import datetime
from rest_framework import mixins
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
import logging
from django.db.models import Subquery
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import threading


from apis.accounts.aggregator import create_user_account
from apis.accounts.dtos import UserCreateContextDto, IdentityCreateContextDto
from apis.accounts.serializers import AccountSerializer, UserAttributesUserContextSerializer, CoachCoacheeConnectionSerializer
from apis.accounts.serializers import SetupAccountSerializer, CoachCoacheeMentorMenteeProfileSerializer, SignatureBotSerializer, BotAttributeSerializer,DirectoryInfoSErializer
from clients.permissions import IsAuthenticatedClient
from tests.models import TestAttemptSession, Test
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from identities.helpers import get_user_via_identity
from pdf_generator.helpers import get_participant_report
from users.helpers import upsert_user_attributes
from users.models import CoachCoacheeMentorMenteeProfile, User, UserAttribute, CoachCoacheeConnection
from users.choices import BotTypeChoice
from tenants.models import Tenant
from tests.choices import TestAttemptSessionStatusChoices
from users.models import SignatureBot, BotAttribute, ClientUserInfo
from users.choices import StatusChoice, ProfileTypeChoice, CoachCoacheeConnectionStatusChoice
from tests.helpers import scrape_article_data


from identities.models import Identity
from skills.models import SkillsRating
from utilities.models import BotQnA, DirectoryPageInfo
from users.db import get_user_by_id,get_user_display_name
import json
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from email_sender.helpers import send_generic_email, send_email_with_html_template
from utilities.helpers import extract_fields
from commons.langchain import download_and_transcribe_audio, extract_text_from_pdf, extract_text_from_doc
from coaching_conversations.helpers import avatar_bot_default_prompt
from utilities.helpers import process_idp, regenerate_idp_or_scenarios
from utilities.models import UserActionInfo
from commons.utils import extract_file_and_text
                    
from itertools import groupby
from operator import attrgetter
from django.db.models import Q
from commons.youtube_utils import get_youtube_transcript
from utilities.prompts import get_intake_summary_prompt
from commons.anthropic import anthropic_completion

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
        group_name = request.query_params.get('group',None)
        candidate_type = request.query_params.get('candidate_type',None)
        data = []
        if group_name:
            tests = Test.objects.filter(deleted=0,client_name=group_name)
            for item in tests:
                title_parts = item.title.split(':')
                key = title_parts[0].strip().capitalize()
            
                data.append({"title": item.title,"description": item.description, "domain": key,
                                "test_code": item.test_code, "interaction_mode": item.interaction_mode, "is_micro": item.is_micro})

        if candidate_type:
            tests = Test.objects.filter(deleted=0,tenant_id=self.request.tenant.uid,candidate_type=candidate_type.strip().lower())
            for test in tests:
                if test.area_domain:
                    key = test.area_domain
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

        logger.info(f"****************** Bot ID: {bot_id} **********************")

        try:
            signature_bot = SignatureBot.objects.get(bot_id=bot_id)
        except Exception as e:
            logger.exception({"!!!!!!!!!! Error": e}, exc_info=True)
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
        data['is_sample_bot'] = signature_bot.is_sample_bot
        data['is_system_bot'] = signature_bot.is_system_bot
        data['additional_data'] = signature_bot.data.get('additional_data',None)
        try:
            bot_att = BotAttribute.objects.get(bot_id=signature_bot.uid)
            data['is_audio_response'] = bot_att.is_audio_response

            if bot_att.fitment_data:
                data['fitment_qna'] = bot_att.fitment_data['mentee_que']
            if bot_att.fitment_data:
                data['fitment_options'] = bot_att.fitment_data['options']
            
            if bot_att.feedback_questions:
                data['feedback_qna'] = bot_att.feedback_questions
            if bot_att.initial_qnas:
                data['initial_qna'] = bot_att.initial_qnas

            coach_profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=signature_bot.user_id,profile_type=ProfileTypeChoice.coach,bot_ids__icontains=bot_id)
            for i in coach_profile:
                data["coaching_for_fitment"] = i.coaching_for_fitment.lower() if i.coaching_for_fitment else None

            
            feedback_bot = SignatureBot.objects.filter(tenant_id=self.request.tenant.uid,user_id=signature_bot.user_id,bot_type=BotTypeChoice.feedback_bot).first()
            if feedback_bot:
                data['feedback_id'] = feedback_bot.bot_id
            else:
                data['feedback_id'] = None

            if not signature_bot.is_system_bot and not signature_bot.is_sample_bot:
                if coach_profile.count() > 0:
                    data['owner_profile_image'] = coach_profile.first().profile_image_url
            
        except Exception as e:
            logger.exception(e)


        return Response({"data":data},status=status.HTTP_200_OK)


    @action(methods=['GET'], detail=False, url_path="get-client-information")
    def get_client_informations(self,request,*args, **kwargs):
        """
        Retrieves client information based on the provided parameters.
        Returns:
            dict: A dictionary containing the retrieved client information. The structure of the dictionary depends on the `mode` parameter.
        """
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
                    restricted = False
                    demo_user = False
                    
                    restricted_emails = []
                    if u.restricted_ids:
                        restricted_emails = [e.strip() for e in u.restricted_ids.split(',')]
                    demo_emails = []
                    if u.demo_ids:
                        demo_emails = [e.strip() for e in u.demo_ids.split(',')]

                    
                    if email in restricted_emails:
                        restricted = True
                    if email in demo_emails:
                        demo_user = True

                    user_info.append({
                        "client_name": u.client_name,
                        "avatar_bot_creation": u.avatar_bot_creation,
                        "feedback_bot_creation": u.feedback_bot_creation,
                        "subject_matter_bot_creation": u.subject_matter_bot_creation,
                        "monthly_conversation_limit": u.number_of_conversation_per_month,
                        "required_form_details": extract_fields(u.required_form_fields) if u.required_form_fields else None,
                        "is_restricted": restricted,
                        "is_demo_user": demo_user,
                        "accessed_bot_ids": u.accessed_bot_ids,
                        "coach_skills": u.coach_skills,
                        "coach_expertise": u.coach_expertise,
                        "departments": u.departments,
                    })

                if len(user_info) == 0:
                    user_info.append({"msg": "user not found",
                                      "is_restricted": True,
                                      "is_demo_user": False},
                                      )

                data['user_info'] = user_info

            return Response({"data":data },status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"got error: {e}")
            return Response({"error":e},status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'], detail=False, url_path="get-user-feedback-data")
    def get_user_feedback_data(self,request,*args, **kwargs):
        """
        Retrieves or creates user feedback data for a specific bot.

        Args:
            request (object): The HTTP request object.
            method (string): The method to perform, either "get" or "post".
            feedback_type(string):  nagetive then fetches only critical msg.
            bot_id (string): The ID of the bot for which to retrieve or create feedback data.
            user_id (string): The ID of the user for whom to create feedback data (only required for "post" method).
            qna (string): The question and answer data for the feedback (only required for "post" method).
            is_positive (boolean): Indicates whether the feedback is positive or not (only required for "post" method).
            qna_type (string): The type of the feedback (only required for "post" method).

        Returns:
            If the method is "get":
                A dictionary containing the positive messages data.
            If the method is "post":
                A dictionary with a "message" key indicating the success of the creation.
        """
        try:
            method = request.query_params.get('method',None)
            bot_id = request.query_params.get('bot_id',None)
            feedback_type = request.query_params.get("feedback_type",None)
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
                qna_type = request.query_params.get("qna_type",None)
                if qna_type and qna_type.lower() == 'intake':
                    recent_intake_data = BotQnA.objects.filter(tenant_id = self.request.tenant.uid,bot_id=signature_bot.uid,qna_type='intake').order_by('-created').first()
                    return Response({"intake_summary": recent_intake_data.intake_summary},status=status.HTTP_200_OK)
                
                feedback_data = BotQnA.objects.filter(tenant_id = self.request.tenant.uid,bot_id=signature_bot.uid,qna_type='feedback')
                msg_data = []
                for feed in feedback_data:
                    participant_name = get_user_display_name(
                        get_user_by_id(feed.participant_id))
                    
                    if feedback_type == "negative":
                        if not feed.is_positive:
                            msg_data.append({
                                "participant_name": participant_name,
                                "date": feed.created,
                                "msg": feed.participant_qna
                            })
                    else:
                        if feed.is_positive:
                            msg_data.append({
                                "participant_name": participant_name,
                                "date": feed.created,
                                "msg": feed.participant_qna
                            })
                if feedback_type == "negative":
                    data['critical_msgs'] = msg_data
                else:
                    data['positive_msgs'] = msg_data

            elif method.lower() == 'post':
                participant_id = request.query_params.get('user_id',None)
                feedback_qna = request.query_params.get('qna',None)
                is_positive = request.query_params.get('is_positive',None)
                qna_type = request.query_params.get('qna_type',None)


                intake_summary_prompt = get_intake_summary_prompt(feedback_qna)
                intake_summary = anthropic_completion(intake_summary_prompt,50000)

                BotQnA.objects.create(
                    tenant_id = self.request.tenant.uid,
                    participant_id = participant_id,
                    participant_qna = json.loads(feedback_qna),
                    is_positive = is_positive,
                    bot_id = signature_bot.uid,
                    qna_type = qna_type,
                    intake_summary = intake_summary
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
            user_id = request.query_params.get('user_id',None)
            if user_id:
                try:
                    profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=user_id)
                    return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profile,many=True).data },status=status.HTTP_200_OK)
                except Exception as e:
                    logger.exception(e)
                    return Response({"error":"profile not found"},status=status.HTTP_404_NOT_FOUND)
            if profile_id:
                try:
                    profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,uid=profile_id)
                    return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profile).data },status=status.HTTP_200_OK)
                except Exception as e:
                    logger.exception(e)
                    return Response({"error":"profile not found"},status=status.HTTP_404_NOT_FOUND)
            else:
                profiles = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,is_approved=True)
                profile_type = request.query_params.get('profile_type',None)
                if profile_type:
                    profiles = profiles.filter(profile_type=profile_type)
                return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profiles,many=True).data },status=status.HTTP_200_OK)

        if request.method == 'PATCH':
            profile_id = request.query_params.get('profile_id',None)
            print("*"*100)
            logger.info(f"data : {request.data}")
            data = {"tenant_id" : self.request.tenant.uid}
            data.update(request.data)
            print(data)
            profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,uid=profile_id)
            serializer = CoachCoacheeMentorMenteeProfileSerializer(profile,data=data,partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profile).data },status=status.HTTP_200_OK)

        if request.method == 'POST':
            logger.info(f"************************************** request files : {request}**************************************************************************** request data: {request.data}")
            data = request.data.copy()
            data['tenant_id'] = self.request.tenant.uid

            profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=self.request.tenant.uid,user_id=data['user_id'],profile_type=data['profile_type'])
            if profile.count() > 0:
                return Response({"msg": "Entry already Exist","data": CoachCoacheeMentorMenteeProfileSerializer(profile,many=True).data },status=status.HTTP_200_OK)
            
            serializer = CoachCoacheeMentorMenteeProfileSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            logger.info(f"serializer data: {serializer.validated_data}")
            created_profile = serializer.save()
            send_generic_email(f"{created_profile.name} just created {created_profile.profile_type}  Account",
                               f"{created_profile.name} just created {created_profile.profile_type}  Account. check it out on admin panel(https://coach-api-ovh.coachbots.com/custom-admin/) and approve it, to make it display on Directory page")
            # send_generic_email(f"{created_profile.name} just created {created_profile.profile_type}  Account",
            #                    f"{created_profile.name} just created {created_profile.profile_type}  Account. check it out on admin panel(https://coach-api-ovh.coachbots.com/custom-admin/) and approve it, to make it display on Directory page",
            #                    'aadil611ofc@gmail.com')
            DirectoryPageInfo.objects.create(
                    name=created_profile.name,
                    profile_id=created_profile.uid,
                    department=created_profile.department,
                    bot_type=BotTypeChoice.feedback_bot,
                    profile_pic_url=created_profile.profile_image_url or "None",
                    profile_type=created_profile.profile_type,
                    description=created_profile.about,
                    experience=created_profile.experience,
                    expertise=created_profile.area_domain,
                    status=StatusChoice.available,
                    skills=created_profile.high_rating_characteristics,
                    is_visible= True,
                    is_approved = False,
                    )
            
            return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(created_profile).data },status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path="get-bots")
    def get_bots(self,request,*args, **kwargs):
        user_id = request.query_params.get('user_id',None)
        
        all_bots = SignatureBot.objects.filter(deleted=False,is_approved=True)
        if user_id:
            data = []
            all_bots = all_bots.filter(user_id=user_id)
            for bot in all_bots:
                serializer = SignatureBotSerializer(bot)
                bot_att = BotAttribute.objects.get(bot_id=bot.uid)
                botser = BotAttributeSerializer(bot_att)
                data.append({"signature_bot": serializer.data,
                             "bot_attributes": botser.data})
            return Response({"data": data},status=status.HTTP_200_OK)
        else:
            return Response({"data": [bot.bot_id for bot in all_bots]},status=status.HTTP_200_OK)
        

    #************* utility methods ***************
    def process_and_store_youtube_transcript(self,youtube_links,signature_bot):
        extracted_from_youtube = {}
        extracted_media_data = {}

        logger.info(f"*************** youtube_links in process_and_store : {youtube_links}")

        transcript = None
        for link in youtube_links:
            if link != '':
                try:
                    for i in range(2):
                        transcript = get_youtube_transcript(link)
                        if transcript is not None:
                            break
                    if transcript is None:
                        transcript = download_and_transcribe_audio(link)
                    extracted_from_youtube[link] = transcript
                except Exception as e:
                    logger.exception(e)
                    extracted_from_youtube[link] = {"error": "error in extracting transcript"}
            
        # extracted_media_data['extracted_from_youtube'] = extracted_from_youtube
        signature_bot.data['media_data']['extracted_from_youtube'] = extracted_from_youtube
        signature_bot.save(update_fields=["data"])
        return transcript

    
    @action(methods=['POST','PATCH'],detail=False, url_path="create-bot-by-details")
    def create_bot_by_details(self,request,*args, **kwargs):
        """
        Creates a new bot based on the provided bot details.

        :param request: The HTTP request object.
        :param bot_details: A dictionary containing the bot details with keys 'faqs', 'attributes', 'bot_details', and 'recommended_codes'.
        :return: A dictionary containing the bot details with keys 'faqs', 'attributes', 'bot_details', and 'recommended_codes'.
        :rtype: dict
        """

        data = request.data

        # tenant = self.request.tenant
        # print("Tenant: ",tenant, "T"*100)

        if request.method == 'POST':
            profile_id = data.get('profile_id',None)
            try:
        
                bot_type = data.get('bot_type')
                if bot_type is None or bot_type == '' or bot_type not in [choice[0] for choice in BotTypeChoice.choices]:
                    return Response({"error": "bot_type is required"},status=status.HTTP_400_BAD_REQUEST)
                
                if (profile_id is None or profile_id == '' ) and bot_type != BotTypeChoice.feedback_bot :
                    return Response({"error": "profile_id is required"},status=status.HTTP_400_BAD_REQUEST)


                participant_id = data.get('participant_id')
                if participant_id is None or participant_id == '':
                    return Response({"error": "participant_id is required"},status=status.HTTP_400_BAD_REQUEST)

                bot_name = data.get('bot_name')
                if bot_name is None or bot_name == '':
                    return Response({"error": "bot_name is required"},status=status.HTTP_400_BAD_REQUEST)

                bot_id = "-".join([bot_type, participant_id[:5], bot_name.strip().lower().replace(" ","-")])
                existing_bots = SignatureBot.objects.filter(bot_id=bot_id,tenant_id=self.request.tenant.uid,deleted=False)
                if existing_bots.count() > 0:
                    return Response({"error": "Bot already exists"},status=status.HTTP_400_BAD_REQUEST)

                try:
                    user = User.objects.get(uid=participant_id)
                except:
                    return Response({"error": "User not found"},status=status.HTTP_404_NOT_FOUND)
                

                bot_attributes = data.get('attributes')
                if bot_attributes is None or bot_attributes == '':
                    return Response({"error": "attributes is required"},status=status.HTTP_400_BAD_REQUEST)
                
                feedback_questions = data.get("feedback_questions")
                if bot_type == BotTypeChoice.feedback_bot:
                    if feedback_questions is None or feedback_questions == '':
                        return Response({"error": "feedback_questions is required"},status=status.HTTP_400_BAD_REQUEST)

                fitment_answer = data.get('fitment_answer',None)
                if bot_type == BotTypeChoice.avatar_bot:
                    if fitment_answer is None or fitment_answer == "":
                        return Response({"error": "fitment_answer is required"},status=status.HTTP_400_BAD_REQUEST)
                    
                bot_base_url = data.get('bot_base_url',None)
                if not bot_base_url:
                    return Response({"error": "bot_base_url is required"},status=status.HTTP_400_BAD_REQUEST)

                faqs = data.get('faqs')
                fitment_details = data.get('fitment_data',None)
                initial_questions = data.get('initial_questions',None)
                media_data = data.get('media_data')
                bot_details = data.get('bot_details',{})
                additional_data = data.get('additional_data')
                coach_data = data.get('coach_data')

                bot_details["is_login_required"] = False
                bot_details["is_strict_login_required"] = False
                

                all_data = {}

                all_data['coach_data'] = coach_data

                extracted_media_data = {}

                if additional_data:
                    all_data['additional_data'] = additional_data

                print("################# media_data: ",media_data)

                if 'attatched_pdfs' in request.data:
                    if media_data is None:
                        media_data = {}
                    media_data = json.loads(media_data)
                    media_data['attatched_pdfs'] = request.data.getlist('attatched_pdfs')
                    logger.info(f"*************** attached_pdfs files in request: {media_data['attatched_pdfs']}")
                extracted_media_data = {}

                logger.info(f"*************** attached_pdfs files in request: {request.data}, $$$$$$$$ {'attatched_pdfs' in request.data}")

                
                signature_bot = SignatureBot.objects.create(
                    bot_id=bot_id,
                    tenant_id=self.request.tenant.uid,
                    user_id=participant_id,
                    bot_type=bot_type,
                )


                #******** process media data ********

                if media_data and signature_bot.bot_type != BotTypeChoice.feedback_bot:
                    if 'youtube_links' in media_data:
                        youtube_links = media_data['youtube_links']
                        youtube_links = [link.strip() for link in youtube_links.split(',')]


                        #* save these links in bot attributes
                        """ extracted_from_youtube = {}
                        for link in youtube_links:
                            
                            if link != '':
                                transcript_data = download_and_transcribe_audio(link)
                                extracted_from_youtube[link] = transcript_data
                        
                        extracted_media_data['extracted_from_youtube'] = extracted_from_youtube """

                        threading.Thread(target=self.process_and_store_youtube_transcript,args=(youtube_links,signature_bot)).start()


                    if 'article_links' in media_data:
                        article_links = media_data['article_links']
                        article_links = [link.strip() for link in article_links.split(',')]

                        logger.info(f"******************* article_links: {article_links}")
                        #* save these links in bot attributes
                        extracted_from_article = {}
                        for link in article_links:
                            
                            if link != '':
                                transcript_data = scrape_article_data(link).get('article_content',None)
                                extracted_from_article[link] = transcript_data
                        
                        # logger.info(f"******************* extracted_from_article: {extracted_from_article}")
                        extracted_media_data['extracted_from_article'] = extracted_from_article


                    if 'pdf_data' in data:
                        pdf_data = data.getlist('pdf_data')
                        extracted_from_pdf = {}
                        logger.info(f"******************* pdf_data: {doc_data}")

                        if len(pdf_data) > 0:
                            for index, pdf in enumerate(pdf_data):
                                extracted_from_pdf[index+1] = pdf
                        logger.info(f"******************* pdf_data: {extracted_from_pdf}")
                        extracted_media_data['extracted_from_pdf'] = extracted_from_pdf

                    if 'doc_data' in data:
                        doc_data = data.getlist('doc_data')
                        extracted_from_doc = {}


                        logger.info(f"******************* doc_data: {doc_data}")
                        if len(doc_data) > 0:
                            for index, doc in enumerate(doc_data):
                                extracted_from_doc[index+1] = doc

                        logger.info(f"******************* doc_data: {extracted_from_doc}")
                        extracted_media_data['extracted_from_doc'] = extracted_from_doc


                    if 'attached_docs' in media_data or 'attached_docs' in request.FILES:
                        attached_docs = media_data['attached_docs'] if 'attached_docs' in media_data else request.FILES.getlist('attached_docs')
                        doc_names = []
                        extracted_from_doc = {}

                        for file in attached_docs:
                            # logger.info(f"file name : {file.name}, {file.read()}")
                            doc_names.append(file.name)
                            path = default_storage.save(file.name, ContentFile(file.read()))
                            doc_content = extract_text_from_doc(path)
                            default_storage.delete(path)
                            extracted_from_doc[file.name] = doc_content

                        extracted_media_data['extracted_from_doc'] = extracted_from_doc


                    if 'attatched_pdfs' in media_data or 'attatched_pdfs' in request.FILES:
                        attatched_pdfs = media_data['attatched_pdfs'] if 'attatched_pdfs' in media_data else request.FILES.getlist('attatched_pdfs')
                        pdf_names = []
                        extracted_from_pdf = {}

                        for file in attatched_pdfs:
                            # logger.info(f"file name : {file.name}, {file.read()}")
                            pdf_names.append(file.name)
                            path = default_storage.save(file.name, ContentFile(file.read()))
                            pdf_content = extract_text_from_pdf(path)
                            default_storage.delete(path)
                            extracted_from_pdf[file.name] = pdf_content

                        extracted_media_data['extracted_from_pdf'] = extracted_from_pdf


                all_data['media_data'] = extracted_media_data




                bot_att = BotAttribute.objects.create(tenant_id=self.request.tenant.uid,
                                                    bot_id=signature_bot.uid,
                                                    bot_name=bot_name,
                                                    )
                
                # fitment_data= {"options": {"1": ["Weekly commitments", "Bi-weekly sessions", "Monthly sessions", "Ad Hoc / On demand", "Customized Structure"], "2": ["Career advancement", "Skill development", "Introspection & Reflection", "Industry insights", "Networking & Leadership"], "3": ["Technology", "Business Operations", "Industrial Operations", "Sales & Marketing", "HR & People Management"]}, "mentee_que": {"1": "How much time and commitment are you prepared to invest in a mentoring/coaching journey? Are there specific timelines or availability constraints you'd like your mentor/coach to consider?", "2": "What are your expectations from this mentoring/coaching session - in terms of key outcome areas?", "3": "What are the hard skill areas, if any, you want to improve upon?"}, "mentor_que": {"1": "How much time are you willing to commit to mentoring/coaching? Are there specific times or days that work best for you, or any constraints you'd like a potential mentee to be aware of?", "2": "What are your expectations from this mentoring/coaching session - in terms of key outcome areas?", "3": "What are the hard skill areas, if any, you want to contribute in?"}, "fitment_measures": {"mid": "The score reflects a promising yet moderate fit in coaching dynamics. Acknowledge existing areas for improvement and work collaboratively to address specific concerns. Proactively work on refining coaching dynamics to elevate the overall experience for both the coach and coachee. Continuous effort and attention to areas of improvement can lead to a more effective coaching partnership.", "top": "The score refelcts a robust alignment between the coach and coachee, laying the foundation for an optimal coaching relationship. The coaching relationship is optimal, providing a strong foundation for success. Maintain and nurture open communication and collaboration, as these are key elements in sustaining the excellence of the coaching dynamic.", "bottom": "The score signals a notable discord in coaching dynamics, this suggests a reconsideration of the coaching relationship. Misalignment may impede progress, so exploring alternative matches could unveil better synergies and enhance overall effectiveness. Re-evaluate if the coaching partnership aligns with the coachee's goals and needs."}}
                fitment_data= {
                    "options":{
                    "1": ["Anyone above me","Same or up to two level below","Any level"],
                    "2": ["Yes","No"],
                    "3": ["Career advancement","Skill development", "Introspection & reflection", "Networking & leadership"]
                    },
                    "mentee_que": {"1": "What level of coach & mentor do you want?", "2": "I want a coach & mentor someone from the same department.", "3": "What kind of outcome do you want from these sessions the most?"},
                    "mentor_que": {"1": "What level of participant do you want to coach & mentor?", "2": "I want to coach & mentor someone in the same department.", "3": "What kind of outcome can you support in these sessions the most?"}
                    }
                if fitment_details:
                    fitment_data = fitment_details

                fitment_data["fitment_measures"] = {
                                                    "top": "The score refelcts a robust alignment between the coach and coachee, laying the foundation for an optimal coaching relationship. The coaching relationship is optimal, providing a strong foundation for success. Maintain and nurture open communication and collaboration, as these are key elements in sustaining the excellence of the coaching dynamic.",
                                                    "bottom": "The score signals a notable discord in coaching dynamics, this suggests a reconsideration of the coaching relationship. Misalignment may impede progress, so exploring alternative matches could unveil better synergies and enhance overall effectiveness. Re-evaluate if the coaching partnership aligns with the coachee's goals and needs.",
                                                    "mid": "The score reflects a promising yet moderate fit in coaching dynamics. Acknowledge existing areas for improvement and work collaboratively to address specific concerns. Proactively work on refining coaching dynamics to elevate the overall experience for both the coach and coachee. Continuous effort and attention to areas of improvement can lead to a more effective coaching partnership."
                                                }
                
                initial_qna = {"1": "Before we begin the session, hope you have checked the fitment. In any case, I would like to know more about you - as a person, your challenges, aspirations, and whatever you feel comfortable sharing.", "2": "What do you want to achieve with your session with me today - let me know the goals you have in mind.", "3": "What specific problems you are facing currently that are a priority for you? What have you tried so far in terms of finding your solutions?", "4": "Do you believe your solutions have worked so far? Why or why not?"}
                if initial_questions:
                    initial_qna = initial_questions
                updated_fields = []
                if bot_details:
                    signature_bot.bot_details = bot_details
                    updated_fields.append("bot_details")
                else:
                    signature_bot.bot_details = {"info":bot_attributes['heading']}
                    updated_fields.append("bot_details")

                if bot_attributes:
                    signature_bot.attributes = bot_attributes
                    updated_fields.append("attributes")

                if faqs:
                    signature_bot.faqs = faqs
                    updated_fields.append("faqs")

                if bot_type == BotTypeChoice.avatar_bot:
                    try:
                        prompt = SignatureBot.objects.filter(tenant_id=self.request.tenant.uid,deleted=0).first().custom_prompt
                    except Exception as e:
                        prompt = avatar_bot_default_prompt
                    signature_bot.custom_prompt = prompt
                    updated_fields.append("custom_prompt")

                if all_data:
                    signature_bot.data = all_data
                    updated_fields.append("data")

                if updated_fields:
                    signature_bot.save(update_fields=updated_fields)

                updated_fields = []
                if fitment_answer and bot_type == BotTypeChoice.avatar_bot:
                    bot_att.fitment_answers = {"mentor_answer": fitment_answer.split(",")}
                    bot_att.fitment_data = fitment_data
                    updated_fields.extend(["fitment_answers","fitment_data"])

                if feedback_questions:
                    bot_att.feedback_questions = feedback_questions
                    updated_fields.append("feedback_questions")

                email = data.get('email',None)
                if email:
                    bot_att.coach_email = email
                    updated_fields.append("coach_email")
                

                if initial_qna and bot_type != BotTypeChoice.feedback_bot:
                    bot_att.initial_qnas = initial_qna
                    updated_fields.append("initial_qnas")

                
                if updated_fields:
                    bot_att.save(update_fields=updated_fields)

                # SAVING BOTURL AND bot_snippets
                try: 
                    bot_url =''
                    if bot_type == BotTypeChoice.avatar_bot:
                        bot_url = f"{bot_base_url}/coach/{bot_id}"
                    elif bot_type == BotTypeChoice.feedback_bot:
                        bot_url = f"{bot_base_url}/feedback/{bot_id}"
                    elif bot_type == BotTypeChoice.subject_matter_bot:
                        bot_url = f"{bot_base_url}/subject-expert/{bot_id}"
                    elif bot_type == BotTypeChoice.helper_bot:
                        bot_url = f"{bot_base_url}/subject-expert/{bot_id}"

                    bot_snippet = f"""
                                <div class="deep-chat-poc2" data-bot-id="{bot_id}"></div>
                                <script src="{bot_base_url}/widget/coachbots-stt-widget.js" defer></script>
                                    """
                    coach_profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=0,uid=profile_id)
                    coach_profile.bot_urls = (coach_profile.bot_urls + f", {bot_url}") if coach_profile.bot_urls else bot_url
                    coach_profile.bot_ids = (coach_profile.bot_ids + f", {bot_id}") if coach_profile.bot_ids else bot_id
                    snippet = coach_profile.bot_snippets
                    if snippet:
                        snippet[bot_type] = bot_snippet
                    else:
                        snippet = {f"{bot_type}": bot_snippet}
                    
                    coach_profile.bot_snippets = snippet

                        

                    coach_profile.save(update_fields=["bot_urls","bot_ids","bot_snippets"])

                    if bot_type == BotTypeChoice.avatar_bot:
                        directories = DirectoryPageInfo.objects.filter(profile_id = coach_profile.uid)
                        for directory in directories:
                            directory.avatar_bot_id = bot_id
                            directory.avatar_snippit = bot_snippet
                            directory.avatar_bot_url = bot_url
                            directory.save(update_fields=["avatar_bot_id","avatar_snippit","avatar_bot_url"])

                        
                    if bot_type == BotTypeChoice.feedback_bot:
                        directory = DirectoryPageInfo.objects.filter(profile_id = coach_profile.uid)

                        for direc in directory:
                            direc.feedback_wall = bot_url
                            direc.save(update_fields=['feedback_wall'])

                    
                except Exception as e:
                    logger.exception(f"couldn't save bot_url in CoachCoacheeMentorMenteeProfile")
                
                return Response({"bot_id":signature_bot.bot_id,"bot_uid": signature_bot.uid },status=status.HTTP_200_OK)
            
            except Exception as e:
                logger.exception("Got error while creating bot: {e}")
                try:
                    coach_profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=0,uid=profile_id)
                    coach_profile.deleted = True
                    coach_profile.save(update_fields=["deleted"])
                    DirectoryPageInfo.objects.filter(profile_id=profile_id).delete()
                except Exception as e:
                    logger.error(f"Got error in crating bot : profile_id is missing")

                return Response({"msg":f"Got error : {e}" },status=status.HTTP_400_BAD_REQUEST)

            
        elif request.method == "PATCH":
            bot_id = data.get("bot_id",None)
            try:
                signature_bot = SignatureBot.objects.get(tenant_id=self.request.tenant.uid,uid=bot_id)
            except SignatureBot.DoesNotExist:
                return Response({"error": "SignatureBot not found"}, status=status.HTTP_404_NOT_FOUND)
            
            updated_data = data.get("updated_data",None)

            if updated_data:
                
                additional_data = updated_data.get('additional_data')
                profile_description = additional_data.get("profile_description",None)
                bot_details = signature_bot.bot_details
                bot_details['coach_name'] = updated_data.get("bot_name",None)
                
                
                bot_data = signature_bot.data
                if additional_data:
                    if profile_description:
                        bot_details['info'] = profile_description
                    
                    bot_data["additional_data"] = additional_data

                signature_bot.bot_details = bot_details
                signature_bot.data = bot_data
                signature_bot.save(update_fields=["bot_details","data"])

                bot_att = BotAttribute.objects.get(bot_id=signature_bot.uid)
                
                fitment_answer = updated_data.get('fitment_answers',None)
                email = updated_data.get("email",None)
                updated_fields = []

                if fitment_answer:
                    bot_att.fitment_answers = {"mentor_answer":fitment_answer.split(",")}
                    updated_fields.append("fitment_answers")
                if email:
                    bot_att.coach_email = email
                    updated_fields.append("coach_email")

                bot_att.coach_name = updated_data.get("bot_name",None)
                updated_fields.append("coach_name")

                feedback_questions = updated_data.get("feedback_questions",None)

                if feedback_questions:
                    bot_att.feedback_questions = feedback_questions
                    updated_fields.append("feedback_questions")
                
                bot_att.save(update_fields=updated_fields)

            media_data = data.get('media_data')
            if 'attatched_pdfs' in request.data:
                if media_data is None:
                    media_data = {}
                media_data = json.loads(media_data)
                media_data['attatched_pdfs'] = request.data.getlist('attatched_pdfs')
                logger.info(f"*************** attached_pdfs files in request: {media_data['attatched_pdfs']}")
            extracted_media_data = {}

            logger.info(f"*************** attached_pdfs files in request: {request.data}, $$$$$$$$ {'attatched_pdfs' in request.data}")

            if media_data and signature_bot.bot_type != BotTypeChoice.feedback_bot:
                if 'youtube_links' in media_data:
                    # logger.info(f"################# youtube_links: {media_data['youtube_links']}")
                    youtube_links = media_data['youtube_links']
                    youtube_links = [link.strip() for link in youtube_links.split(',')]

                    print("################# youtube_links: ",youtube_links)

                    #* save these links in bot attributes
                    """ extracted_from_youtube = {}
                    for link in youtube_links:
                        
                        if link != '':
                            transcript_data = download_and_transcribe_audio(link)
                            extracted_from_youtube[link] = transcript_data
                    
                    extracted_media_data['extracted_from_youtube'] = extracted_from_youtube """
                   
                    threading.Thread(target=self.process_and_store_youtube_transcript,args=(youtube_links,signature_bot)).start()


                if 'article_links' in media_data:
                    article_links = media_data['article_links']
                    article_links = [link.strip() for link in article_links.split(',')]

                    logger.info(f"******************* article_links: {article_links}")
                    #* save these links in bot attributes
                    extracted_from_article = {}
                    for link in article_links:
                        
                        if link != '':
                            transcript_data = scrape_article_data(link).get('article_content',None)
                            extracted_from_article[link] = transcript_data
                    
                    # logger.info(f"******************* extracted_from_article: {extracted_from_article}")
                    extracted_media_data['extracted_from_article'] = extracted_from_article
            
            if signature_bot.bot_type != BotTypeChoice.feedback_bot:
                if 'pdf_data' in data:
                    pdf_data = data.getlist('pdf_data')
                    extracted_from_pdf = {}
                    logger.info(f"******************* pdf_data: {pdf_data}")

                    if len(pdf_data) > 0:
                        for index, pdf in enumerate(pdf_data):
                            file_name, text = extract_file_and_text(pdf)
                            extracted_from_pdf[file_name] = text
                    logger.info(f"******************* pdf_data: {extracted_from_pdf}")
                    extracted_media_data['extracted_from_pdf'] = extracted_from_pdf

                if 'doc_data' in data:
                    doc_data = data.getlist('doc_data')
                    extracted_from_doc = {}


                    logger.info(f"******************* doc_data: {doc_data}")
                    if len(doc_data) > 0:
                        for index, doc in enumerate(doc_data):
                            file_name, text = extract_file_and_text(doc)
                            extracted_from_doc[file_name] = text

                    logger.info(f"******************* doc_data: {extracted_from_doc}")
                    extracted_media_data['extracted_from_doc'] = extracted_from_doc
                
                if (media_data and 'attached_docs' in media_data) or 'attached_docs' in request.FILES:
                    attached_docs = media_data['attached_docs'] if 'attached_docs' in media_data else request.FILES.getlist('attached_docs')
                    doc_names = []
                    extracted_from_doc = {}

                    for file in attached_docs:
                        # logger.info(f"file name : {file.name}, {file.read()}")
                        doc_names.append(file.name)
                        path = default_storage.save(file.name, ContentFile(file.read()))
                        doc_content = extract_text_from_doc(path)
                        default_storage.delete(path)
                        extracted_from_doc[file.name] = doc_content

                    extracted_media_data['extracted_from_doc'] = extracted_from_doc
                    
                if (media_data and 'attatched_pdfs' in media_data) or 'attatched_pdfs' in request.FILES:
                    attatched_pdfs = media_data['attatched_pdfs'] if 'attatched_pdfs' in media_data else request.FILES.getlist('attatched_pdfs')
                    pdf_names = []
                    extracted_from_pdf = {}

                    """ logger.info(f"******************* attatched_pdfs: {attatched_pdfs}") """

                    for file in attatched_pdfs:
                        # logger.info(f"file name : {file.name}, {file.read()}")
                        pdf_names.append(file.name)
                        
                        path = default_storage.save(file.name, ContentFile(file.read()))

                        pdf_content = extract_text_from_pdf(path)

                        default_storage.delete(path)
                        extracted_from_pdf[file.name] = pdf_content

                

                    extracted_media_data['extracted_from_pdf'] = extracted_from_pdf

                    logger.info(f"******************* extracted_from_pdf: {extracted_from_pdf}")

                logger.info(f"######### extracted media data : {extracted_media_data}")

            if extracted_media_data:
                signature_bot.data['media_data'] = extracted_media_data
                signature_bot.save()

            # if updated_data:
            #     # Update the instance with the new data
            #     sig_bot_updates = updated_data.get('signature_bot',None)
            #     bot_att_updates = updated_data.get('bot_attributes',None)
            #     updated_fields = []
            #     if sig_bot_updates:
            #         for key, value in sig_bot_updates.items():
            #             setattr(signature_bot, key, value)
            #             updated_fields.append(key)
            #         # Save the updated instance
            #         signature_bot.save(update_fields=updated_fields)

            #     if bot_att_updates:
            #         updated_fields = []
            #         bot_att = BotAttribute.objects.get(bot_id=signature_bot.uid)
            #         for key, value in bot_att_updates.items():
            #             setattr(signature_bot, key, value)
            #             updated_fields.append(key)
            #         # Save the updated instance
            #         bot_att.save(update_fields=updated_fields)
                

            return Response({"msg": "updated"}, status=status.HTTP_200_OK)


    @action(methods=['GET','POST'],detail=False, url_path="user-competency-details")
    def user_competency_details(self,request,*args, **kwargs):
        """
        Retrieves or updates the competency details of a user based on their user ID.

        Args:
            request (object): The HTTP request object.
            user_id (string): The ID of the user for whom the competency details are being retrieved or updated.
            method (string): The HTTP method used for the request ('GET' or 'POST').

        Returns:
            If the HTTP method is 'GET', the method returns a list containing the competency data of the user.
            If the HTTP method is 'POST', the method returns a response with a success message.
        """
        try:
            data = []
            user_id = request.query_params.get('user_id')
            if request.method == 'GET':
                competency_data = UserAttribute.objects.get(user_id=user_id).competency_data
                if competency_data:
                    data.append(competency_data)

                return Response(data,status=status.HTTP_200_OK)
            elif request.method == 'POST':
                skill_data = request.query_params.get('competency_skills')
                skill_data = {str(i+1): value for i, value in enumerate(skill_data.split(','))}
                user_att = UserAttribute.objects.get(user_id=user_id)
                user_att.competency_data = skill_data
                user_att.save(update_fields=["competency_data"])
                return Response({"msg":"saved"},status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"got error {e}"},status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET','POST','PATCH'],detail=False, url_path="get_or_create_idp")
    def get_or_create_idp(self,request,*args, **kwargs):
        """
        This method is used to get or create an Individual Development Plan (IDP) based on the HTTP method in the request.

        The method supports GET, POST, and PATCH HTTP methods. 

        For a GET request, it retrieves an existing IDP. The 'user_id' and 'idp_id' are expected to be provided as query parameters. 
        If 'idp_id' is provided, it tries to fetch the IDP with that ID. If not, it fetches the IDP for the provided 'user_id'. 

        For a POST request, it creates a new IDP. The 'user_id' and 'idp_data' are expected to be provided in the request data. 
        The 'idp_data' should contain the necessary information to create the IDP.

        For a PATCH request, it regenerates the IDP or scenarios. The 'idp_id' is expected to be provided in the request data.

        Args:
            request (HttpRequest): The HTTP request object. Depending on the HTTP method, it should contain:
                - GET: 'user_id' and optionally 'idp_id' as query parameters.
                - POST: 'user_id' and 'idp_data' in the request data.
                - PATCH: 'idp_id' in the request data.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: The HTTP response object containing the IDP data and HTTP status. 
            If the operation is successful, it returns the IDP data with HTTP status 200. 
            If not, it returns an error message with HTTP status 404 for GET and POST, and 400 for exceptions.

        Example:
            For a GET request:
            Request: GET /get_or_create_idp?user_id=123
            Response: {
                "idp_data": {...},
                "status": "completed"
            }, status=200
        """
        try:
            access_token = request.headers.get('Authorization')

            if request.method == 'GET':
                # user_id = request.data.get('user_id',None)
                user_id = request.query_params.get('user_id',None)
                idp_id = request.query_params.get('idp_id',None)
                if idp_id is not None:
                    data, success = process_idp("",user_id,request.tenant.uid,access_token,only_data=True,idp_id=idp_id)
                    if not success:
                        return Response(data,status=status.HTTP_404_NOT_FOUND)
                    return Response(data,status=status.HTTP_200_OK)


                data, success = process_idp("",user_id,request.tenant.uid,access_token,only_data=True)
                if not success:
                    return Response(data,status=status.HTTP_404_NOT_FOUND)
                return Response(data,status=status.HTTP_200_OK)
            
            elif request.method == 'POST':
                user_id = request.data.get('user_id',None)
                idp_data = request.data.get('idp_data',None)
                logger.info(f"****************** idp_data: {idp_data}")
                data, success = process_idp(idp_data,user_id,request.tenant.uid,access_token)
                if not success:
                    return Response(data,status=status.HTTP_404_NOT_FOUND)
                return Response(data,status=status.HTTP_200_OK)
            
            elif request.method == 'PATCH':
                idp_id = request.data.get('idp_id',None)
                logger.info(f"****************** idp_id: {idp_id}")
                data, success = regenerate_idp_or_scenarios(idp_id=idp_id,access_token=access_token,tenant_id=request.tenant.uid)
                return Response(data,status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"got error in get_or_create_idp: {e}")
            return Response({"msg": "got_error"},status=status.HTTP_400_BAD_REQUEST)
          
          
    @action(methods=['GET'],detail=False, url_path="get-directory-informations")
    def get_directory_informations(self,request,*args, **kwargs):
        """
        Retrieves directory information based on the provided email in the request query parameters.

        This method first checks if an email is provided in the request query parameters. If an email is provided, it fetches the client information associated with the email. 
        It then retrieves all identities associated with the emails of the client and fetches the profiles associated with these identities. 
        If the client has accessed any bots, it also fetches the profiles associated with these bots. 
        Finally, it retrieves all directory information that is visible, approved, and associated with these profiles.

        If no email is provided, it simply retrieves all directory information that is visible and approved.

        Args:
            request (HttpRequest): The HTTP request object. The request query parameters may contain an 'email' key with the email as the value.

        Returns:
            HttpResponse: The HTTP response object containing the serialized directory information data. 
            The data is a list of dictionaries where each dictionary represents a directory information. 
            Each dictionary contains keys like 'id', 'name', 'description', etc. representing the directory information attributes.

        Raises:
            HTTP_400_BAD_REQUEST: If there is any error during the process, an error message is returned with a status of 400.

        Example:
            Input: 
                request.query_params = {'email': 'test@example.com'}
            Output: 
                [
                    {
                        'id': 1,
                        'name': 'Directory 1',
                        'description': 'This is directory 1',
                        ...
                    },
                    {
                        'id': 2,
                        'name': 'Directory 2',
                        'description': 'This is directory 2',
                        ...
                    },
                    ...
                ]
        """
        try:
            email = request.query_params.get('email')
            if email:
                client = ClientUserInfo.objects.get(deleted=0,tenant_id=request.tenant.uid,member_emails__icontains=email)
                emails = client.member_emails.split(',')
                emails = [email.strip() for email in emails]
                user_ids = Identity.objects.filter(deleted=False,tenant_id=request.tenant.uid,value__in = emails)
                user_ids_list = list(user_ids.values_list('user_id', flat=True))
                profile_ids = list(CoachCoacheeMentorMenteeProfile.objects.filter(deleted=0,tenant_id=request.tenant.uid,user_id__in=user_ids_list).values_list("uid",flat=True))
                
                if client.accessed_bot_ids:
                    bot_ids = client.accessed_bot_ids.split(',')
                    bot_profile_ids = []
                    for bot_id in bot_ids:
                        bot_profile_ids.extend(list(CoachCoacheeMentorMenteeProfile.objects.filter(bot_ids__contains=bot_id).values_list("uid",flat=True)))
                    profile_ids.extend(bot_profile_ids)
                    profile_ids = list(set(profile_ids))
                    logger.info(f"accessed_bots: {bot_ids},bot_profile_ids: {bot_profile_ids}, profile_ids: {profile_ids}")

                directories = DirectoryPageInfo.objects.filter(is_visible=True,is_approved=True,profile_id__in = profile_ids)
                serializer = DirectoryInfoSErializer(directories,many=True)
            else:
                directories = DirectoryPageInfo.objects.filter(is_visible=True,is_approved=True)
                serializer = DirectoryInfoSErializer(directories,many=True)
                
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception({"got error in directory information api": e})
            return Response({"error": f"got error {e}"},status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'],detail=False,url_path="participant-leader-board-report")
    def participant_leader_board_report(self,request, *args, **kwargs):
        """
        Retrieves a leaderboard report for participants based on their activities.

        This method fetches the client information based on the provided email in the request query parameters.
        It then retrieves all the users associated with the client and fetches their action information.
        The method constructs a report for each user, including their name, user_id, counts of different bot interactions,
        total simulations, session notes count, and profile type. If a user has a 'coach' profile type, it is updated in the report.
        The total score is calculated as the sum of total bots, session notes count, total simulations, and total bot interactions.
        If a user does not have any action information, a report is still created for them with all counts as zero.
        Finally, the method sorts the data based on the total score in descending order and assigns a rating to each user based on their position in the sorted list.

        Args:
            request (object): The HTTP request object. The request query parameters should include an 'email' field.

        Returns:
            Response: A list of dictionaries, each containing the following fields:
                - name: The display name of the user.
                - user_id: The unique identifier of the user.
                - avatar_bot_count: The count of avatar bot interactions.
                - subject_matter_count: The count of subject matter bot interactions.
                - total_bots: The total count of bot interactions.
                - total_simulations: The total count of simulations attempted.
                - total_bot_interactions: The total count of bot interactions attempted.
                - session_notes_count: The count of session notes.
                - profile_type: The profile type of the user, either 'coachee' or 'coach'.
                - total_score: The total score calculated as the sum of total bots, session notes count, total simulations, and total bot interactions.
                - rating: The rating of the user based on their total score.

        Example:
            [
                {
                    "name": "John Doe",
                    "user_id": "123",
                    "avatar_bot_count": 5,
                    "subject_matter_count": 3,
                    "total_bots": 8,
                    "total_simulations": 2,
                    "total_bot_interactions": 10,
                    "session_notes_count": 4,
                    "profile_type": "coach",
                    "total_score": 24,
                    "rating": 1
                },
                ...
            ]
        """
        try:
            if request.method == "GET":
                email = request.query_params.get('email')
                client = ClientUserInfo.objects.get(deleted=0,tenant_id=request.tenant.uid,member_emails__icontains=email)
                emails = client.member_emails.split(',')
                emails = [email.strip() for email in emails]
                user_ids = Identity.objects.filter(deleted=False,tenant_id=request.tenant.uid,value__in = emails)
                user_ids_list = list(user_ids.values_list('user_id', flat=True))
                user_actions = UserActionInfo.objects.filter(deleted=False,tenant_id=request.tenant.uid,user_id__in=user_ids_list)
                data = []
                for user_action in user_actions:
                    user = get_user_by_id(user_action.user_id)
                    temp = {
                        "name": get_user_display_name(user),
                        "user_id": user.uid,
                        "avatar_bot_count": user_action.avatar_bot_count,
                        "subject_matter_count": user_action.subject_matter_bot_count,
                        "total_bots": user_action.avatar_bot_count + user_action.subject_matter_bot_count,
                        "total_simulations": user_action.interaction_attempted,
                        "total_bot_interactions": user_action.chat_attempted,
                        "session_notes_count": user_action.session_notes_count,
                        "profile_type": "coachee"
                    }
                    profiles = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=request.tenant.uid,user_id=user.uid)
                    for p in profiles:
                        if p.profile_type == ProfileTypeChoice.coach:
                            temp['profile_type'] = p.profile_type

                    temp['total_score'] = temp['total_bots'] + temp['session_notes_count'] + temp['total_simulations'] + temp['total_bot_interactions']
                    data.append(temp)

                existing_user_ids = set(user_action.user_id for user_action in user_actions)
                # Iterate through user_ids and include those not present in user_actions
                for user_id in user_ids_list:
                    if user_id not in existing_user_ids:
                        user = get_user_by_id(user_id)
                        profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=request.tenant.uid,user_id=user_id).first()
                        temp = {
                            "name": get_user_display_name(user),
                            "user_id": user.uid,
                            "avatar_bot_count": 0, 
                            "subject_matter_count": 0,
                            "total_bots": 0,
                            "total_simulations": 0,
                            "total_bot_interactions": 0,
                            "session_notes_count": 0,
                            "profile_type": profile.profile_type if profile else 'coachee',
                            'total_score': 0
                        }
                        profiles = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False, tenant_id=request.tenant.uid, user_id=user.uid)
                        for p in profiles:
                            if p.profile_type == ProfileTypeChoice.coach:
                                temp['profile_type'] = p.profile_type

                        data.append(temp)
                    
                data = sorted(data, key=lambda x: x['total_score'], reverse=True)
                for i, item in enumerate(data, start=1):
                    item['rating'] = i

                return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)


    @action(methods=['GET','POST','PATCH'],detail=False, url_path="coach-coachee-connections")
    def coach_coachee_connections(self, request, *args, **kwargs):
        """
        This method handles GET, POST, and PATCH requests for coach-coachee connections.

        For GET requests, it retrieves coach-coachee connections based on the provided query parameters: 'connection_id', 'user_id', 'coach_id', and 'coachee_id'. 
        If no parameters are provided, it returns all connections for the current tenant.

        For POST requests, it creates a new coach-coachee connection. It requires 'coach_id', 'coachee_id', and 'profile_page_url' in the request data. 
        After creating the connection, it sends an email to the coach with a connection request.

        For PATCH requests, it updates an existing coach-coachee connection. It requires 'connection_id' or both 'coach_id' and 'coachee_id' in the request data. 
        It also updates the connection status and sends an email to the coachee if the status is 'accepted'.

        Input:
            request: A Django HttpRequest object. Contains metadata about the request.
                For GET, it may contain query parameters 'connection_id', 'user_id', 'coach_id', 'coachee_id'.
                For POST, it must contain 'coach_id', 'coachee_id', and 'profile_page_url' in request.data.
                For PATCH, it must contain 'connection_id' or both 'coach_id' and 'coachee_id' in request.data.

        Output:
            A Django HttpResponse object. Contains the serialized data of the coach-coachee connections or an error message.

        Example:
            GET /coach-coachee-connections?coach_id=1
            Response: {"data": [{"connection_id": 1, "coach_id": 1, "coachee_id": 2, "status": "accepted"}]}

            POST /coach-coachee-connections
            Request data: {"coach_id": 1, "coachee_id": 2, "profile_page_url": "http://example.com/profile"}
            Response: {"data": {"connection_id": 1, "coach_id": 1, "coachee_id": 2, "status": "pending"}}

            PATCH /coach-coachee-connections
            Request data: {"connection_id": 1, "status": "accepted"}
            Response: {"data": {"connection_id": 1, "coach_id": 1, "coachee_id": 2, "status": "accepted"}}
        """
        if request.method == 'GET':
            connection_id = request.query_params.get('connection_id',None)
            user_id = request.query_params.get('user_id',None)
            coach_id = request.query_params.get('coach_id',None)
            coachee_id = request.query_params.get('coachee_id',None)
            if coach_id:
                try:
                    connection = CoachCoacheeConnection.objects.filter(deleted=False,coach_id=coach_id, tenant_id=self.request.tenant.uid)
                    return Response({"data": CoachCoacheeConnectionSerializer(connection,many=True).data },status=status.HTTP_200_OK)
                except Exception as e:
                    logger.exception(e)
                    return Response({"error":"connection not found"},status=status.HTTP_404_NOT_FOUND)
            if connection_id:
                try:
                    connection = CoachCoacheeConnection.objects.get(deleted=False,uid=connection_id,tenant_id=self.request.tenant.uid)
                    return Response({"data": CoachCoacheeConnectionSerializer(connection).data },status=status.HTTP_200_OK)
                except Exception as e:
                    logger.exception(e)
                    return Response({"error":"connection not found"},status=status.HTTP_404_NOT_FOUND)
                
            if coachee_id:
                try:
                    connection = CoachCoacheeConnection.objects.filter(deleted=False,coachee_id=coachee_id, tenant_id=self.request.tenant.uid)
                    return Response({"data": CoachCoacheeConnectionSerializer(connection,many=True).data },status=status.HTTP_200_OK)
                except Exception as e:
                    logger.exception(e)
                    return Response({"error":"connection not found"},status=status.HTTP_404_NOT_FOUND)
            
            # sending only that client members data
            email = request.query_params.get('email')
            client = ClientUserInfo.objects.get(deleted=0,tenant_id=request.tenant.uid,member_emails__icontains=email)
            emails = client.member_emails.split(',')
            emails = [email.strip() for email in emails]
            user_ids = Identity.objects.filter(deleted=False,tenant_id=request.tenant.uid,value__in = emails)
            user_ids_list = list(user_ids.values_list('user_id', flat=True))
            profile_ids = list(CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=request.tenant.uid,user_id__in=user_ids_list).values_list('uid', flat=True))
            logger.info(f"profile_ids: {profile_ids}, user_ids: {user_ids_list}")

            connections = CoachCoacheeConnection.objects.filter(Q(coach_id__in=profile_ids) | Q(coachee_id__in=profile_ids),
                                                                deleted=False,
                                                                tenant_id=self.request.tenant.uid,
                                                                )
            return Response({"data": CoachCoacheeConnectionSerializer(connections,many=True).data },status=status.HTTP_200_OK)

        if request.method == 'PATCH':
            connection_id = request.data.get('connection_id',None)
            coach_id = request.data.get('coach_id',None)
            coachee_id = request.data.get('coachee_id',None)

            if connection_id:
                connection = CoachCoacheeConnection.objects.get(deleted=False,uid=connection_id)
                
                data = request.data.copy()
                coach = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,tenant_id=request.tenant.uid,uid=connection.coach_id)
                coachee = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,tenant_id=request.tenant.uid,uid=connection.coachee_id)
                
                coach_name = coach.name
                coachee_name = coachee.name
                coachee_email = coachee.email
                # serializer = CoachCoacheeConnectionSerializer(connection,data=data,partial=True)
                # serializer.is_valid(raise_exception=True)
                # serializer.save()

                if data.get('status') == CoachCoacheeConnectionStatusChoice.accepted:
                    connection.status = CoachCoacheeConnectionStatusChoice.accepted
                    connection.save(update_fields=['status'])
                    subject = "Connection Approved"
                    html = f"""
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                                <tr>
                                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;"> Congratuations,{coach_name} has approved your connection request.</p>

                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
                                </td>
                                </tr>
                        </table>
                        """

                    send_email_with_html_template(subject=subject,html_content=html,to_email=coachee_email)
                    return Response({"data": CoachCoacheeConnectionSerializer(connection).data },status=status.HTTP_200_OK)
                else:
                    connection.status = CoachCoacheeConnectionStatusChoice.rejected
                    connection.save(update_fields=['status'])
                    return Response({"data": CoachCoacheeConnectionSerializer(connection).data },status=status.HTTP_200_OK)
            
            if coach_id and coachee_id:
                connection = CoachCoacheeConnection.objects.get(deleted=False,coach_id=coach_id,coachee_id=coachee_id)
                data = request.data.copy()
                # serializer = CoachCoacheeConnectionSerializer(connection,data=data,partial=True)
                # serializer.is_valid(raise_exception=True)
                # serializer.save()

                if data.get('status') == CoachCoacheeConnectionStatusChoice.accepted:
                    connection.status = CoachCoacheeConnectionStatusChoice.accepted
                    connection.save(update_fields=['status'])
                    coach = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,tenant_id=request.tenant.uid,uid=coach_id)
                    coachee = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,tenant_id=request.tenant.uid,uid=coachee_id)
                    
                    coach_name = coach.name
                    coachee_name = coachee.name
                    coachee_email = coachee.email
                    subject = "Connection Approved"
                    html = f"""
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                                <tr>
                                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;"> Congratuations,{coach_name} as approved your connection request.</p>

                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
                                </td>
                                </tr>
                        </table>
                        """

                    send_email_with_html_template(subject=subject,html_content=html,to_email=coachee_email)
                    return Response({"data": CoachCoacheeConnectionSerializer(connection).data },status=status.HTTP_200_OK)
                else:
                    connection.status = CoachCoacheeConnectionStatusChoice.rejected
                    connection.save(update_fields=['status'])
                    return Response({"data": CoachCoacheeConnectionSerializer(connection).data },status=status.HTTP_200_OK)

        if request.method == 'POST':
            coach_id = request.data.get('coach_id',None)
            coachee_id = request.data.get('coachee_id',None)
            profile_url = request.data.get('profile_page_url')

            logger.info(f"***************** request data: {request.data}")

            if None in [coach_id,coachee_id]:
                return Response({"error":"coach_id and coachee_id are required"},status=status.HTTP_400_BAD_REQUEST)
            
            try:
                coach = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False, uid=coach_id)
                bot_ids = coach.bot_ids.split(',')
                if len(bot_ids) == 0:
                    return Response({"error":"coach doesn't have any bot"},status=status.HTTP_400_BAD_REQUEST)
                
                avatar_bot_id = None
                for bot_id in bot_ids:
                    bot = SignatureBot.objects.get(deleted=False,bot_id=bot_id.strip())
                    if bot.bot_type == BotTypeChoice.avatar_bot:
                        avatar_bot_id = bot.bot_id

                if avatar_bot_id is None:
                    return Response({"error":"coach doesn't have any avatar bot"},status=status.HTTP_400_BAD_REQUEST)


            except Exception as e:
                logger.exception(e)
                return Response({"error":"coach not found"},status=status.HTTP_404_NOT_FOUND)

            data = request.data.copy()
            data['tenant_id'] = self.request.tenant.uid
            data['coach_avatar_bot_id'] = avatar_bot_id
            serializer = CoachCoacheeConnectionSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            created_connection = serializer.save()
            coach = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,tenant_id=request.tenant.uid,uid=coach_id)
            coachee = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,tenant_id=request.tenant.uid,uid=coachee_id)
            
            coach_name = coach.name
            coachee_name = coachee.name
            coachee_email = coachee.email
            subject = "you have a connection request"
            html = f"""
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;"> Dear {coach_name},  One of the participants has requested to confirm connecrtion. You can do so via visiting your profile page here. <a href={profile_url} >Profile page </a> . Thanks! </p>

                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
                        </td>
                        </tr>
                </table>
                """

            send_email_with_html_template(subject=subject,html_content=html,to_email=coach.email)
            return Response({"data": CoachCoacheeConnectionSerializer(created_connection).data },status=status.HTTP_201_CREATED)
            
            
    @action(methods=['GET'],detail=False,url_path="feedback-leaderboard-report")
    def feedback_leader_board(self,request, *args, **kwargs):
        """
        Generates a feedback leaderboard report for a given client.

        This method retrieves the client's information using the email provided in the request's query parameters.
        It then fetches all the identities associated with the client's member emails and retrieves all the feedback 
        provided by these users from the BotQnA model. The feedback is grouped by bot_id and for each bot, the number 
        of positive and negative feedback is calculated. The bot's name and owner's name are also retrieved. All this 
        information is then formatted and appended to a list. The list is sorted in descending order based on the number 
        of positive feedback. Finally, a rating is assigned to each bot based on its position in the sorted list.

        Args:
            request (HttpRequest): The HTTP request object. The request's query parameters should contain an 'email' field 
            which is the email of the client for whom the report is to be generated.

        Returns:
            HttpResponse: The HTTP response object containing the feedback leaderboard report. The report is a list of 
            dictionaries where each dictionary contains the following keys:
                - 'bot_name': The name of the bot.
                - 'user_id': The user id of the bot's owner.
                - 'owner_name': The display name of the bot's owner.
                - 'positive_feedback_count': The number of positive feedback for the bot.
                - 'negative_feedback_count': The number of negative feedback for the bot.
                - 'rating': The bot's rating based on the number of positive feedback. The bot with the highest number 
                of positive feedback has a rating of 1.

        Example:
            Request: GET /feedback-leaderboard-report?email=client@example.com
            Response: 
            {
                "group": [
                    {
                        "bot_name": "Bot 1",
                        "user_id": 1,
                        "owner_name": "Owner 1",
                        "positive_feedback_count": 10,
                        "negative_feedback_count": 2,
                        "rating": 1
                    },
                    {
                        "bot_name": "Bot 2",
                        "user_id": 2,
                        "owner_name": "Owner 2",
                        "positive_feedback_count": 8,
                        "negative_feedback_count": 3,
                        "rating": 2
                    },
                    ...
                ]
            }
        """
        try:
            if request.method == "GET":
                email = request.query_params.get('email')
                client = ClientUserInfo.objects.get(deleted=0,tenant_id=request.tenant.uid,member_emails__icontains=email)
                emails = client.member_emails.split(',')
                emails = [email.strip() for email in emails]
                user_ids = Identity.objects.filter(deleted=False,tenant_id=request.tenant.uid,value__in = emails)
                user_ids_list = list(user_ids.values_list('user_id', flat=True))
                feedback_bots = SignatureBot.objects.filter(deleted=False,tenant_id=request.tenant.uid,user_id__in=user_ids_list,bot_type=BotTypeChoice.feedback_bot)
                # bot_qnas = BotQnA.objects.filter(deleted=False,tenant_id=request.tenant.uid,qna_type='feedback',participant_id__in=user_ids_list)

                # Sort the queryset by bot_id
                # bot_qnas = sorted(bot_qnas, key=lambda x: x.bot_id)

                # Group the sorted queryset by bot_id
                # grouped_bot_qnas = groupby(bot_qnas, key=attrgetter('bot_id'))
                formatted_data = []
                for bot in feedback_bots:
                    bot_id = bot.uid
                    bot_qnas = BotQnA.objects.filter(deleted=False,tenant_id=request.tenant.uid,qna_type='feedback',bot_id=bot_id)
                    positive_count = sum(1 for item in bot_qnas if item.is_positive)
                    negative_count = sum(1 for item in bot_qnas if not item.is_positive)
                    bot_name = BotAttribute.objects.get(bot_id=bot_id).bot_name
                    owner_name = get_user_display_name(get_user_by_id(bot.user_id))

                    formatted_entry = {
                        "bot_name": bot_name,
                        "user_id": bot.user_id,
                        "owner_name": owner_name,
                        "positive_feedback_count": positive_count,
                        "negative_feedback_count": negative_count
                    }
                    formatted_data.append(formatted_entry)
                    
                    
                # for bot_id, group in grouped_bot_qnas:
                #     positive_count = sum(1 for item in group if item.is_positive)
                #     negative_count = sum(1 for item in group if not item.is_positive)
                #     signature_bot = SignatureBot.objects.get(uid=bot_id)
                #     bot_name = BotAttribute.objects.get(bot_id=bot_id).bot_name
                #     owner_name = get_user_display_name(get_user_by_id(signature_bot.user_id))

                #     formatted_entry = {
                #         "bot_name": bot_name,
                #         "user_id": signature_bot.user_id,
                #         "owner_name": owner_name,
                #         "positive_feedback_count": positive_count,
                #         "negative_feedback_count": negative_count
                #     }
                #     formatted_data.append(formatted_entry)


                formatted_data = sorted(formatted_data, key=lambda x: x["positive_feedback_count"], reverse=True)
                for rating, item in enumerate(formatted_data,start=1):
                    item['rating'] = rating

                return Response({'group': formatted_data},status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(e)
            return  Response({"Error": f"Got Error in Feedback-leaderboard-report : {e}"},status=status.HTTP_400_BAD_REQUEST)
