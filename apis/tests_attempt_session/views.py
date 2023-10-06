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
from tests.models import TestAttemptSession
from tests.models import Test
from users.db import get_user_display_name, get_user_by_id
from tests.choices import TestAttemptSessionStatusChoices
import logging
from email_sender.helpers import send_feedbackd_email
from users.models import UserAttribute
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
        test = Test.objects.get(uid=test_attempt_session.test_id)
        test_title = test.title
        data['title'] = test_title
        data['skills_explanation'] = update_skill_name(test_attempt_session.skills_explanation)
        data['culture_skills_explanation'] = test_attempt_session.culture_skills_explanation
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
            return Response({"status": "error"}, status=status.HTTP_200_OK)