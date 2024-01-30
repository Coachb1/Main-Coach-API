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
from apis.accounts.serializers import SetupAccountSerializer, CoachCoacheeMentorMenteeProfileSerializer, SignatureBotSerializer, BotAttributeSerializer,DirectoryInfoSErializer
from clients.permissions import IsAuthenticatedClient
from tests.models import TestAttemptSession, Test
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from identities.helpers import get_user_via_identity
from pdf_generator.helpers import get_participant_report
from users.helpers import upsert_user_attributes
from users.models import CoachCoacheeMentorMenteeProfile, User, UserAttribute
from users.choices import BotTypeChoice
from tenants.models import Tenant
from tests.choices import TestAttemptSessionStatusChoices
from users.models import SignatureBot, BotAttribute, ClientUserInfo
from users.choices import StatusChoice, ProfileTypeChoice


from identities.models import Identity
from skills.models import SkillsRating
from utilities.models import BotQnA, DirectoryPageInfo
from users.db import get_user_by_id,get_user_display_name
import json
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from email_sender.helpers import send_generic_email
from utilities.helpers import extract_fields
from commons.langchain import download_and_transcribe_audio, extract_text_from_pdf
from coaching_conversations.helpers import avatar_bot_default_prompt
from utilities.helpers import process_idp

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

            if not signature_bot.is_system_bot and not signature_bot.is_sample_bot:
                data['owner_profile_image'] = coach_profile[0].profile_image_url
            
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
                        "is_demo_user": demo_user
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
            user_id = request.query_params.get('user_id',None)
            if user_id:
                try:
                    profile = CoachCoacheeMentorMenteeProfile.objects.filter(user_id=user_id)[0]
                    return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profile).data },status=status.HTTP_200_OK)
                except Exception as e:
                    logger.exception(e)
                    return Response({"error":"profile not found"},status=status.HTTP_404_NOT_FOUND)
            if profile_id:
                try:
                    profile = CoachCoacheeMentorMenteeProfile.objects.get(uid=profile_id)
                    return Response({"data": CoachCoacheeMentorMenteeProfileSerializer(profile).data },status=status.HTTP_200_OK)
                except Exception as e:
                    logger.exception(e)
                    return Response({"error":"profile not found"},status=status.HTTP_404_NOT_FOUND)
            else:
                profiles = CoachCoacheeMentorMenteeProfile.objects.filter(is_approved=True)
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
                    favourite_simulation_codes=created_profile.favourite_simulation_codes,
                    status=StatusChoice.available,
                    skills=created_profile.hard_skill_areas,
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
        
            bot_type = data.get('bot_type')
            if bot_type is None or bot_type == '' or bot_type not in [choice[0] for choice in BotTypeChoice.choices]:
                return Response({"error": "bot_type is required"},status=status.HTTP_400_BAD_REQUEST)


            participant_id = data.get('participant_id')
            if participant_id is None or participant_id == '':
                return Response({"error": "participant_id is required"},status=status.HTTP_400_BAD_REQUEST)

            bot_name = data.get('bot_name')
            if bot_name is None or bot_name == '':
                return Response({"error": "bot_name is required"},status=status.HTTP_400_BAD_REQUEST)

            bot_id = "-".join([bot_type, participant_id[:5], bot_name])
            existing_bots = SignatureBot.objects.filter(bot_id=bot_id)
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

            bot_details["is_login_required"] = False
            bot_details["is_strict_login_required"] = False
            

            all_data = {}

            if additional_data:
                all_data['additional_data'] = additional_data

            print("################# media_data: ",media_data)

            if media_data and bot_type != BotTypeChoice.feedback_bot:
                if 'youtube_links' in media_data:
                    youtube_links = media_data['youtube_links']
                    youtube_links = [link.strip() for link in youtube_links.split(',')]

                    print("################# youtube_links: ",youtube_links)

                    #* save these links in bot attributes

                    for link in youtube_links:
                        if link != '':
                            transcript_data = download_and_transcribe_audio(link)
                            all_data[link] = transcript_data

                # if 'pdf_links' in media_data:
                #     pdf_links = media_data['pdf_links']
                #     pdf_links = [link.strip() for link in pdf_links.split(',')]

                #     #* save these links in bot attributes

                #     for link in pdf_links:
                #         transcript_data = extract_text_from_pdf(link)
                #         all_data[link] = transcript_data


            signature_bot = SignatureBot.objects.create(
                bot_id=bot_id,
                tenant_id=self.request.tenant.uid,
                user_id=participant_id,
                bot_type=bot_type,
            )
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
                signature_bot.custom_prompt = avatar_bot_default_prompt()
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

            if initial_qna and bot_type != BotTypeChoice.feedback_bot:
                bot_att.initial_qnas = initial_qna
                updated_fields.append("initial_qnas")

            
            if updated_fields:
                bot_att.save(update_fields=updated_fields)

            # SAVING BOTURL AND bot_snippets
            try: 
                bot_url =''
                if bot_type == BotTypeChoice.avatar_bot:
                    bot_url = f"{bot_base_url}/{bot_id}"
                elif bot_type == BotTypeChoice.feedback_bot:
                    bot_url = f"{bot_base_url}/feedback/{bot_id}"
                elif bot_type == BotTypeChoice.subject_matter_bot:
                    bot_url = f"{bot_base_url}/subject-expert/{bot_id}"
                if bot_type == BotTypeChoice.avatar_bot:
                    bot_url = f"{bot_base_url}/helper/{bot_id}"

                bot_snippet = f"""
                            <div class="deep-chat-poc2" data-bot-id="{bot_id}">jiks</div>
                            <script src="{bot_base_url}/widget/coachbots-stt-widget.js" defer></script>
                                """
                coach_profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=0,user_id=participant_id)
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
            

            return Response({"bot_id":signature_bot.bot_id },status=status.HTTP_200_OK)
        
        elif request.method == "PATCH":
            bot_id = data.get("bot_id",None)
            try:
                signature_bot = SignatureBot.objects.get(id=bot_id)
            except SignatureBot.DoesNotExist:
                return Response({"error": "SignatureBot not found"}, status=status.HTTP_404_NOT_FOUND)
            
            updated_data = data.get("updated_data",None)
            if updated_data:
                # Update the instance with the new data
                sig_bot_updates = updated_data['signature_bot']
                bot_att_updates = updated_data['bot_attributes']
                updated_fields = []
                if sig_bot_updates:
                    for key, value in sig_bot_updates.items():
                        setattr(signature_bot, key, value)
                        updated_fields.append(key)
                    # Save the updated instance
                    signature_bot.save(update_fields=updated_fields)

                if bot_att_updates:
                    updated_fields = []
                    bot_att = BotAttribute.objects.get(bot_id=signature_bot.uid)
                    for key, value in bot_att_updates.items():
                        setattr(signature_bot, key, value)
                        updated_fields.append(key)
                    # Save the updated instance
                    bot_att.save(update_fields=updated_fields)
                

            return Response({"msg": "updated"}, status=status.HTTP_200_OK)


    @action(methods=['GET','POST'],detail=False, url_path="user-competency-details")
    def user_competency_details(self,request,*args, **kwargs):

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
        

    @action(methods=['GET','POST'],detail=False, url_path="get_or_create_idp")
    def get_or_create_idp(self,request,*args, **kwargs):
        
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
                return Response(data,status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"got error in get_or_create_idp: {e}")
            return Response({"msg": "got_error"},status=status.HTTP_400_BAD_REQUEST)
          
          
    @action(methods=['GET'],detail=False, url_path="get-directory-informations")
    def get_directory_informations(self,request,*args, **kwargs):

        try:
            directories = DirectoryPageInfo.objects.filter(is_visible=True)
            serializer = DirectoryInfoSErializer(directories,many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception({"got error in directory information api": e})
            return Response({"error": f"got error {e}"},status=status.HTTP_400_BAD_REQUEST)
