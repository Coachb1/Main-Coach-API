from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
import pytz
import datetime

from apis.tests_attempt_session.serializers import TestAttemptSessionSerializer
from clients.permissions import IsAuthenticatedClient
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from commons.utils import generic_completion
from tests.helpers import get_meeting_report_from_test_attempt_session
from tests.helpers import get_skills_tracker_data, calculate_similarity
from tests.helpers import create_test_question_answer_session
from pdf_generator.helpers import get_report_from_test_attempt_session, update_skill_name
from tests.models import TestAttemptSession, TestQuestion, TestQuestionResponse
from tests.models import Test
from users.db import get_user_display_name, get_user_by_id
from tests.choices import TestAttemptSessionStatusChoices
from tests.helpers import (send_report_link_to_email, send_report_link_to_email_orch, get_group_discussion_chat_conversation, send_report_link_to_whatsapp,
                            get_next_mcq_question_options_prompt, get_last_mcq_question_options_promt, extract_mcq_options_from_response)
from tests.choices import TestTypeChoices, ScenarioCaseChoices
import logging
from email_sender.helpers import send_feedbackd_email, send_bot_conversation_email
from users.models import UserAttribute, SignatureBot
from skills.helpers import (feedback_summary, calulate_summary_for_culture_and_normal_skill, evaluate_skills_explanation,
                            evaluate_culture_skills_explanation, evaluate_skills_explanation_conversation, evaluate_culture_skills_explanation_conversation)

from coaching_conversations.models import CoachingConversation
from utilities.helpers import get_session_notes, save_session_notes, get_session_notes_data, update_session_notes
from coaching_conversations.helpers import get_bot_conversation_data_user

logger = logging.getLogger(__name__)


class TestAttemptSessionViewSet(ApiViewSet,
                                mixins.ListModelMixin,
                                mixins.RetrieveModelMixin):
    queryset = TestAttemptSession.objects.filter(deleted=0)
    serializer_class = TestAttemptSessionSerializer
    permission_classes = (IsAuthenticatedClient, IsAuthenticatedUser)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_fields = ("test_id", "test_score", "participant_id")
    ordering_fields = ("id", "test_score")
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_id = serializer.validated_data["test_id"]
        participant_id = serializer.validated_data["participant_id"]
        test_invite_id = serializer.validated_data.get("test_invite_id")
        is_signature_bot = serializer.validated_data.get("is_signature_bot", False)

        print("is_signature_bot =========>", is_signature_bot)

        session = create_test_question_answer_session(
            tenant=request.tenant,
            test_id=test_id,
            test_invite_id=test_invite_id,
            participant_id=participant_id,
            is_signature_bot=is_signature_bot
        )

        return Response(data=TestAttemptSessionSerializer(instance=session).data, status=status.HTTP_201_CREATED)

    @action(methods=["GET"], detail=True, url_path="report")
    def get_test_report(self, request, *args, **kwargs):
        test_attempt_session = self.get_object()
        report_url = get_report_from_test_attempt_session(test_attempt_session)
        return Response({"report_url": report_url}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="report-data")
    def get_test_report_frontend(self, request, *args, **kwargs):
        test_attempt_session = self.get_object()
        data = get_report_from_test_attempt_session(
            test_attempt_session, only_data=True)
        tenant = self.request.tenant
        data['logo'] = tenant.logo
        return Response({"data": data, "status": "completed"}, status=status.HTTP_200_OK)
    

    @action(methods=["GET"], detail=True, url_path="meeting-report-data")
    def get_meeting_report_frontend(self, request, *args, **kwargs):
        test_attempt_session = self.get_object()
        data = get_meeting_report_from_test_attempt_session(
            test_attempt_session)

        tenant = self.request.tenant
        data['logo'] = tenant.logo
        return Response({"data": data, "status": "completed"}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="get-session-id")
    def get_session_uid(self, request, *args, **kwargs):
        participant_id = request.query_params.get("participant_id")
        test_id = request.query_params.get("test_id")

        # Filter the test_attempt_session with the given test_id and participant_id and ordered by created
        test_attempt_session = TestAttemptSession.objects.filter(
            test_id=test_id, participant_id=participant_id, deleted=0).order_by("-id").first()

        return Response({"uid": test_attempt_session.uid}, status=status.HTTP_200_OK)
    
    @action(methods=["GET"], detail=False, url_path="get-skills-tracker-report-data")
    def get_skills_tracker_report_data(self, request, *args, **kwargs):
        participant_id = request.query_params.get("participant_id")
        data = get_skills_tracker_data(participant_id)

        tenant = self.request.tenant
        data['logo'] = tenant.logo
        
        return Response({"data": data, "status": "completed"}, status=status.HTTP_200_OK)
    
    @action(methods=["GET","POST"], detail=False, url_path="cancel-test-sessions")
    def cancel_prev_sessions(self, request, *args, **kwargs):
        participant_id = request.data.get("user_id")

        # Filter the test_attempt_session with the given participant_id 
        test_attempt_sessions = TestAttemptSession.objects.filter(participant_id=participant_id, deleted=0, status=TestAttemptSessionStatusChoices.in_progress)

        cancel_count = 0
        try:
            for test_attempt_session in test_attempt_sessions:
                test_attempt_session.status = TestAttemptSessionStatusChoices.cancelled
                test_attempt_session.save(update_fields=['status'])
                cancel_count += 1
        except:
            pass

        return Response({"status": "cancelled","message":f"{cancel_count} sessions cancelled.","cancelled_session": cancel_count}, status=status.HTTP_200_OK)


    @action(methods=["GET"], detail=False, url_path="get-past-completed-interactions")
    def get_past_completed_interactions(self, request, *args, **kwargs):
        participant_id = request.query_params.get("participant_id")
        try:
            qs = super().get_queryset().filter(participant_id=participant_id,tenant_id=self.request.tenant.uid, status=TestAttemptSessionStatusChoices.completed).order_by("-id")
            
            test_dict = {}

            for session in qs:
                test = Test.objects.get(uid=session.test_id)
                test_name = test.title
                test_name = test_name[:min(len(test_name), 50)]

                if len(test_name) == 50:
                    test_name = f"{test_name}..."
                
                if test_name not in test_dict:
                    test_dict[test_name] = f"{session.test_id},{session.uid}"
                if len(test_dict) == 10:
                    break
        
            return Response(data=test_dict, status=status.HTTP_200_OK)
        except Exception as e:
            logger.info({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)


    @action(methods=["GET"], detail=False, url_path="get-session-status")
    def get_session_status(self, request, *args, **kwargs):
        try:
            session_id = request.query_params.get('session_id')
            logger.info({"SESSION_ID":session_id})
            session = TestAttemptSession.objects.get(uid=session_id)
            session_status = session.status

            
            timezone = pytz.timezone("Asia/Kolkata")
            expires_at = session.expires_at
            now = datetime.datetime.now(timezone)

            

            return Response(data={"status":session_status, "is_expired": expires_at < now}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            
    @action(methods=["GET"], detail=False, url_path="get-attempted-test-list")
    def get_list(self, request, *args, **kwargs):
        # participant_id = request.data.get("user_id")
        participant_id =  request.query_params.get("user_id")

        # Filter the test_attempt_session with the given participant_id 
        test_attempt_sessions = TestAttemptSession.objects.filter(participant_id=participant_id, deleted=0, status=TestAttemptSessionStatusChoices.completed)
        checkin_type_sessions_count = test_attempt_sessions.filter(is_checkin_type=1).count()

        test_codes = set()
        for test_attempt_session in test_attempt_sessions:

            test_codes.add(Test.objects.get(uid=test_attempt_session.test_id).test_code)

        data = {"codes": list(test_codes),"checkin_type_test_count": checkin_type_sessions_count, "total_session":test_attempt_sessions.count()}

        return Response({"data": data, "status": "completed"}, status=status.HTTP_200_OK)



    @action(methods=["GET","POST"], detail=False, url_path="submit_feedback")
    def submit_feedback(self, request, *args, **kwargs):
        try:
            participant_id = request.query_params.get("participant_id")
            session_id = request.query_params.get("session_id")
            feedback = request.query_params.get("feedback")
            rating = request.query_params.get("rating")
            test_id = request.query_params.get("test_id")
            test_title = request.query_params.get("test_title")

            user_attributes = UserAttribute.objects.get(
                                    user_id=participant_id).attributes
            candidate_name = f"{user_attributes.get('real_name')} (username: {user_attributes.get('name')})"
            
            send_feedbackd_email(candidate_name, test_id, test_title, session_id, rating, feedback)

            return Response({"status": "sent"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(methods=["POST"], detail=False, url_path="send-report-email")
    def send_report_email(self, request, *args, **kwargs):
        try:
            logger.info("send_report_email")
            test_attempt_session_id = request.query_params.get("test_attempt_session_id")
            report_url = request.query_params.get("report_url")
            is_whatsapp = request.query_params.get("is_whatsapp")
            is_whatsapp = True if is_whatsapp in ["true", "True"] else False
            is_free = False
            
            logger.info({"message":"##################################### Request Received for sending email #####################################",
                            "test_attempt_session_id":test_attempt_session_id, "report_url":report_url, "is_whatsapp":is_whatsapp})
            


            try:
                test_attempt_session = TestAttemptSession.objects.get(uid=test_attempt_session_id)
                test = Test.objects.get(uid=test_attempt_session.test_id)
            except Exception as e:
                logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
                return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)
            
            if test.is_free:
                is_free = True

            if is_whatsapp or report_url is None or report_url == "":
                report_url = test_attempt_session.report_url


            if test.test_type == TestTypeChoices.coaching or test.scenario_case == ScenarioCaseChoices.process_training or test.test_type in (TestTypeChoices.dynamic_mcq, TestTypeChoices.mcq) or test.is_transcript_only:
                send_report_link_to_email(test, test_attempt_session, report_url, is_whatsapp)
                return Response({"status": "sent"}, status=status.HTTP_200_OK)

            if is_whatsapp and test.test_type != TestTypeChoices.interview and test.scenario_case != ScenarioCaseChoices.employee_feedback:
                send_report_link_to_whatsapp(
                    test, test_attempt_session, report_url)
                

            #################* summary  start #################
            updated_fields = []
            
            
            skills_summary = calulate_summary_for_culture_and_normal_skill(test_attempt_session, 
                                                                            test_attempt_session.culture_skills_rating,
                                                                            test_attempt_session.skills_rating,is_free)
            logger.info({"************************skills_summary in submit email ********************":skills_summary})
            if len(skills_summary) > 0:
                test_attempt_session.culture_and_skill_summary = skills_summary
                updated_fields.append("culture_and_skill_summary")

            responses = TestQuestionResponse.objects.filter(
                test_attempt_session_id=test_attempt_session.uid,
                responder_type='user',
                deleted=0
            )
            feedbacks = ''
            for response in responses:
                if response.feedback_text:
                    feedbacks += response.feedback_text + '\n'

            feedbacks_summary = feedback_summary(test_attempt_session,feedbacks,is_free)
            logger.info({"************************feedbacks_summary in submit email ********************":feedbacks_summary})
            if len(feedbacks_summary) > 0:
                test_attempt_session.feedback_summary = feedbacks_summary
                updated_fields.append("feedback_summary")


            #####################* summary end #################

            if not test.is_free :
                #####################* explanation start #################
                if test.test_type == TestTypeChoices.orchestrated_conversation or test.test_type == TestTypeChoices.dynamic_discussion:
                    user_persona = test.orchestrated_conversation_details.get("test_user_persona")
                    objective = test.orchestrated_conversation_details.get("objective")

                    chat_conversation = get_group_discussion_chat_conversation(
                        test_attempt_session, user_persona)

                    skills_explanation = evaluate_skills_explanation_conversation(objective, chat_conversation, user_persona, test_attempt_session.skills_rating, test_attempt_session)
                    logger.info({"************************ skills_explanation in submit email orc********************":skills_explanation,"len": len(skills_explanation.keys()),"skill_rating_len": len(test_attempt_session.skills_rating.keys())})

                    culture_skills_explanation = evaluate_culture_skills_explanation_conversation(objective, chat_conversation, user_persona, test_attempt_session.culture_skills_rating, test_attempt_session)
                    logger.info({"************************ culture_skills_explanation in submit email orc********************":culture_skills_explanation,"len": len(culture_skills_explanation.keys()),"cul_rating_len": len(test_attempt_session.culture_skills_rating.keys())})

                    if skills_explanation:
                        test_attempt_session.skills_explanation = skills_explanation
                        updated_fields.append("skills_explanation")

                    if culture_skills_explanation:
                        test_attempt_session.culture_skills_explanation = culture_skills_explanation
                        updated_fields.append("culture_skills_explanation")

                else:
                
                    responses = TestQuestionResponse.objects.filter(
                        test_attempt_session_id=test_attempt_session.uid,
                        deleted=0
                    )
                    conversation = ""
                    count = 1

                    for response in responses:

                        question = TestQuestion.objects.get(
                            uid=response.question_id)

                        question_text = question.question
                        response_text = response.response_text

                        conversation += f"{count}. [Question:] {question_text}\n"
                        if not question.is_view_only:
                            conversation += f"[Answer:] {response_text}\n\n"

                        count += 1

                    skills_explanation = evaluate_skills_explanation(test.title, test.description, conversation, test_attempt_session.skills_rating, test_attempt_session)
                    logger.info({"************************skills_explanation in submit email ********************":skills_explanation,"len": len(skills_explanation.keys()),"skill_rating_len": len(test_attempt_session.skills_rating.keys())})
                    if skills_explanation:
                        test_attempt_session.skills_explanation = skills_explanation
                        updated_fields.append("skills_explanation")

                    if not test.is_pitch:
                        culture_skills_explanation = evaluate_culture_skills_explanation(test.title, test.description, conversation,test_attempt_session.culture_skills_rating , test_attempt_session)
                        logger.info({"************************culture_skills_explanation in submit email ********************":culture_skills_explanation,"len": len(culture_skills_explanation.keys()),"cul_rating_len": len(test_attempt_session.culture_skills_rating.keys())})  
                    else:
                        culture_skills_explanation = None            
                    if culture_skills_explanation:
                        test_attempt_session.culture_skills_explanation = culture_skills_explanation
                        updated_fields.append("culture_skills_explanation")
                

                #####################* explanation end #################

            test_attempt_session.save(update_fields=updated_fields)
                

            if test.test_type == TestTypeChoices.orchestrated_conversation or test.test_type == TestTypeChoices.dynamic_discussion:
                if test.email_address_list:
                    send_report_link_to_email_orch(test,test_attempt_session,report_url,is_whatsapp)
            else:
                if test.email_address_list:
                    send_report_link_to_email(test, test_attempt_session, report_url, is_whatsapp)

            return Response({"status": "sent"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(methods=["POST"], detail=False, url_path="set-name-and-email")
    def set_name_email(self, request, *args, **kwargs):
        try:
            participant_id = request.query_params.get("participant_id")
            name = request.query_params.get("name")
            email = request.query_params.get("email")

            logger.info({"message":"##################################### Request Received for setting name and email #####################################"
                            ,"participant_id":participant_id, "name":name, "email":email})

            try:
                user = get_user_by_id(participant_id)
            except Exception as e:
                logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
                return Response({"status": "error","message":"invalid participant id"}, status=status.HTTP_400_BAD_REQUEST)
            user_attribute = UserAttribute.objects.get(
                                    user_id=participant_id)

            if name is not None and name != "":
                user.name = name
                user.save(update_fields=['name'])

            if 'profile' not in user_attribute.attributes:
                user_attribute.attributes['profile'] = {}
            user_attribute.attributes['profile']['real_name'] = name
            user_attribute.attributes['profile']['email'] = email
            if 'username' not in user_attribute.attributes['profile']:
                user_attribute.attributes['profile']['username'] = email

            user_attribute.attributes['real_name'] = name
            user_attribute.attributes['name'] = email.split('@')[0]
            user_attribute.attributes['email'] = email
            
            user_attribute.save(update_fields=['attributes'])

            return Response({"status": "updated"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(methods=["GET"], detail=False, url_path="check-session-data-exist")
    def check_session_data_exist(self, request, *args, **kwargs):
        session_id = request.query_params.get('session_id')

        try:
            session_finished_at = TestAttemptSession.objects.get(uid = session_id).finished_at
            check  = False
            if session_finished_at:
                check = True

            return Response({"check":check}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(methods=['GET'],detail=False,url_path="get_next_mcq_question_options")
    def get_next_mcq_question_options(self,request, *args, **kwargs):
        test_attempt_session_id = request.query_params.get('test_attempt_session_id')
        description = request.query_params.get('description')
        question_text = request.query_params.get('situation')
        option_a = request.query_params.get('option_a')
        option_b = request.query_params.get('option_b')
        option_selected = request.query_params.get('option_selected')
        

        try:
            test_attempt_session = TestAttemptSession.objects.get(uid=test_attempt_session_id)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)

        test = Test.objects.get(uid=test_attempt_session.test_id)

        total_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid, deleted=0).count()

        logger.info(f")))))))))))))))))))))))))) question_text: {question_text}, option_selected: {option_selected}, option_a: {option_a}, option_b: {option_b}, total_responses: {total_responses}")
        
        test_attempt_session.feedback_summary = question_text
        test_attempt_session.save(update_fields=['feedback_summary'])

        if total_responses == test.total_question - 1:
            next_question_and_options_prompt = get_last_mcq_question_options_promt(description, question_text, option_a, option_b, option_selected)
        else:
            next_question_and_options_prompt = get_next_mcq_question_options_prompt(description, question_text, option_a, option_b, option_selected)

        logger.info({">>>>>>>>>>>>>>>>>>>>>>>>>>>> next mcq question prompt":next_question_and_options_prompt})

        retry_count = 0
        while retry_count < 5:
            response = generic_completion(next_question_and_options_prompt, 600)
            logger.info({">>>>>>>>>>>>>>>>>>>>>>>>>>>> next mcq question response":response})
            options_data = extract_mcq_options_from_response(response)
            logger.info({">>>>>>>>>>>>>>>>>>>>>>>>>>>> options_data":options_data, "question text": test_attempt_session.feedback_summary})

            # if both options generated are 75% same then continue else break
            if calculate_similarity(options_data['option_a'], options_data['option_b']) > 75:
                logger.info({">>>>>>>>>>>>>>>>>>>>>>>>>>>> options are same so going to retry":options_data,"retry_count":retry_count})
                retry_count += 1
                continue
            else:
                break

        return Response({"options_data":options_data}, status=status.HTTP_200_OK)



    @action(methods=['GET'],detail=False,url_path="send-bot-transcript-email")
    def send_bot_transcript_email(self,request, *args, **kwargs):
        test_attempt_session_id = request.query_params.get('test_attempt_session_id')
        submitted_email = request.query_params.get('submitted_email')

        logger.info({"message":"##################################### Request Received for sending bot transcript email #####################################",
                     "test_attempt_session_id":test_attempt_session_id, "submitted_email":submitted_email})

        try:
            test_attempt_session = TestAttemptSession.objects.get(tenant_id=self.request.tenant.uid, uid=test_attempt_session_id)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            signature_bot = SignatureBot.objects.get(tenant_id=self.request.tenant.uid, uid=test_attempt_session.test_id)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)

        user_email = UserAttribute.objects.get(tenant_id=self.request.tenant.uid, user_id=test_attempt_session.participant_id).attributes['email']
        bot_owner_email = UserAttribute.objects.get(tenant_id=self.request.tenant.uid, user_id=signature_bot.user_id).attributes['email']

        # previous_conversations = CoachingConversation.objects.filter(
        # tenant_id=self.request.tenant.uid,
        # test_attempt_session_id=test_attempt_session.uid,
        # deleted=0
        #     ).order_by(
        #         "id"
        #     ).values(
        #         "participant_message_text",
        #         "coach_message_text",
        #     )
        
        participant_id = test_attempt_session.participant_id
        candidate_name = f"""{get_user_display_name(
            get_user_by_id(participant_id)).capitalize()} {user_email}"""
        tenant = self.request.tenant
        # bot_ids = list(set(SignatureBot.objects.filter(deleted=0).values_list('bot_id',flat=True)))
        sessions = TestAttemptSession.objects.filter(deleted=0,tenant_id=tenant.uid,test_id=signature_bot.uid,participant_id=participant_id)
        conv = get_bot_conversation_data_user(sessions,tenant,participant_id,only_converation=True)
        conv = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in conv]

        for email in [submitted_email, bot_owner_email,"info@coachbots.com"]:
            send_bot_conversation_email(candidate_name, conv, email)

        return Response({"status": "sent"}, status=status.HTTP_200_OK)

    
    @action(methods=['GET'],detail=False,url_path="save_session_notes")
    def save_session_notes(self,request, *args, **kwargs):
        """
        Save or retrieve session notes for a user in a specific context.

        Args:
            request (HttpRequest): The HTTP request object.
            user_id (str): The ID of the user for whom the session notes are being saved/retrieved.
            context (str): The context in which the session notes are being saved/retrieved.
            mentor_id (str, optional): The ID of the mentor (required only when saving session notes as a mentor).
            mode (str): The mode of operation, either 'mentor' or 'mentee'.
        
        Returns:
            Response: The response containing the saved or retrieved session notes data.
        """
        try:
            tenant_id = self.request.tenant.uid
            user_id = request.query_params.get('user_id')
            context = request.query_params.get('context')
            mentor_id = request.query_params.get('mentor_id')
            mode = request.query_params.get('for')
            access_token = request.query_params.get('token', None)
            logger.info(f"details: {mode}, userid: {user_id}, mentor_id; {mentor_id}")

            if mode == 'mentor':
                data = save_session_notes(user_id,mentor_id,tenant_id,context,access_token)
                return Response({"data":data}, status=status.HTTP_200_OK)
            elif mode == 'mentee':
                data = get_session_notes(user_id,mentor_id)
                return Response({"data":data}, status=status.HTTP_200_OK)
            else:
                return Response({"details": 'for parameter not found. please check'},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'save_session_notes erro , {e}',exc_info=True)
            return Response({"Error":e}, status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'],detail=False,url_path="get_or_update_session_notes")
    def get_or_update_session_notes(self,request, *args, **kwargs):
        try:
            tenant_id = self.request.tenant.uid
            mode = request.query_params.get('mode',None)
            session_note_id = request.query_params.get('session_note_id',None)
            recommendations = request.query_params.get('recommendations',None)

            if mode == 'get':
                data = get_session_notes_data(tenant_id)
                return Response({"data":data}, status=status.HTTP_200_OK)
            elif mode == 'update':
                if not recommendations or not session_note_id:
                    return Response({"Error": "recommendations or session_note_id not found"}, status=status.HTTP_400_BAD_REQUEST)

                data = update_session_notes(session_note_id,recommendations)
                return Response({"data":data}, status=status.HTTP_200_OK)
            else:
                return Response({"details": 'Mode parameter not found. please check'},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'get_or_update_session_notes error , {e}',exc_info=True)
            return Response({"Error":e}, status=status.HTTP_400_BAD_REQUEST)


