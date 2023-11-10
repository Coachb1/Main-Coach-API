from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apis.tests_attempt_session.serializers import TestAttemptSessionSerializer
from clients.permissions import IsAuthenticatedClient
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from tests.helpers import get_meeting_report_from_test_attempt_session
from tests.helpers import get_skills_tracker_data
from tests.helpers import create_test_question_answer_session
from pdf_generator.helpers import get_report_from_test_attempt_session, update_skill_name
from tests.models import TestAttemptSession, TestQuestion, TestQuestionResponse
from tests.models import Test
from users.db import get_user_display_name, get_user_by_id
from tests.choices import TestAttemptSessionStatusChoices
from tests.helpers import send_report_link_to_email, send_report_link_to_email_orch, get_group_discussion_chat_conversation, send_report_link_to_whatsapp
from tests.choices import TestTypeChoices, ScenarioCaseChoices
import logging
from email_sender.helpers import send_feedbackd_email
from users.models import UserAttribute
from skills.helpers import (feedback_summary, calulate_summary_for_culture_and_normal_skill, evaluate_skills_explanation,
                            evaluate_culture_skills_explanation, evaluate_skills_explanation_conversation, evaluate_culture_skills_explanation_conversation)
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

        session = create_test_question_answer_session(
            tenant=request.tenant,
            test_id=test_id,
            test_invite_id=test_invite_id,
            participant_id=participant_id
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
            session_status = TestAttemptSession.objects.get(uid=session_id).status

            return Response(data={"status":session_status}, status=status.HTTP_200_OK)
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

            if not test.is_free:
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


                    culture_skills_explanation = evaluate_culture_skills_explanation(test.title, test.description, conversation,test_attempt_session.culture_skills_rating , test_attempt_session)
                    logger.info({"************************culture_skills_explanation in submit email ********************":culture_skills_explanation,"len": len(culture_skills_explanation.keys()),"cul_rating_len": len(test_attempt_session.culture_skills_rating.keys())})              
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