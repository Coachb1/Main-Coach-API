from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
import pytz
import datetime
import json
from django.http import StreamingHttpResponse
import time
import anthropic

from apis.tests_attempt_session.serializers import TestAttemptSessionSerializer, TestReportConfigSerializer
from clients.permissions import IsAuthenticatedClient
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from commons.utils import generic_completion
from tests.helpers import get_meeting_report_from_test_attempt_session, get_conversation_summary,create_scenario_from_transcript
from tests.helpers import get_skills_tracker_data, calculate_similarity
from tests.helpers import create_test_question_answer_session
from pdf_generator.helpers import get_report_from_test_attempt_session, update_skill_name
from tests.models import TestAttemptSession, TestQuestion, TestQuestionResponse, TestReportConfig
from tests.models import Test
from users.db import get_user_display_name, get_user_by_id
from tests.choices import TestAttemptSessionStatusChoices
from tests.helpers import (send_report_link_to_email, send_report_link_to_email_orch, get_group_discussion_chat_conversation, send_report_link_to_whatsapp,
                            get_next_mcq_question_options_prompt, get_last_mcq_question_options_promt, extract_mcq_options_from_response)
from tests.choices import TestTypeChoices, ScenarioCaseChoices
import logging
from email_sender.helpers import send_feedbackd_email, send_bot_conversation_email,send_feedback_conversation_email
from users.models import UserAttribute, SignatureBot, BotAttribute, CoachCoacheeMentorMenteeProfile, CoachCoacheeConnection
from skills.helpers import (feedback_summary, calulate_summary_for_culture_and_normal_skill, evaluate_skills_explanation,
                            evaluate_culture_skills_explanation, evaluate_skills_explanation_conversation, evaluate_culture_skills_explanation_conversation)

from coaching_conversations.models import CoachingConversation

from utilities.helpers import get_session_notes, save_session_notes, get_session_notes_data, update_session_notes, get_fitness_analysis_score,save_user_action_info,save_bot_engagement
from coaching_conversations.helpers import get_bot_conversation_data_user
from skills.helpers import json_extraction
from utilities.models import UserActionInfo, BotQnA, BotEngagement
from utilities.helpers import cal_score_for_fitment
from users.choices import CoachCoacheeConnectionStatusChoice
from commons.utils import get_bot_engagements
from commons.notifications import send_error_notification
from commons.webhook_utils import invoke_webhook
from users.helpers import get_client_info_from_user_detail
from commons.cache_utils import get_cache, set_cache, delete_cache, generate_cache_key, reset_cache_with_prefix
from tests.helpers import generate_psychometric_report_data


logger = logging.getLogger(__name__)
ANTHROPIC_KEY = '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'


class TestAttemptSessionViewSet(ApiViewSet,
                                mixins.ListModelMixin,
                                mixins.RetrieveModelMixin):
    """
    This class represents a viewset for handling API requests related to test attempt sessions.

    Summary:
        This viewset provides methods for creating test attempt sessions, retrieving test reports, getting session details, and performing various actions related to test sessions.

    Methods:
        - get_queryset(): Returns the queryset for retrieving test attempt sessions, filtered by tenant ID.
        - create(): Creates a new test attempt session based on the provided data.
        - get_test_report(): Retrieves the test report for a specific test attempt session.
        - get_test_report_frontend(): Retrieves the test report data for a specific test attempt session, formatted for frontend display.
        - get_meeting_report_frontend(): Retrieves the meeting report data for a specific test attempt session, formatted for frontend display.
        - get_session_uid(): Retrieves the UID of the latest test attempt session for a given participant and test ID.
        - get_skills_tracker_report_data(): Retrieves the skills tracker report data for a specific participant.
        - cancel_prev_sessions(): Cancels all in-progress test attempt sessions for a given participant.
        - get_past_completed_interactions(): Retrieves a list of past completed interactions for a given participant.
        - get_session_status(): Retrieves the status of a specific test attempt session.
        - get_list(): Retrieves a list of attempted tests for a given participant.
        - submit_feedback(): Submits feedback for a specific test attempt session.
        - send_report_email(): Sends a test report email for a specific test attempt session.
        - set_name_email(): Sets the name and email for a participant.
        - check_session_data_exist(): Checks if session data exists for a specific test attempt session.
        - get_next_mcq_question_options(): Retrieves the next multiple-choice question options for a specific test attempt session.
        - send_bot_transcript_email(): Sends a bot transcript email for a specific test attempt session.
        - save_session_notes(): Saves or retrieves session notes for a user in a specific context.
        - get_or_update_session_notes(): Retrieves or updates session notes data.

    Fields:
        - queryset: The queryset for retrieving test attempt sessions, filtered by deleted status.
        - serializer_class: The serializer class for serializing/deserializing test attempt session data.
        - permission_classes: The permission classes for controlling access to the API endpoints.
        - filter_backends: The filter backends for filtering test attempt sessions based on specific fields.
        - filterset_fields: The fields to be used for filtering test attempt sessions.
        - ordering_fields: The fields to be used for ordering test attempt sessions.
        - lookup_field: The field to be used for looking up test attempt sessions.
    """
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
        is_idp_discussion_opted = serializer.validated_data.get("is_idp_discussion_opted")
        intake_id = serializer.validated_data.get("intake_id")
        signature_session_id = serializer.validated_data.get("signature_session_id")

        print("is_signature_bot =========>", is_signature_bot, "is_idp", is_idp_discussion_opted)

        session = create_test_question_answer_session(
            tenant=request.tenant,
            test_id=test_id,
            test_invite_id=test_invite_id,
            participant_id=participant_id,
            is_signature_bot=is_signature_bot,
            is_idp_discussion_opted = is_idp_discussion_opted,
            intake_id = intake_id,
            signature_session_id=signature_session_id
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

        cache_key = generate_cache_key('get_attempted_test_list', participant_id=participant_id)

        # Attempt to retrieve data from cache
        cached_data = get_cache(cache_key)
        if cached_data is not None:
            return Response({"data": cached_data, "status": "completed"}, status=status.HTTP_200_OK)

        # Filter the test_attempt_session with the given participant_id 
        test_attempt_sessions = TestAttemptSession.objects.filter(participant_id=participant_id, deleted=0, status=TestAttemptSessionStatusChoices.completed).exclude(finished_at=None)
        checkin_type_sessions_count = test_attempt_sessions.filter(is_checkin_type=1).count()

        test_codes = set()
        for test_attempt_session in test_attempt_sessions:
            try:
                test_codes.add(Test.objects.get(uid=test_attempt_session.test_id).test_code)
            except:
                logger.info(f"Test not found for test_id: {test_attempt_session.test_id}")

        data = {"codes": list(test_codes),"checkin_type_test_count": checkin_type_sessions_count, "total_session":test_attempt_sessions.count()}
        set_cache(cache_key, data)
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
            if not user_attributes.get('real_name'):
                candidate_name = f"{user_attributes.get('name')} (username: {user_attributes.get('email')})"
            
            try:
                send_feedbackd_email(candidate_name, test_id, test_title, session_id, rating, feedback)
            except Exception as e:
                logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
                send_error_notification("submit_feedback","Error in sending feedback email",{"participant_id":participant_id,"session_id":session_id,"feedback":feedback,"rating":rating,"test_id":test_id,"test_title":test_title})

            return Response({"status": "sent"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            send_error_notification("submit_feedback","Error in submit feedback",{"participant_id":participant_id,"session_id":session_id,"feedback":feedback,"rating":rating,"test_id":test_id,"test_title":test_title})
            return Response({"status": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(methods=["POST"], detail=False, url_path="send-report-email")
    def send_report_email(self, request, *args, **kwargs):
        """
        Sends a report email or WhatsApp message based on the test attempt session details.
        This method handles the generation and sending of report links via email or WhatsApp, 
        along with processing feedback summaries, skill summaries, and explanations for various 
        test types and scenarios. It also invokes a webhook if configured.
        Args:
            request (Request): The HTTP request object containing query parameters.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        Query Parameters:
            test_attempt_session_id (str): The unique identifier for the test attempt session.
            report_url (str): The URL of the report to be sent.
            is_whatsapp (str): Indicates whether the report should be sent via WhatsApp ("true"/"True").
        Returns:
            Response: A Response object with the status of the operation:
                - {"status": "sent"} with HTTP 200 if the email/WhatsApp message is successfully sent.
                - {"status": "error"} with HTTP 400 if there is an error in retrieving the test attempt session or test.
                - {"status": "error"} with HTTP 500 if there is an unexpected server error.
        Raises:
            Exception: Captures and logs any unexpected errors during execution.
        Workflow:
            1. Retrieve test attempt session and test details.
            2. Determine whether the test is free and handle report URL fallback.
            3. Process feedback summaries for journaling scenarios.
            4. Send report links via email or WhatsApp based on test type and scenario.
            5. Generate skill and culture summaries and explanations for applicable test types.
            6. Save updated fields to the test attempt session.
            7. Invoke webhook if configured for the participant's client.
        Logging:
            - Logs detailed information about the request, processing steps, and errors.
            - Includes elapsed time for waiting on ratings and summaries.
        Notes:
            - Handles special cases for orchestrated conversations, dynamic discussions, and pitch scenarios.
            - Ensures timeout handling for rating updates.
            - Sends error notifications for email sending failures.
        """
        try:
            logger.info("send_report_email")
            test_attempt_session_id = request.query_params.get("test_attempt_session_id")
            report_url = request.query_params.get("report_url")
            is_whatsapp = request.query_params.get("is_whatsapp")
            is_whatsapp = True if is_whatsapp in ["true", "True"] else False
            is_free = False
            send_report_to_candidate = request.query_params.get('send_report_to_candidate', None)
            send_report_to_candidate = send_report_to_candidate.lower() in ["true", "True"] if send_report_to_candidate else None
            
            logger.info({"message":"##################################### Request Received for sending email #####################################",
                            "test_attempt_session_id":test_attempt_session_id, "report_url":report_url, "is_whatsapp":is_whatsapp, "send_report_to_candidate": send_report_to_candidate})
            


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

            if test.scenario_case in [ScenarioCaseChoices.journaling]:
                feedbacks = ''
                responses = TestQuestionResponse.objects.filter(
                        test_attempt_session_id=test_attempt_session.uid,
                        responder_type='user',
                        deleted=0
                    )
                for response in responses:
                    if response.feedback_text:
                        feedbacks += response.feedback_text + '\n'

                if len(feedbacks.strip()) >0:
                    feedbacks_summary = feedback_summary(test_attempt_session,feedbacks,is_free)
                    logger.info({"************************feedbacks_summary in submit email ********************":feedbacks_summary})
                    if len(feedbacks_summary) > 0:
                        test_attempt_session.feedback_summary = feedbacks_summary
                        test_attempt_session.save(update_fields=['feedback_summary'])

                    
                send_report_link_to_email(test, test_attempt_session, report_url, is_whatsapp,send_report_to_candidate=send_report_to_candidate)
                return Response({"status": "sent"}, status=status.HTTP_200_OK)

            if test.test_type == TestTypeChoices.coaching or test.scenario_case in [ScenarioCaseChoices.process_training] or test.test_type in (TestTypeChoices.dynamic_mcq, TestTypeChoices.mcq) or test.is_transcript_only:
                send_report_link_to_email(test, test_attempt_session, report_url, is_whatsapp, send_report_to_candidate=send_report_to_candidate)
                return Response({"status": "sent"}, status=status.HTTP_200_OK)

            if is_whatsapp and test.test_type != TestTypeChoices.interview and test.scenario_case != ScenarioCaseChoices.employee_feedback:
                send_report_link_to_whatsapp(
                    test, test_attempt_session, report_url)
                

            #################* summary  start #################
            updated_fields = []
            start_time = time.time()

            while True:
                current_time = time.time()
                elapsed_time = current_time - start_time
                
                test_attempt_session.refresh_from_db()
                
                logger.info(f"Culture rating: {test_attempt_session.culture_skills_rating}, Skills rating: {test_attempt_session.skills_rating}, Elapsed time: {elapsed_time:.2f} seconds")
                
                if test_attempt_session.culture_skills_rating and test_attempt_session.skills_rating:
                    break

                if elapsed_time > 60:
                    logger.error("Timeout exceeded while waiting for ratings to be set.")
                    break

                time.sleep(1)

            if test_attempt_session.culture_skills_rating and test_attempt_session.skills_rating:

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

            if len(feedbacks.strip()) >0:
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
                    objective = test.description

                    chat_conversation = get_group_discussion_chat_conversation(
                        test_attempt_session, user_persona)
                    
                    if test_attempt_session.skills_rating:
                        skills_explanation = evaluate_skills_explanation_conversation(objective, chat_conversation, user_persona, test_attempt_session.skills_rating, test_attempt_session)
                        logger.info({"************************ skills_explanation in submit email orc********************":skills_explanation,"len": len(skills_explanation.keys()),"skill_rating_len": len(test_attempt_session.skills_rating.keys())})
                        if skills_explanation:
                            test_attempt_session.skills_explanation = skills_explanation
                            updated_fields.append("skills_explanation")

                    if test.calculate_culture and test_attempt_session.culture_skills_rating:
                        culture_skills_explanation = evaluate_culture_skills_explanation_conversation(objective, chat_conversation, user_persona, test_attempt_session.culture_skills_rating, test_attempt_session)
                        logger.info({"************************ culture_skills_explanation in submit email orc********************":culture_skills_explanation,"len": len(culture_skills_explanation.keys()),"cul_rating_len": len(test_attempt_session.culture_skills_rating.keys())})
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
                    
                    if test_attempt_session.skills_rating:
                        skills_explanation = evaluate_skills_explanation(test.title, test.description, conversation, test_attempt_session.skills_rating, test_attempt_session)
                        logger.info({"************************skills_explanation in submit email ********************":skills_explanation,"len": len(skills_explanation.keys()),"skill_rating_len": len(test_attempt_session.skills_rating.keys())})
                        if skills_explanation:
                            test_attempt_session.skills_explanation = skills_explanation
                            updated_fields.append("skills_explanation")

                    if test.calculate_culture and test_attempt_session.culture_skills_rating:
                        if not test.scenario_case == ScenarioCaseChoices.pitch: 
                            culture_skills_explanation = evaluate_culture_skills_explanation(test.title, test.description, conversation,test_attempt_session.culture_skills_rating , test_attempt_session)
                            logger.info({"************************culture_skills_explanation in submit email ********************":culture_skills_explanation,"len": len(culture_skills_explanation.keys()),"cul_rating_len": len(test_attempt_session.culture_skills_rating.keys())})  
                        else:
                            culture_skills_explanation = None   

                        if culture_skills_explanation:
                            test_attempt_session.culture_skills_explanation = culture_skills_explanation
                            updated_fields.append("culture_skills_explanation")
                

                #####################* explanation end #################



            # if test.scenario_case == ScenarioCaseChoices.psychometric:
            #     generate_psychometric_report_data(test=test,test_attempt_session=test_attempt_session)
                

            test_attempt_session.save(update_fields=updated_fields)
                

            if test.test_type == TestTypeChoices.orchestrated_conversation or test.test_type == TestTypeChoices.dynamic_discussion:
                if test.email_address_list:
                    try:
                        send_report_link_to_email_orch(test,test_attempt_session,report_url,is_whatsapp,send_report_to_candidate)
                    except Exception as e:
                        send_error_notification("send_report_email",f"Error in sending email: {e}",{"test_attempt_session_id":test_attempt_session_id,"report_url":report_url,"is_whatsapp":is_whatsapp})
            else:
                if test.email_address_list:
                    try:
                        send_report_link_to_email(test, test_attempt_session, report_url, is_whatsapp,send_report_to_candidate)
                    except Exception as e:
                        send_error_notification("send_report_email",f"Error in sending email: {e}",{"test_attempt_session_id":test_attempt_session_id,"report_url":report_url,"is_whatsapp":is_whatsapp})

            try:
                participant_id = test_attempt_session.participant_id
                participant_attribute_obj = UserAttribute.objects.get(
                    user_id=participant_id)
                participant_attributes = participant_attribute_obj.attributes
                participant_email = participant_attributes.get(
                    "profile", {}).get("email") or participant_attributes.get('email',None)
                client_obj = get_client_info_from_user_detail(participant_attribute_obj.tenant_id,participant_email)
                logger.info(f"<< Client details >> {client_obj.client_name if client_obj else ''}, {client_obj.webhook_url}")
                if client_obj.webhook_url:
                    logger.info(f"<<<<<<<<<<<< pushing data to WEBHOOK_URL >>>>>>>")
                    invoke_webhook("simulation-attempted",{"username":participant_attributes.get("username"),"client_id": client_obj.client_name if client_obj else "", "participant_email": participant_email, "simulation_title": test.title, "report_link": report_url, "date": str(test_attempt_session.created.date())},client_obj.webhook_url, client_obj.webhook_secret or "") 
            except Exception as e:
                logger.info(f"Failed to invoke webhook")

            return Response({"status": "sent"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(methods=["POST"], detail=False, url_path="set-name-and-email")
    def set_name_email(self, request, *args, **kwargs):
        """
        Objective: The objective of the set_name_email method is to set the name and email of a participant in the system.

        Explanation: This method is used to update the name and email of a participant in the system. It receives the participant ID, name, and email as query parameters in the request. It then retrieves the user associated with the participant ID and updates their name and email fields. It also updates the user attributes related to the participant's profile, such as real name, username, and email. Finally, it saves the updated user attributes.

        Params:
        participant_id: The ID of the participant for whom the name and email need to be set.
        name: The new name of the participant.
        email: The new email of the participant.

        Input: The method receives the participant ID, name, and email as query parameters in the request.

        Output: The method returns a response with a status code indicating the success or failure of the operation. If the name and email are successfully updated, the response will have a status code of 200 (OK) and a JSON body with the status "updated". If there is an error, the response will have a status code indicating the type of error (e.g., 400 for a bad request or 500 for an internal server error) and a JSON body with the status "error". Eg : {"status": "updated"}

        """
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
        """
        Check if session data exists for a specific test attempt session.

        Parameters:
        - request: The HTTP request object.
        - session_id: The UID of the test attempt session.

        Returns:
        - Response: The HTTP response object containing the result of the check.
            - check (bool): True if session data exists, False otherwise.
            - {"check": true}
        """
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
        """
        Retrieves the next multiple-choice question options for a specific test attempt session.

        Parameters:
            - test_attempt_session_id (str): The UID of the test attempt session.
            - description (str): The description of the question.
            - question_text (str): The text of the question.
            - option_a (str): The text of option A.
            - option_b (str): The text of option B.
            - option_selected (str): The selected option.

        Returns:
            - options_data (dict): A dictionary containing the next question options data.

        Raises:
            - HTTP 400 Bad Request: If the test attempt session with the given UID does not exist.

        Description:
            This method retrieves the next multiple-choice question options for a specific test attempt session. It takes the UID of the test attempt session, the description of the question, the text of the question, the text of option A, the text of option B, and the selected option as parameters.

            First, it retrieves the test attempt session object using the provided UID. If the test attempt session does not exist, it returns an HTTP 400 Bad Request response.

            Then, it retrieves the test object associated with the test attempt session.

            Next, it counts the total number of responses for the test attempt session.

            It updates the feedback summary of the test attempt session with the question text.

            If the total number of responses is equal to the total number of questions minus one, it calls the get_last_mcq_question_options_promt() function to get the last question options prompt. Otherwise, it calls the get_next_mcq_question_options_prompt() function to get the next question options prompt.

            It then enters a loop with a maximum of 5 retries. In each iteration, it calls the generic_completion() function with the next question options prompt and a timeout of 600 seconds to generate a response. It extracts the options data from the response using the extract_mcq_options_from_response() function.

            If the similarity between option A and option B is greater than 75%, it continues to the next iteration. Otherwise, it breaks out of the loop.

            Finally, it returns the options_data dictionary containing the next question options.

        Example:
            GET /test-attempt-sessions/get_next_mcq_question_options?test_attempt_session_id=123&description=Question%20description&question_text=What%20is%20the%20capital%20of%20France%3F&option_a=Paris&option_b=London&option_selected=option_a

            Response:
            {
                "options_data": {
                    "option_a": "Paris",
                    "option_b": "London"
                }
            }
        """
   
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



    @action(methods=['GET', 'POST'],detail=False,url_path="send-bot-transcript-email")
    def send_bot_transcript_email(self,request, *args, **kwargs):
        
        """
        Sends a bot transcript email for a specific test attempt session.

        Parameters:
            - request: The HTTP request object.
            - test_attempt_session_id: The ID of the test attempt session for which the bot transcript email is to be sent.
            - submitted_email: The email address to which the bot transcript email should be sent.

        Returns:
            - Response: The HTTP response object containing the status of the email sending process.

        Objective:
            This method is used to send a bot transcript email for a specific test attempt session. The bot transcript email contains the conversation between the participant and the bot during the test session.

        Process:
            1. Retrieve the test attempt session ID and the submitted email address from the request query parameters.
            2. Get the test attempt session object based on the tenant ID and the test attempt session ID.
            3. Get the signature bot object based on the tenant ID and the test ID of the test attempt session.
            4. Get the user email address and the bot owner email address from the user attributes.
            5. Save the action point for the participant and the bot owner.
            6. Get the conversation data between the participant and the bot for the test attempt session.
            7. Send the bot conversation email to the submitted email address, the bot owner email address, and the default email address.

        Input Requirements:
            - The test_attempt_session_id parameter must be a valid ID of a test attempt session.
            - The submitted_email parameter must be a valid email address.

        Output:
            - The HTTP response object containing the status of the email sending process. The status can be "sent" if the email is successfully sent, or "error" if there is an error during the email sending process.
            - {"status": "sent"}
        """
        test_attempt_session_id = request.query_params.get('test_attempt_session_id')
        submitted_email = request.query_params.get('submitted_email')
        session_qna_data = request.data.get('session_qna_data')
        submitted_name = request.query_params.get('submitted_name')
        send_email = request.query_params.get('send_email','true')
        send_email =  True if send_email in  [ True, 'true', 1] else False

        
        logger.info(f">>>>>>>>>>>>>>>>>{request.data} ")

        logger.info({"message":"##################################### Request Received for sending bot transcript email #####################################",
                     "test_attempt_session_id":test_attempt_session_id, "submitted_email":submitted_email,
                     "session_qna_data":session_qna_data})

        try:
            test_attempt_session = TestAttemptSession.objects.get(tenant_id=self.request.tenant.uid, uid=test_attempt_session_id)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            signature_bot = SignatureBot.objects.get(deleted=False,tenant_id=self.request.tenant.uid, uid=test_attempt_session.test_id)
            bot_att = BotAttribute.objects.get(bot_id=signature_bot.uid)
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)
        
        user_email = UserAttribute.objects.get(tenant_id=self.request.tenant.uid, user_id=test_attempt_session.participant_id).attributes
        user_email = user_email.get('email') if 'email' in user_email else user_email.get('profile').get('email')
        bot_owner_email = UserAttribute.objects.get(tenant_id=self.request.tenant.uid, user_id=signature_bot.user_id).attributes
        bot_owner_email = bot_owner_email.get('email') if 'email' in bot_owner_email else bot_owner_email.get('profile').get('email')
        logger.info(f"************** user_email: {user_email}, bot_owner_email: {bot_owner_email}")

        try:
            coachee_profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,user_id=test_attempt_session.participant_id, tenant_id=request.tenant.uid)
            coach_profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,user_id=signature_bot.user_id, tenant_id=request.tenant.uid)
            connection = CoachCoacheeConnection.objects.get(deleted=False,coachee_id=coachee_profile.uid,coach_id=coach_profile.uid,
                                                            status=CoachCoacheeConnectionStatusChoice.accepted, tenant_id=request.tenant.uid)
            connected = True
        except Exception as e:
            logger.exception(e)
            connected = False
            if signature_bot.bot_type != 'deep_dive':
                connected = True
            coach_profile = None
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
            get_user_by_id(participant_id)).capitalize()}"""
        

        tenant = self.request.tenant
        save_user_action_info(tenant.uid,participant_id,"transcript_email_sent") # saving action point
        save_user_action_info(tenant.uid,signature_bot.user_id,"transcript_email_recieved")

        # bot_ids = list(set(SignatureBot.objects.filter(deleted=0).values_list('bot_id',flat=True)))
        # sessions = TestAttemptSession.objects.filter(deleted=0,tenant_id=tenant.uid,test_id=signature_bot.uid,participant_id=participant_id)
        if not session_qna_data:
            sessions = TestAttemptSession.objects.filter(deleted=0,tenant_id=tenant.uid,uid=test_attempt_session_id)
            conv = get_bot_conversation_data_user(sessions,tenant,participant_id,only_converation=True)
            temp = []
            for index, c in enumerate(conv):
                if index == 0:
                    temp.append({
                        "user": c.get('participant_message_text'),
                    })
                else:
                    if c.get('coach_message_text'):
                        temp[-1]['coach'] = c.get('coach_message_text')
                    if c.get('participant_message_text'):
                        temp.append({
                            "user": c.get('participant_message_text')
                        })
                # {"user":i['participant_message_text'],"coach": i['coach_message_text']
            conv = temp
        else:
            conv = [{"user":t["user"],"coach":t["coach"]} for t in session_qna_data]
        
        conversation_summary = get_conversation_summary(conv)
        
        logger.info({"********************* conversation_summary":conversation_summary})

        test_attempt_session.conversation_summary = conversation_summary
        test_attempt_session.save(update_fields=["conversation_summary"]) # saving session summary
        
        created_scenarios = None
        if send_email:
            created_scenarios = None
            # created_scenarios = create_scenario_from_transcript(conv, access_token,tenant.uid,participant_id)

        
        logger.info({"********************* created_scenarios":created_scenarios})

        

        # for email in [submitted_email, bot_owner_email,"coachbots@googlegroups.com"]:
            # send_bot_conversation_email(candidate_name, conv, recepients)
        recepients = [submitted_email if submitted_email else user_email]
        if connected or signature_bot.bot_type == 'deep_dive':
            recepients.append(bot_owner_email)

        coach_name = f"""{get_user_display_name(
            get_user_by_id(signature_bot.user_id)).capitalize()}"""

        if signature_bot.bot_type == 'deep_dive':
            coach_name = f"""{coach_name} ({signature_bot.bot_id})"""
        elif signature_bot.bot_type == 'user_bot':
            coach_name = f"""{bot_att.bot_name.capitalize()}"""


        # recepients = ['bagoriarajan@gmail.com']
        
        logger.info(f"************** session_qna_data conv: {conv}")
        try:
            candidate_name = submitted_name if (submitted_name is not None and len(submitted_name.strip()) > 0 ) else candidate_name
            if candidate_name.lower().strip() != "anonymous user" and submitted_email:
                candidate_name = f"{candidate_name} ({submitted_email})"
            if send_email:
                send_bot_conversation_email( 
                    candidate_name=candidate_name, 
                    conversation=conv, 
                    to_email=list(set(recepients)), 
                    summary=conversation_summary, 
                    simulation=created_scenarios, 
                    signature_bot=signature_bot, 
                    coach_name=coach_name,
                    bot_name=bot_att.bot_name,
                    allow_reply=True if signature_bot.bot_type != 'deep_dive' else False, 
                    no_reply=True if (signature_bot.bot_scenario_case == 'icons_by_ai' or signature_bot.bot_type == 'deep_dive') else False
                    )
            test_attempt_session.status = 'completed'
            test_attempt_session.save(update_fields=['status'])
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            send_error_notification("send_bot_transcript_email",f"Error in sending bot transcript email: {e}",{"participant_id":participant_id,"session_id":test_attempt_session_id,"submitted_email":submitted_email})
        
        if signature_bot.bot_scenario_case == 'icons_by_ai':
            try:
                participant_id = test_attempt_session.participant_id
                participant_attribute_obj = UserAttribute.objects.get(
                    user_id=participant_id)
                participant_attributes = participant_attribute_obj.attributes
                participant_email = participant_attributes.get(
                    "profile", {}).get("email") or participant_attributes.get('email',None)
                client_obj = get_client_info_from_user_detail(participant_attribute_obj.tenant_id,participant_email)
                if client_obj.webhook_url:
                    logger.info(f"<<<<<<<<<<<< pushing data to WEBHOOK_URL >>  client_name: {client_obj.client_name}, webhookurl: {client_obj.webhook_url}  >>>>>>>")
                    invoke_webhook("bot-interaction",{"username":participant_attributes.get("username"),"client_id": client_obj.client_name if client_obj else "", "participant_email": participant_email, "Conversation_transcript": conv, "date": str(test_attempt_session.created.date())},client_obj.webhook_url, client_obj.webhook_secret or "") 
            except Exception as e:
                logger.info(f"Failed to invoke webhook")
        return Response({"status": "sent"}, status=status.HTTP_200_OK)

    @action(methods=['GET','POST'],detail=False,url_path="send-feedback-transcript-email")
    def send_feedback_transcript_email(self,request, *args, **kwargs):
        """
        Sends a feedback transcript email for a specific test attempt session.
        Parameters:
           Input Requirements:
            - The request object must contain the required query parameters:
                - bot_id: The ID of the bot.
                - conversation: The conversation data.
                - type_of_email: The type of email to be sent.
                - user_email: The email of the user.


        Objective:
                This method is used to send a feedback transcript email for a specific test attempt session.


            Process:
                1. Retrieve the necessary parameters from the request query parameters:
                    - tenant: The tenant object.
                    - bot_id: The ID of the bot.
                    - conversation: The conversation data.
                    - type_of_email: The type of email to be sent.
                    - user_email: The email of the user.


                2. Retrieve the user ID associated with the bot.
                3. Save the user action information for the feedback received.
                4. Retrieve the bot owner's email address.
                5. Prepare the conversation data for the email, if the type of email is 'feedback_conv'.
                6. Send the feedback conversation email to the bot owner and the default email address.
                7. Return a success response.
        
        Output:
                - Response: The HTTP response object with a success status.
                -          {
                        "status": "sent"
                    }

        """
        tenant = self.request.tenant
        if request.method == 'GET':
            bot_id = request.query_params.get('bot_id')
            conversation = request.query_params.get('conversation')
            type_of_email = request.query_params.get('type_of_email')
            is_positive = request.query_params.get('is_positive','False')
            user_email = request.query_params.get('user_email')
            user_name = request.query_params.get('user_name')
        elif request.method == 'POST':
            bot_id = request.data.get('bot_id')
            conversation = request.data.get('conversation')
            type_of_email = request.data.get('type_of_email')
            is_positive = request.data.get('is_positive','False')
            user_email = request.data.get('user_email')
            user_name = request.data.get('user_name')

        is_positive = True if is_positive in [True, 1, 'True', 'true'] else False
        print(f"bot_id: {bot_id},tenant_id: {tenant.uid}, conversation: {conversation},type_of_email: {type_of_email},user_email: {user_email}",)

        try:
            user_id= SignatureBot.objects.get(deleted=False, tenant_id= tenant.uid, bot_id = bot_id).user_id
            bot_owner_email = UserAttribute.objects.get(tenant_id=self.request.tenant.uid, user_id=user_id).attributes['email']

        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
            return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)



        conv = []
        if  type_of_email == 'feedback_conv':
            save_user_action_info(tenant.uid,user_id,"feedback_recieved")
            conversation = json.loads(conversation) if isinstance(conversation, str) else conversation
            for key, value in conversation.items():
                conv.append({
                    "question": key,
                    "answer": value
                })

        for email in [bot_owner_email,"coachbots@googlegroups.com"]:
            try:
                candidate_name = f"{user_name}({user_email})"
                if user_email == 'Anonymous User':
                    candidate_name = "Anonymous User"

                send_feedback_conversation_email(candidate_name,conv,email,type_of_email,is_positive= is_positive, candidate_email=user_email)
            except Exception as e:
                logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
                send_error_notification("send_feedback_conversation_email",f"Error in sending feedback transcript email: {e}",{"bot_id":bot_id,"conversation":conversation,"type_of_email":type_of_email,"user_email":user_email})

        return Response({'status': 'sent'}, status=status.HTTP_200_OK)
    
    @action(methods=['GET'],detail=False,url_path="save_session_notes")
    def save_session_notes(self,request, *args, **kwargs):
        """
        Save or retrieve session notes for a user in a specific context.

        This method allows for saving or retrieving session notes for a user in a specific context. The session notes are associated with a user and can be saved or retrieved based on the provided parameters.

        Parameters:
        - request (HttpRequest): The HTTP request object.
        - user_id (str): The ID of the user for whom the session notes are being saved/retrieved.
        - context (str): The context in which the session notes are being saved/retrieved.
        - mentor_id (str, optional): The ID of the mentor (required only when saving session notes as a mentor).
        - mode (str): The mode of operation, either 'mentor' or 'mentee'.
        - access_token (str, optional): The access token for authentication (required only when saving session notes as a mentor).

        Returns:
        - Response: The response containing the saved or retrieved session notes data.
        - {"data": session notes data}

        Process:
        1. Extract the necessary parameters from the request and validate them.
        2. Determine the mode of operation (mentor or mentee).
        3. If the mode is 'mentor':
        - Call the 'save_session_notes' function with the provided parameters to save the session notes.
        - If there are any errors, return a response with the error message.
        - Otherwise, return a response with the saved session notes data.
        4. If the mode is 'mentee':
        - Call the 'get_session_notes' function with the provided user ID and mentor ID to retrieve the session notes.
        - Return a response with the retrieved session notes data.
        5. If the mode is neither 'mentor' nor 'mentee', return a response indicating that the 'for' parameter is not found.

        Input Requirements:
        - The request object must contain the necessary parameters: user_id, context, mode.
        - The mode parameter must be either 'mentor' or 'mentee'.

        Output:
        - If the mode is 'mentor':
        - If the session notes are successfully saved, return a response with the saved session notes data.
        - If there are any errors, return a response with the error message.
        - If the mode is 'mentee':
        - Return a response with the retrieved session notes data.
        - If the mode is neither 'mentor' nor 'mentee', return a response indicating that the 'for' parameter is not found.
        """
        try:
            tenant_id = self.request.tenant.uid
            user_id = request.query_params.get('user_id')
            context = request.query_params.get('context')
            mentor_id = request.query_params.get('mentor_id')
            mode = request.query_params.get('for')
            access_token = request.query_params.get('token', None)
            simulation_codes = request.query_params.get('simulation_codes', None)
            logger.info(f"************************** details: {mode}, userid: {user_id}, mentor_id; {mentor_id} \nQueryparams: {request.query_params}")

            if mode == 'mentor':
                data, errors = save_session_notes(user_id,mentor_id,tenant_id,context,access_token,simulation_codes)
                logger.info(f"######################################## save_session_notes data: {data} \nErrors : {errors}")
                if "error" in errors:
                    return Response({"Error":errors['error']}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"data":data}, status=status.HTTP_200_OK)
            elif mode == 'mentee':
                cache_key = generate_cache_key("session-notes",user_id=user_id, mentor_id=mentor_id)
                data = get_cache(cache_key)
                if not data:
                    data = get_session_notes(user_id,mentor_id)
                    set_cache(cache_key,data)
                return Response({"data":data}, status=status.HTTP_200_OK)
            else:
                return Response({"details": 'for parameter not found. please check'},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'save_session_notes erro , {e}',exc_info=True)
            return Response({"Error":e}, status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'],detail=False,url_path="get_or_update_session_notes")
    def get_or_update_session_notes(self,request, *args, **kwargs):
        """
    Retrieves or updates session notes data.

    Returns:
        - If the 'mode' parameter is set to 'get':
            - Response: A JSON response containing the session notes data.
        - If the 'mode' parameter is set to 'update':
            - Response: A JSON response containing the updated session notes data.
        - If the 'mode' parameter is not provided or is invalid:
            - Response: A JSON response indicating the error.

    
    Objective:
        This method is used to retrieve or update session notes data for a user in a specific context.

    Process:
        - The method first checks the 'mode' parameter to determine the operation to be performed.
        - If the 'mode' parameter is set to 'get', the method retrieves the session notes data using the 'get_session_notes_data' function.
        - If the 'mode' parameter is set to 'update', the method checks if the 'recommendations' and 'session_note_id' parameters are provided.
        - If the parameters are provided, the method updates the session notes data using the 'update_session_notes' function.
        - If the parameters are not provided, the method returns an error response.
        - If the 'mode' parameter is not provided or is invalid, the method returns an error response.

    Input/Parameters:
        - mode (str): The mode of operation. Valid values are 'get' and 'update'.
        - session_note_id (str): The ID of the session note to be updated.
        - recommendations (str): The updated recommendations for the session note.

    Output:
        - If the 'mode' parameter is set to 'get':
            - data (dict): A dictionary containing the session notes data.
        - If the 'mode' parameter is set to 'update':
            - data (dict): A dictionary containing the updated session notes data.
        - If the 'mode' parameter is not provided or is invalid:
            - details (str): A string indicating the error.

    Example Usage:
        - To retrieve session notes data:
            GET /api/test-attempt-sessions/get_or_update_session_notes?mode=get

        - To update session notes data:
            GET /api/test-attempt-sessions/get_or_update_session_notes?mode=update&session_note_id=123&recommendations=Lorem%20ipsum

    """
        try:
            tenant_id = self.request.tenant.uid
            mode = request.query_params.get('mode',None)
            session_note_id = request.query_params.get('session_note_id',None)
            recommendations = request.query_params.get('recommendations',None)
            simulation_codes = request.query_params.get('simulation_codes', None)

            if mode == 'get':
                data = get_session_notes_data(tenant_id)
                return Response({"data":data}, status=status.HTTP_200_OK)
            elif mode == 'update':
                if not recommendations or not session_note_id:
                    return Response({"Error": "recommendations or session_note_id not found"}, status=status.HTTP_400_BAD_REQUEST)

                data = update_session_notes(session_note_id,recommendations,simulation_codes)
                return Response({"data":data}, status=status.HTTP_200_OK)
            else:
                return Response({"details": 'Mode parameter not found. please check'},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'get_or_update_session_notes error , {e}',exc_info=True)
            return Response({"Error":e}, status=status.HTTP_400_BAD_REQUEST)



    @action(methods=['POST'],detail=False,url_path="get-fitness-analysis-score")
    def get_fitness_analysis_score(self,request, *args, **kwargs):

        """
        Retrieves the fitness analysis score based on the provided fitness analysis data.

        Parameters: which will in raw body not params
            - bot_id: The ID of the signature bot.
            - fitness_analysis_data: The fitness analysis data provided by the user.
            - participant_id: The ID of the participant.

        Returns:
            - Response: The HTTP response object containing the fitness analysis score.

        Raises:
            - Exception: If there is an error while retrieving the fitness analysis score.

        Process:
            - Retrieves the fitness analysis data from the request.
            - Retrieves the signature bot and bot attributes based on the provided bot ID.
            - Compares the user's fitness analysis data with the mentor's answers.
            - Calculates the matching percentage of answers.
            - Classifies the fitness analysis score based on the matching percentage.
            - Saves the fitness analysis Q&A and scores in the database.
            - Returns the fitness analysis score as the HTTP response.

        Input Requirements:
            - The request must contain the following data:
                - bot_id: The ID of the signature bot.
                - fitness_analysis_data: The fitness analysis data provided by the user.
                - participant_id: The ID of the participant.

        Output:
            - The fitness analysis score as a JSON object containing the following fields:
                - bottom: The classification for the bottom third.
                - mid: The classification for the middle third.
                - top: The classification for the top third.
                - msg: The overall classification message.
                - score: The count of matching answers.

        Example Usage:
            POST /get-fitness-analysis-score
            {
                "bot_id": "12345",
                "fitness_analysis_data": "{\"question1\": {\"cochee\": \"answer1\"}, \"question2\": {\"cochee\": \"answer2\"}}",
                "participant_id": "67890"
            }

            Response:
            {
                "bottom": "Not a good fit",
                "mid": "Potential fit",
                "top": "Good fit",
                "msg": "Potential fit",
                "score": 1
            }
        """
        # try:
        #     logger.info(f"fitness analysis score request: {request.data}")
        #     signature_bot = SignatureBot.objects.get(tenant_id=self.request.tenant.uid, bot_id=request.data['bot_id'])
        #     coach_data = signature_bot.data
        #     fitness_analysis_data = json.loads(request.data['fitness_analysis_data'])
        #     fitness_analysis_score = get_fitness_analysis_score(coach_data,fitness_analysis_data)
        #     fitness_analysis_score = json_extraction(fitness_analysis_score)
        #     logger.info(f"fitness_analysis_score: {fitness_analysis_score}")
        #     return Response({"data":json.loads(fitness_analysis_score)}, status=status.HTTP_200_OK)
            
        # except Exception as e:
        #     logger.error(f'get_fitness_analysis_score error , {e}',exc_info=True)
        #     return Response({"Error":e.args}, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"fitness analysis score request: {request.data}")
            bot_id = request.data.get("bot_id",None)
            user_response = request.data.get("fitness_analysis_data",None)
            participant_id = request.data.get("participant_id",None)
            logger.info(f"{bot_id},{self.request.tenant.uid}")

            score = {}
            if bot_id:
                qna = BotQnA.objects.filter(tenant_id=self.request.tenant.uid, participant_id= participant_id, qna_type = 'fitment' ).order_by("-id")
                if qna.count()>0:
                    score = cal_score_for_fitment(
                        user_response=qna.first().participant_qna,
                        bot_id=bot_id,
                        tenant_id= self.request.tenant.uid
                    )
                       

            return Response(score, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(e)
            return Response({"error": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)



    @action(methods=['GET'],detail=False,url_path="get-or-save-action-point")
    def get_or_save_action_point(self,request, *args, **kwargs):
        
        """
        Retrieves or saves the action points for a user.

        Parameters:
            - mode (can be get or save) , user_id, for(if mode is "save"): for is name of the action which we want to increase

        Returns:
            - If the 'mode' parameter is set to 'get':
                - Returns the action points for the specified user.
            - If the 'mode' parameter is set to 'save':
                - Saves the action points for the specified user and returns a success message.

        Raises:
            - If the 'mode' parameter is not provided or is invalid:
                - Returns a 400 Bad Request response with an error message.
            - If the action info for the specified user is not found:
                - Returns a 400 Bad Request response with an error message.

        Example usage:
            - To retrieve the action points for a user:
                GET /api/test-attempt-sessions/get-or-save-action-point?mode=get&user_id=<user_id>

            - To save the action points for a user:
                GET /api/test-attempt-sessions/get-or-save-action-point?mode=save&user_id=<user_id>&for=<for_>

        """
        try:
            mode = request.query_params.get('mode',None)
            tenant = self.request.tenant
            data = {}
            if mode == 'get':
                user_id = request.query_params.get('user_id',None)
                cache_key = generate_cache_key('action-points', tenant_id=tenant.uid, user_id=user_id)
                
                cached_data = get_cache(cache_key)
                if cached_data:
                    return Response(cached_data, status=status.HTTP_200_OK)
                try:
                    action_info = UserActionInfo.objects.get(tenant_id= tenant.uid,user_id = user_id)
                except:
                    return Response({"msg": 'Action info not found'},status=status.HTTP_400_BAD_REQUEST)
                action_data = {
                    "feedback_given" : action_info.feedback_given,
                    "feedback_recieved": action_info.feedback_recieved,
                    "chat_attempted": action_info.chat_attempted,
                    "transcript_email_recieved": action_info.transcript_email_recieved,
                    "transcript_email_sent": action_info.transcript_email_sent,
                    "interaction_attempted": action_info.interaction_attempted,
                }
                data['action_points'] = action_data
                set_cache(cache_key, data)

            elif mode == "save":
                user_id = request.query_params.get('user_id',None)
                for_ = request.query_params.get('for',None)
                bot_id = request.query_params.get('bot_id',None)
                save_user_action_info(tenant.uid,user_id,for_,bot_id=bot_id)

                data['message'] = "Action point increased."

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(e)
            return Response({"error": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'],detail=False,url_path="get-fitment-analysis-by-user")
    def get_fitment_analysis_by_user(self,request, *args, **kwargs):
        
        """
        Retrieves fitment analysis data for a specific user and bot.

        Parameters:
            - request: The HTTP request object.
            - user_id: The ID of the user for whom the fitment analysis is being retrieved.
            - bot_id: The ID of the bot for which the fitment analysis is being retrieved.

        Returns:
            - data: A dictionary containing fitment analysis data for the user and bot.
                - fitment_data: A list of fitment questions and their corresponding scores.
                    - qna: The fitment question.
                    - score: The fitment score for the question.
                - proceed: A boolean indicating whether the user can proceed based on the fitment scores.
                    - True: The user can proceed.
                    - False: The user cannot proceed.

        Raises:
            - Exception: If there is an error retrieving the fitment analysis data.

        Description:
            This method retrieves fitment analysis data for a specific user and bot. It takes the user ID and bot ID as query parameters in the HTTP request. The method first retrieves the signature bot object based on the bot ID and the tenant ID from the request. Then, it queries the BotQnA model to retrieve fitment questions and their scores for the specified user and bot. The fitment questions are ordered in descending order based on their IDs. The fitment questions and scores are then added to a list in the format of a dictionary. Finally, the method constructs a response dictionary containing the fitment data and a boolean indicating whether the user can proceed based on the fitment scores.

        Example:
            HTTP GET Request:
            GET /api/test-attempt-sessions/get-fitment-analysis-by-user?user_id=123&bot_id=456

            Response:
            {
                "fitment_data": [
                    {
                        "qna": "What are your strengths?",
                        "score": 3
                    },
                    {
                        "qna": "What are your weaknesses?",
                        "score": 2
                    }
                ],
                "proceed": true
            }
        """
        try:
            tenant = self.request.tenant
            data= {}
            user_id = request.query_params.get('user_id')
            bot_id = request.query_params.get('bot_id')
            logger.info({"user_id, bot_id": f"{user_id}, {bot_id}"})

            fitment_qnas = BotQnA.objects.filter(tenant_id = tenant.uid, participant_id= user_id, qna_type = 'fitment' ).order_by("-id")
            logger.info({"fitments================================================>": f"{fitment_qnas} {fitment_qnas.count()}"} )
            if (fitment_qnas).count()> 0:
                score = cal_score_for_fitment(fitment_qnas.first().participant_qna,bot_id,tenant.uid)
                score = score['score']
                data['msg'] = f'Score: {score}'
                if int(score) >=2:
                    data["proceed"] = True
                else:
                    data['proceed'] = False
            else:
                data['msg'] = f'Have not created yet!'
                data['proceed'] = False
            
            fitment_data = []
            for qna in fitment_qnas:
                logger.info({"fitment================================================>": qna})
                fitment_data.append({
                    "qna": qna.participant_qna,
                    "score": qna.fitment_score
                })

            data['fitment_data'] = fitment_data

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(e)
            return Response({"error": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)
        
        
        
    @action(methods=['GET','POST'],detail=False,url_path="create-or-get-bot-engagements")
    def create_or_get_bot_engagements(self,request, *args, **kwargs):
        """
        Handles the creation or retrieval of bot engagements based on the provided parameters. This method supports both GET and POST requests to either fetch existing bot engagement data or create/update bot engagement records.

        Objective:
        The primary goal of this method is to manage bot engagements, which include tracking user interactions with bots, such as the number of times a button was clicked or a session was attempted with the bot. It allows for both querying existing engagement data and incrementing engagement metrics.

        Process:
        - For GET requests, it filters and returns bot engagement data based on optional parameters like `bot_id`, `user_id`, and `by_date`.
        - For POST requests, it creates or updates a bot engagement record for a specific bot and user on the current date, incrementing a specified field.

        Input Requirements:
        - `bot_id` (query parameter): The ID of the bot involved in the engagement. Required for both GET and POST requests.
        - `user_id` (query parameter): The ID of the user involved in the engagement. Required for POST requests and optional for GET requests.
        - `by_date` (query parameter, optional for GET): Filters the engagements to those that occurred on a specific date.
        - `by_user` (query parameter, optional for GET): Filters the engagements to those associated with a specific user.
        - `field_name` (query parameter, required for POST): Specifies the field to increment in the bot engagement record.

        Expected Output:
        - For GET requests, returns a JSON object containing an array of bot engagement records and summary statistics. Each record includes details such as `bot_id`, `user_id`, `interacted_on`, `num_button_clicked`, `num_of_attempted_sessions`, and `attempted_bot_questions`.
        - For POST requests, returns a JSON object with a message indicating the bot engagement was successfully increased.

        Example:
        GET request with `bot_id=1` and `by_date=2023-04-01` might return:
        ```
        {
            "results": [
                {
                    "bot_id": "1",
                    "user_id": "123",
                    "interacted_on": "2023-04-01",
                    "num_button_clicked": 5,
                    "num_of_attempted_sessions": 2,
                    "attempted_bot_questions": 3
                }
            ],
            "total_engagement_with_question_count": 10,
            "total_without_question_count": 7
        }
        ```

        POST request with `bot_id=1`, `user_id=123`, and `field_name=num_of_clicked_button` might return:
        ```
        {"msg": "Bot engagement increased"}
        ```

        Note: The method also handles exceptions by logging them and returning an appropriate error message and status code.
        """

        try:
            data = {}
            bot_id = request.query_params.get('bot_id',None)
            user_id = request.query_params.get('user_id',None)
            tenant = self.request.tenant
            logger.info(f"===================bot_id : {bot_id}, user_id: {user_id}")
            try:
                signature_bot = SignatureBot.objects.get(tenant_id=tenant.uid,deleted=False,bot_id=bot_id)
            except Exception as e:
                logger.exception(e)
                return Response({"msg": "Bot Not found"}, status=status.HTTP_400_BAD_REQUEST)

            if request.method == 'GET':
                by_date = request.query_params.get('by_date',None)
                by_user = request.query_params.get('by_user',None)
                data = get_bot_engagements(tenant_id=tenant.uid,bot_id=signature_bot.uid,by_date=by_date,by_user=by_user)
                

            elif request.method == 'POST':
                field_name = request.query_params.get('field_name',None)
                save_bot_engagement(tenant_id=tenant.uid,bot_id=signature_bot.uid,user_id=user_id,field_name=field_name)

                data = {'msg': 'Bot engagement increased'}

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"create_or_get_bot_engagements failed with {e}")
            return Response({"error": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)
        


    @action(methods=['GET'],detail=False,url_path="testing")
    def testing_simulations(self,request,*args,**kwargs):

        from tests.helpers import simulate_llm_resposne

        simulate_llm_resposne()

        return Response("ok",status=status.HTTP_200_OK)
    
def stream(request):
    conv_id = request.GET.get('conv_id')
    logger.info(f"################################### Conv ID: {conv_id}")

    try:
        conv = CoachingConversation.objects.get(uid=conv_id)
    except Exception as e:
        logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
        def event_stream():
            yield 'data: %s\n\n' % "Conversation not found"
        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    
    logger.info(f"################################### Prompt: {conv.coach_message_metadata}")

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    try:
        prompt = conv.coach_message_metadata['prompt']
    except Exception as e:
        logger.error({"!!!!!!!!!!!!!!!ERROR": e},exc_info=True)
        def event_stream():
            yield 'data: %s\n\n' % "Error in generating response"
        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    def event_stream():
        with client.messages.stream(
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            model="claude-2.1",
        ) as stream:
            for text in stream.text_stream:
                yield 'data: %s\n\n' % text

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')

