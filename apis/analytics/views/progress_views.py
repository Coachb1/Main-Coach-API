"""
apis/analytics/views/progress_views.py
----------------------------------------
REST endpoints for ConceptSession lifecycle and analytics.

Endpoints
---------
    POST  /v1/analytics/progress/start/        start or resume a session
    POST  /v1/analytics/progress/update/       advance completion percentage
    POST  /v1/analytics/progress/complete/     seal a session as completed
    GET   /v1/analytics/progress/me/           caller's own sessions
    GET   /v1/analytics/progress/dashboard/    admin aggregation view
"""

from django.apps import apps
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from analytics.services.export import export_concept_sessions_csv
from analytics.trackers import progress_tracker
from analytics.services import concept_session_stats
from apis.analytics.serializers import (
    StartSessionSerializer,
    UpdateProgressSerializer,
    CompleteSessionSerializer,
    ConceptSessionSerializer,
)
from clients.permissions import IsAuthenticatedClient
from jobaid.models import JobAidSession
from tests.models import CaseMappings, Collection, Module
from users.models import ClientUserInfo, User
from users.permissions import IsAuthenticatedUser, IsSuperAdmin
import logging

logger = logging.getLogger(__name__)




def _get_user_and_mapping(validated_data):
    """Resolve User and CaseMappings from validated serializer data."""
    CaseMappings = apps.get_model("tests", "CaseMappings")
    user = get_object_or_404(User, uid=validated_data["user_id"])
    case_mapping = CaseMappings.objects.filter(uid=validated_data["case_mapping_id"]).first()
    module = None
    if not case_mapping:
        # fetch module-level CaseMappings here to avoid importing the model at the top level of the file    
        module = get_object_or_404(Module, uid=validated_data["case_mapping_id"])
    return user, case_mapping, module


class ConceptProgressViewSet(viewsets.GenericViewSet):

    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        """
        Start (or resume) the active ConceptSession for a user + case mapping.

        Idempotent — returns the existing active session if one already exists.

        Body:
            user_id         (uuid, required)
            case_mapping_id (uuid, required)
        """
        try:
            serializer = StartSessionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            user, case_mapping, module = _get_user_and_mapping(serializer.validated_data)
            session = progress_tracker.start(user=user, case_mapping=case_mapping, module=module)

            return Response(
                ConceptSessionSerializer(session).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception(f"Error in start: {e}")
            return Response(
                {"error": "An error occurred while starting the session."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


    @action(detail=False, methods=["post"], url_path="update")
    def update_progress(self, request):
        """
        Advance the active session's completion_percentage.

        Creates the session automatically if one doesn't exist yet.
        Automatically completes the session when percentage reaches 100.

        Body:
            user_id               (uuid, required)
            case_mapping_id       (uuid, required)
            completion_percentage (float 0–100, required)
        """
        serializer = UpdateProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, case_mapping, module = _get_user_and_mapping(serializer.validated_data)
        session = progress_tracker.update_progress(
            user=user,
            case_mapping=case_mapping,
            completion_percentage=serializer.validated_data["completion_percentage"],
            module=module,
        )

        return Response(
            ConceptSessionSerializer(session).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="complete")
    def complete(self, request):
        """
        Mark the active session as completed.

        Sets completion_percentage=100, ended_at=now(), is_active=False.
        Idempotent — safe to call multiple times.

        Body:
            user_id         (uuid, required)
            case_mapping_id (uuid, required)
        """
        serializer = CompleteSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, case_mapping, module = _get_user_and_mapping(serializer.validated_data)
        session = progress_tracker.complete(user=user, case_mapping=case_mapping, module=module)

        if not session:
            return Response(
                {"detail": "No session found for this user and case mapping."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            ConceptSessionSerializer(session).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticatedClient, IsAuthenticatedUser],
        url_path="me",
    )
    def me(self, request):
        """
        Return all ConceptSessions for the authenticated user.

        Query params:
            status  — filter by status (started / in_progress / completed)
        """
        status_filter = request.query_params.get("status")
        sessions = progress_tracker.get_all_for_user(
            user=request.user,
            status=status_filter,
        )
        return Response(ConceptSessionSerializer(sessions, many=True).data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsSuperAdmin],
        url_path="dashboard",
    )
    def dashboard(self, request):
        """
        Aggregated concept session stats for admins.

        Query params:
            case_mapping_id (uuid, optional) — drill into one case mapping
            user_id         (uuid, optional) — scope to one user
        """
        CaseMappings = apps.get_model("tests", "CaseMappings")

        cm_id = request.query_params.get("case_mapping_id")
        user_id = request.query_params.get("user_id")

        case_mapping = None
        module = None
        jobaid_session = None
        if cm_id:
            case_mapping = CaseMappings.objects.filter(uid=cm_id).first()
            if not case_mapping:
                module = Module.objects.filter(uid=cm_id).first()
            if not case_mapping and not module:
                jobaid_session = JobAidSession.objects.filter(uid=cm_id).first()

        user = get_object_or_404(User, uid=user_id) if user_id else None

        data = concept_session_stats(
            case_mapping=case_mapping,
            user=user,
            module=module,
            jobaid_session=jobaid_session,
        )
        return Response(data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticatedClient, IsAuthenticatedUser],
        url_path="concept-session",
    )
    def concept_session(self, request):
        """
        Get the active ConceptSession for a user + case mapping.

        Query params:
            user_id         (uuid, required)
            case_mapping_id (uuid, required)
        """
        user_id = request.query_params.get("user_id")
        case_mapping_id = request.query_params.get("case_mapping_id")

        if not user_id or not case_mapping_id:
            return Response(
                {"error": "user_id and case_mapping_id are required query parameters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, case_mapping, module = _get_user_and_mapping(
            {"user_id": user_id, "case_mapping_id": case_mapping_id}
        )
        session = progress_tracker.get_active(user=user, case_mapping=case_mapping, module=module)

        if not session:
            return Response(
                {"error": "No active session found for this user and case mapping."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(ConceptSessionSerializer(session).data)
    
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticatedClient, IsAuthenticatedUser],
        url_path="export-concept-sessions"
    )
    def export_concept_sessions(self, request):
        try:
            days = int(request.query_params.get("days", 7))
        except ValueError:
            days = 7
        days = days if days in (7, 14, 30, 90) else 7

        client_id = request.query_params.get("client_id")
        client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None
        
        cm_id = request.query_params.get("case_mapping_id")
        case_mapping = CaseMappings.objects.filter(uid=cm_id).first() if cm_id else None
        module = None
        jobaid_session = None

        if cm_id and not case_mapping:
            module = Module.objects.filter(uid=cm_id).first()
            if not module:
                jobaid_session = JobAidSession.objects.filter(uid=cm_id).first()

        return export_concept_sessions_csv(
            client=client,
            case_mapping=case_mapping,
            module=module,
            jobaid_session=jobaid_session,
            days=days,
        )
    
    @action(detail=False, methods=["post"], url_path="track-jobaid-session-completion",
        permission_classes=[IsAuthenticatedClient, IsAuthenticatedUser],
            )
    def track_jobaid_session_completion(self, request):
        """Helper to mark a ConceptSession as completed based on a JobaidSession."""
        try:
            user_id = request.data.get("user_id")
            jobaid_session_id = request.data.get("jobaid_session_id")
            collection_id = request.data.get("collection_id")
            if not user_id or not jobaid_session_id or not collection_id:
                return Response(
                    {"error": "user_id, jobaid_session_id, and collection_id are required fields."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, uid=user_id)
            jobaid_session = get_object_or_404(JobAidSession, uid=jobaid_session_id)
            collection = get_object_or_404(Collection, uid=collection_id)
            session = progress_tracker.log_jobaid_attempt(user=user, jobaid_session=jobaid_session, collection=collection)
            return Response({"session_id": session.uid, "status": session.status}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error in track_jobaid_session_completion: {e}")
            return Response(
                {"error": "An error occurred while tracking jobaid session completion."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
