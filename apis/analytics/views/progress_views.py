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

from analytics.trackers import progress_tracker
from analytics.services import concept_session_stats
from apis.analytics.serializers import (
    StartSessionSerializer,
    UpdateProgressSerializer,
    CompleteSessionSerializer,
    ConceptSessionSerializer,
)
from clients.permissions import IsAuthenticatedClient
from users.models import User
from users.permissions import IsAuthenticatedUser, IsSuperAdmin


def _get_user_and_mapping(validated_data):
    """Resolve User and CaseMappings from validated serializer data."""
    CaseMappings = apps.get_model("tests", "CaseMappings")
    user = get_object_or_404(User, uid=validated_data["user_id"])
    case_mapping = get_object_or_404(CaseMappings, uid=validated_data["case_mapping_id"])
    return user, case_mapping


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
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, case_mapping = _get_user_and_mapping(serializer.validated_data)
        session = progress_tracker.start(user=user, case_mapping=case_mapping)

        return Response(
            ConceptSessionSerializer(session).data,
            status=status.HTTP_200_OK,
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

        user, case_mapping = _get_user_and_mapping(serializer.validated_data)
        session = progress_tracker.update_progress(
            user=user,
            case_mapping=case_mapping,
            completion_percentage=serializer.validated_data["completion_percentage"],
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

        user, case_mapping = _get_user_and_mapping(serializer.validated_data)
        session = progress_tracker.complete(user=user, case_mapping=case_mapping)

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

        case_mapping = get_object_or_404(CaseMappings, uid=cm_id) if cm_id else None
        user = get_object_or_404(User, uid=user_id) if user_id else None

        data = concept_session_stats(case_mapping=case_mapping, user=user)
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
                {"detail": "user_id and case_mapping_id are required query parameters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, case_mapping = _get_user_and_mapping(
            {"user_id": user_id, "case_mapping_id": case_mapping_id}
        )
        session = progress_tracker.get_active(user=user, case_mapping=case_mapping)

        if not session:
            return Response(
                {"detail": "No active session found for this user and case mapping."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(ConceptSessionSerializer(session).data)