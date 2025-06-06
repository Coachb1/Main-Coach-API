from rest_framework import status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from utilities.helpers import get_sid,get_h
from dotenv import load_dotenv

# from apis.web_auth.serializers import LoginSerializer
from commons.viewset import ApiViewSet
from tenants.helpers import tenant_from_subdomain_prefix
from tests.choices import TestAttemptSessionStatusChoices, TestTypeChoices
from tests.models import TestAttemptSession, Test
from .serializers import FrontendAuthSerializer, FrontendAccessTokenSerializer
from .serializers import FrontendLeaderboardReportSerializer
from .serializers import FrontendCandidateReportSerializer
from .serializers import FrontendInteractionReportSerializer
from .serializers import FrontendInteractionSessionReportSerializer
from .serializers import FrontendCoachingSessionReportSerializer
from .serializers import FrontendMeetingAnalysisReportSerializer
from .serializers import FrontendAskingGreatQuestionsReportSerializer
from .serializers import FrontendSkillsTrackerReportSerializer
from .serializers import IDPSerializer, AdminReportSerializer
from .serializers import FrontendSkillsDiscoveryReportSerializer, DynamicDiscussionReportSerializer
from web_auth.helpers import create_new_tokens, get_new_access_token
from settings import FRONTEND_BASE_URL
from settings import BACKEND
from .report_types import ReportType
from url_shortener.helpers import check_url_exists, url_shortify
from url_shortener.models import UrlShortenerMap
from utilities.models import JotUrlSession
import datetime
import pytz
import os
import re
from django.db.models import Q

import hashlib
import logging

logger = logging.getLogger(__name__)
load_dotenv()


class FrontendAuthViewSet(ApiViewSet):
    """
    This class represents a view set for handling frontend authentication-related operations.

    Summary:
        This code defines a class named `FrontendAuthViewSet` which is a subclass of `ApiViewSet`. It contains two methods: `get_report_url` and `get_or_refresh_sid`. The `get_report_url` method is used to generate a report URL based on the provided parameters, while the `get_or_refresh_sid` method is used to retrieve or refresh a session ID.

    
    Main functionalities:
        - The `get_report_url` method generates a report URL based on the provided parameters. It handles different report types and includes additional query parameters based on the report type.
        - The `get_or_refresh_sid` method retrieves or refreshes a session ID for a user. It checks if the session ID needs to be refreshed based on the last updated timestamp.

    Methods:
        - `get_report_url`: Generates a report URL based on the provided parameters. It handles different report types and includes additional query parameters based on the report type.
        - `get_or_refresh_sid`: Retrieves or refreshes a session ID for a user. It checks if the session ID needs to be refreshed based on the last updated timestamp.

    Fields:
        - `FRONTEND_BASE_URL`: The base URL for the frontend application.
        - `BACKEND`: The backend configuration.
        - `ReportType`: A class that defines constants for different report types.
        - `logger`: A logger instance for logging errors and information.
        - Other imported modules and classes used within the code.
    """

    @action(methods=["POST"], detail=False, url_path="get-report-url")
    def get_report_url(self, request, *args, **kwargs):
        serializer = FrontendAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        report_type = serializer.validated_data["report_type"]
        shortify_url = serializer.validated_data["shortify_url"]

        tokens = create_new_tokens('user-report', 'uid', user_id)

        refresh_token = tokens["refresh"]

        url = f"{FRONTEND_BASE_URL}/{report_type}/{refresh_token}/"

        # print(f"Initial url: {url}")

        if report_type == ReportType.LEADERBOARD_REPORT:
            leaderboard_serializer = FrontendLeaderboardReportSerializer(
                data=request.data)

            leaderboard_serializer.is_valid(raise_exception=True)

            skills = leaderboard_serializer.validated_data["skills"]

            url = f"{url}?skills={','.join(skills)}&backend={BACKEND}"
        
        elif report_type == ReportType.SUMMARY_LEADERBOARD_REPORT:
            leaderboard_serializer = FrontendLeaderboardReportSerializer(
                data=request.data)

            leaderboard_serializer.is_valid(raise_exception=True)

            skills = leaderboard_serializer.validated_data["skills"]

            url = f"{url}?skills={','.join(skills)}&backend={BACKEND}"

        elif report_type == ReportType.CANDIDATE_REPORT:
            candidate_serializer = FrontendCandidateReportSerializer(
                data=request.data)

            candidate_serializer.is_valid(raise_exception=True)

            candidate_id = candidate_serializer.validated_data["candidate_id"]

            url = f"{url}?candidate_id={candidate_id}&backend={BACKEND}"

        elif report_type == ReportType.INTERACTION_REPORT:
            interaction_serializer = FrontendInteractionReportSerializer(
                data=request.data)

            interaction_serializer.is_valid(raise_exception=True)

            interaction_id = interaction_serializer.validated_data["interaction_id"]

            url = f"{url}?interaction_id={interaction_id}&backend={BACKEND}"

        elif report_type == ReportType.INTERACTION_SESSION_REPORT:
            session_serializer = FrontendInteractionSessionReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            session_id = session_serializer.validated_data["session_id"]
            interaction_id = session_serializer.validated_data["interaction_id"]

            url = f"{url}?session_id={session_id}&interaction_id={interaction_id}&backend={BACKEND}"

        elif report_type == ReportType.ProcessTrainingReport:
            session_serializer = FrontendInteractionSessionReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            session_id = session_serializer.validated_data["session_id"]
            interaction_id = session_serializer.validated_data["interaction_id"]

            url = f"{url}?session_id={session_id}&interaction_id={interaction_id}&backend={BACKEND}"

        elif report_type == ReportType.SUMMARY_FEEDBACK_REPORT:
            session_serializer = FrontendInteractionSessionReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            session_id = session_serializer.validated_data["session_id"]
            interaction_id = session_serializer.validated_data["interaction_id"]

            url = f"{url}?session_id={session_id}&interaction_id={interaction_id}&backend={BACKEND}"

        elif report_type == ReportType.COACHING_SESSION_REPORT:
            session_serializer = FrontendCoachingSessionReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            test_attempt_session_id = session_serializer.validated_data["test_attempt_session_id"]
            try:
                test_attempt_session =  TestAttemptSession.objects.get(
                                                        uid=test_attempt_session_id, deleted=0)
                if test_attempt_session.status == TestAttemptSessionStatusChoices.in_progress:
                    test_attempt_session.status = TestAttemptSessionStatusChoices.completed
                    test_attempt_session.finished_at = datetime.datetime.now()
                    test_attempt_session.save()
            except Exception as e:
                logger.info({"!!! Error !!!":"failed to get session from session_id for coaching", "error":e.args})

            url = f"{url}?backend={BACKEND}&test_attempt_session_id={test_attempt_session_id}&ordering=id"

        elif report_type == ReportType.MEETING_ANALYSIS_REPORT:
            session_serializer = FrontendMeetingAnalysisReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            test_attempt_session_id = session_serializer.validated_data["test_attempt_session_id"]

            url = f"{url}?test_attempt_session_id={test_attempt_session_id}&backend={BACKEND}"

        elif report_type == ReportType.ASKING_GREAT_QUESTIONS_REPORT:
            session_serializer = FrontendAskingGreatQuestionsReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            test_attempt_session_id = session_serializer.validated_data["test_attempt_session_id"]
            interaction_id = session_serializer.validated_data['interaction_id']

            url = f"{url}?test_attempt_session_id={test_attempt_session_id}&interaction_id={interaction_id}&backend={BACKEND}"
        
        elif report_type == ReportType.SKILLS_TRACKER_REPORT:
            session_serializer = FrontendSkillsTrackerReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            participant_id = session_serializer.validated_data["user_id"]

            url = f"{url}?participant_id={participant_id}&backend={BACKEND}"

        elif report_type == ReportType.SKILLS_DISCOVERY_REPORT:
            session_serializer = FrontendSkillsDiscoveryReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            session_id = session_serializer.validated_data["session_id"]
            interaction_id = session_serializer.validated_data["interaction_id"]

            url = f"{url}?session_id={session_id}&interaction_id={interaction_id}&backend={BACKEND}"

        elif report_type == ReportType.DYNAMIC_DISCUSSOIN_REPORT:
            serializer = DynamicDiscussionReportSerializer(
                data=request.data)

            serializer.is_valid(raise_exception=True)

            test_attempt_session_id = serializer.validated_data["test_attempt_session_id"]
            interaction_id = serializer.validated_data['interaction_id']

            url = f"{url}?test_attempt_session_id={test_attempt_session_id}&interaction_id={interaction_id}&backend={BACKEND}"

        elif report_type == ReportType.DecisionAnalysisReport:
            session_serializer = FrontendInteractionSessionReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            session_id = session_serializer.validated_data["session_id"]
            interaction_id = session_serializer.validated_data["interaction_id"]

            url = f"{url}?session_id={session_id}&interaction_id={interaction_id}&backend={BACKEND}"

        elif report_type == ReportType.PERSONALITY_DISTRIBUTION_REPORT:
            client_id = request.data.get('client_id', None)
            url = f"{url}?client_id={client_id}&backend={BACKEND}"   

        elif report_type == ReportType.PERSONALITY_PSYCHOMATRIC_REPORT:
            session_serializer = FrontendInteractionSessionReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            session_id = session_serializer.validated_data["session_id"]
            interaction_id = session_serializer.validated_data["interaction_id"]

            url = f"{url}?session_id={session_id}&interaction_id={interaction_id}&backend={BACKEND}"

        elif report_type == ReportType.IDP_REPORT:
            serializer = IDPSerializer(
                data=request.data)

            serializer.is_valid(raise_exception=True)

            url = f"{url}?uid={serializer.validated_data['idp_id']}&backend={BACKEND}"

        elif report_type in [ReportType.KUDOS_BOARD_REPROT, ReportType.PARTICIPANT_LEADERBOARD_REPORT,
                             ReportType.PARTICIPANT_MAPPING_REPORT, ReportType.CRITICAL_FEEDBACK_REPORT]:
            serializer = AdminReportSerializer(
                data=request.data)

            serializer.is_valid(raise_exception=True)

            url = f"{url}?email={serializer.validated_data['email']}&backend={BACKEND}"
            
        # TODO: Logic to shortify the URL is temporarily disabled
        if False:
            # compute the hash of the url
            long_url_hash = hashlib.sha256(url.encode()).hexdigest()
            # Check if exists in db
            short_url = check_url_exists(long_url_hash, user_id)

            if short_url:
                url = short_url
                # print('--'*100)
                # print('Already that url exists in db')
            else:
                # Shortify the url
                long_url = url
                url = url_shortify(url)

                # print('--'*100)
                # print('New url shortified')
                # print(f'long_url: {long_url}')
                # print(f'short_url: {url}')

                # save the short url in db
                UrlShortenerMap.objects.create(
                    long_url_hash=long_url_hash,
                    long_url=long_url,
                    short_url=url,
                    tenant_id=user_id
                )

        data = {
            "url": url,
        }

        return Response(data=data, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=False, url_path="get-all-reports-by-testcode")
    def get_all_reports_by_testcode(self, request, *args, **kwargs):
        """
        Retrieve all report URLs for completed sessions associated with a given test code.
        Args:
            request (Request): The HTTP request object containing the test_code in the request data.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        Returns:
            Response: A Response object containing:
                - A list of report URLs for completed sessions if found.
                - An error message if the test_code is missing or invalid.
                - A message if no completed sessions are found for the given test code.
        Raises:
            Exception: If an error occurs while fetching the test or generating report URLs.
        Workflow:
            1. Validate the presence of `test_code` in the request data.
            2. Retrieve the test object associated with the given `test_code`.
            3. Fetch all completed sessions for the test.
            4. Determine the report type based on the test's type and scenario case.
            5. Generate report URLs for each completed session.
            6. Return the list of report URLs or appropriate error messages.
        Error Handling:
            - Returns HTTP 400 if `test_code` is missing.
            - Returns HTTP 404 if no test or completed sessions are found.
            - Logs errors encountered during report URL generation.
        Example Response:
            {
                "report_urls": [
                    {
                        "session_id": "session_uid_1",
                        "report_url": "https://frontend_base_url/report_type/refresh_token/?session_id=session_uid_1&interaction_id=test_id&backend=backend"
                    },
                    {
                        "session_id": "session_uid_2",
                        "report_url": "https://frontend_base_url/report_type/refresh_token/?session_id=session_uid_2&interaction_id=test_id&backend=backend"
                    }
                ]
            }
        """
        test_code = request.data.get("test_code")
        if not test_code:
            return Response(
                {"error": "test_code is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            test = Test.objects.get(deleted=False, test_code=test_code)
        except Exception as e:
            return Response(
                {'error': f"No test found for {test_code}"},
                status = status.HTTP_404_NOT_FOUND
            )

        # Fetch all completed sessions for the given test
        sessions = TestAttemptSession.objects.filter(
            Q(test_id=test.uid) & Q(deleted=False) & Q(status=TestAttemptSessionStatusChoices.completed)
        ).exclude(finished_at=None)

        if not sessions.exists():
            return Response(
                {"error": "No completed sessions found for the given testcode"},
                status=status.HTTP_404_NOT_FOUND
            )
        report_type = ReportType.INTERACTION_SESSION_REPORT
        if  test.test_type in [TestTypeChoices.test, TestTypeChoices.trainer, TestTypeChoices.test_thread, TestTypeChoices.trainer_thread]:
            if test.scenario_case == 'psychometric':
                report_type = ReportType.PERSONALITY_PSYCHOMATRIC_REPORT
            else:
                report_type = ReportType.INTERACTION_SESSION_REPORT
        elif  test.test_type in [TestTypeChoices.dynamic_discussion, TestTypeChoices.dynamic_discussion_thread]:
            report_type = ReportType.DYNAMIC_DISCUSSOIN_REPORT
        elif  test.test_type in [TestTypeChoices.coaching]:
            report_type = ReportType.COACHING_SESSION_REPORT
        elif test.test_type in [TestTypeChoices.orchestrated_conversation]:
            report_type = ReportType.MEETING_ANALYSIS_REPORT
        
        tokens = create_new_tokens("user-report", "uid", sessions[0].participant_id)
        refresh_token = tokens["refresh"]
        report_urls = []
        for session in sessions:
            try:
                url = f"{FRONTEND_BASE_URL}/{report_type}/{refresh_token}/"
                if report_type == ReportType.INTERACTION_SESSION_REPORT:
                    url = f"{url}?session_id={session.uid}&interaction_id={session.test_id}&backend={BACKEND}"
                elif report_type == ReportType.COACHING_SESSION_REPORT:
                    url = f"{url}?backend={BACKEND}&test_attempt_session_id={session.uid}&ordering=id"
                elif report_type == ReportType.MEETING_ANALYSIS_REPORT:
                    url = f"{url}?test_attempt_session_id={session.uid}&backend={BACKEND}"
                elif report_type == ReportType.DYNAMIC_DISCUSSOIN_REPORT:
                    url = f"{url}?test_attempt_session_id={session.uid}&interaction_id={session.test_id}&backend={BACKEND}"
                elif report_type == ReportType.PERSONALITY_PSYCHOMATRIC_REPORT:
                    url = f"{url}?session_id={session.uid}&interaction_id={session.test_id}&backend={BACKEND}"
                report_urls.append({"session_id": session.uid, "report_url": url})
            except Exception as e:
                logger.error(
                    {"error": f"Failed to generate report for session {session.uid}", "details": str(e)},
                    exc_info=True
                )

        return Response(
            {"report_urls": report_urls},
            status=status.HTTP_200_OK
        )
    
    @action(methods=["GET"], detail=False, url_path="get-or-refresh-sid")
    def get_or_refresh_sid(self, request, *args, **kwargs):
        """
        Retrieves or refreshes a session ID for jot url.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: The response containing the session ID and hashed session ID.

        
        """
        user_email = os.getenv("JOTURL_EMAIL")
        try:
            session = JotUrlSession.objects.get(email=user_email)
            session_updated_at = session.updated_at.replace(tzinfo=pytz.utc)

            date_25_day_ago = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=25)
            if session_updated_at < date_25_day_ago:
                session.session_id = get_sid(user_email)
                session.save()
            
        except Exception as e:
            session = JotUrlSession.objects.create(email=user_email, session_id=get_sid(user_email))
            logger.error({"!!!Error":e},exc_info=True)
        
        return Response(data={"sid": session.session_id,"_h":get_h(session.session_id)}, status=status.HTTP_200_OK)
    
    @action(methods=['POST'], detail=False, url_path='reset-expiry-token')
    def reset_expiry_token(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
    
        sessions = TestAttemptSession.objects.filter(
            deleted=False, status=TestAttemptSessionStatusChoices.completed
        ).exclude(finished_at=None).exclude(report_url=None)
    
        if user_id:
            sessions = sessions.filter(participant_id=user_id)
    
        # Fetch existing test IDs in bulk
        existing_tests = set(
            Test.objects.filter(deleted=False, uid__in=sessions.values_list("test_id", flat=True))
            .values_list("uid", flat=True)
        )
    
        user_tokens = {}
        updated_sessions = []
    
        for session in sessions:
            logger.info(f"session:uid: {session.uid} report_url: {session.report_url}, finished_at={session.finished_at}, deleted: {session.deleted}")
            if not session.report_url:
                logger.info(f'Session with id {session.uid} does not have a report URL')
                continue
            participant_id = session.participant_id
    
            if participant_id not in user_tokens:
                logger.info(f"Creating new tokens for user {participant_id}")
                user_tokens[participant_id] = create_new_tokens("user-report", "uid", participant_id)["refresh"]
                logger.info(f"Refresh token: {user_tokens[participant_id]}")
    
            if session.test_id not in existing_tests:
                logger.warning(f"Test with id {session.test_id} not found")
                continue
    
            refresh_token = user_tokens[participant_id]
            report_type = session.report_url.split("/")[3]
            updated_url = re.sub(rf"(?<={re.escape(report_type)}/)[^/\?]+", refresh_token, session.report_url)
    
            session.report_url = updated_url
            updated_sessions.append(session)
    
        # Bulk update all modified sessions at once
        if updated_sessions:
            TestAttemptSession.objects.bulk_update(updated_sessions, ["report_url"])
    
        return Response(data={"message": "Updated the report tokens"}, status=status.HTTP_200_OK)
    