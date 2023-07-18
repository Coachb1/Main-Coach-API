from rest_framework import status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

# from apis.web_auth.serializers import LoginSerializer
from commons.viewset import ApiViewSet
from tenants.helpers import tenant_from_subdomain_prefix
from .serializers import FrontendAuthSerializer, FrontendAccessTokenSerializer
from .serializers import FrontendLeaderboardReportSerializer
from .serializers import FrontendCandidateReportSerializer
from .serializers import FrontendInteractionReportSerializer
from .serializers import FrontendInteractionSessionReportSerializer
from .serializers import FrontendCoachingSessionReportSerializer
from .serializers import FrontendMeetingAnalysisReportSerializer
from .serializers import FrontendAskingGreatQuestionsReportSerializer
from web_auth.helpers import create_new_tokens, get_new_access_token
from settings import FRONTEND_BASE_URL
from .report_types import ReportType
from url_shortener.helpers import check_url_exists, url_shortify
from url_shortener.models import UrlShortenerMap

import hashlib


class FrontendAuthViewSet(ApiViewSet):

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

            url = f"{url}?skills={','.join(skills)}"

        elif report_type == ReportType.CANDIDATE_REPORT:
            candidate_serializer = FrontendCandidateReportSerializer(
                data=request.data)

            candidate_serializer.is_valid(raise_exception=True)

            candidate_id = candidate_serializer.validated_data["candidate_id"]

            url = f"{url}?candidate_id={candidate_id}"

        elif report_type == ReportType.INTERACTION_REPORT:
            interaction_serializer = FrontendInteractionReportSerializer(
                data=request.data)

            interaction_serializer.is_valid(raise_exception=True)

            interaction_id = interaction_serializer.validated_data["interaction_id"]

            url = f"{url}?interaction_id={interaction_id}"

        elif report_type == ReportType.INTERACTION_SESSION_REPORT:
            session_serializer = FrontendInteractionSessionReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            session_id = session_serializer.validated_data["session_id"]
            interaction_id = session_serializer.validated_data["interaction_id"]

            url = f"{url}?session_id={session_id}&interaction_id={interaction_id}"

        elif report_type == ReportType.COACHING_SESSION_REPORT:
            session_serializer = FrontendCoachingSessionReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            test_attempt_session_id = session_serializer.validated_data["test_attempt_session_id"]

            url = f"{url}?test_attempt_session_id={test_attempt_session_id}&ordering=id"

        elif report_type == ReportType.MEETING_ANALYSIS_REPORT:
            session_serializer = FrontendMeetingAnalysisReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            test_attempt_session_id = session_serializer.validated_data["test_attempt_session_id"]

            url = f"{url}?test_attempt_session_id={test_attempt_session_id}"

        elif report_type == ReportType.ASKING_GREAT_QUESTIONS_REPORT:
            session_serializer = FrontendAskingGreatQuestionsReportSerializer(
                data=request.data)

            session_serializer.is_valid(raise_exception=True)

            test_attempt_session_id = session_serializer.validated_data["test_attempt_session_id"]
            interaction_id = session_serializer.validated_data['interaction_id']

            url = f"{url}?test_attempt_session_id={test_attempt_session_id}&interaction_id={interaction_id}"

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
