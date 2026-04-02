from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from analytics.models import Event
from analytics.services.export import export_events_csv
from analytics.trackers import click_tracker
from analytics.services import dashboard_stats, top_features, clicks_by_day
from apis.analytics.serializers import EventSerializer, TrackEventSerializer
from clients.permissions import IsAuthenticatedClient
from users.models import ClientUserInfo, User
from users.permissions import IsAuthenticatedUser, IsSuperAdmin


class EventViewSet(viewsets.GenericViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [AllowAny]

    def create(self, request):
        """Track a single interaction event."""
        serializer = TrackEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = None
        if data.get("user_id"):
            user = get_object_or_404(User, uid=data["user_id"])

        feature = data.get("feature", "")
        feature_path = data.get("feature_path", "")

        # Derive feature from path when not explicitly supplied
        if not feature and feature_path:
            feature = feature_path.split("|")[-1]

        click_tracker.record(
            feature=feature,
            event_type=data["event_type"],
            feature_path=feature_path or None,
            metadata=data.get("metadata", {}),
            user=user,
            client=user.get_client() if user else None,
        )

        return Response({"status": "tracked"}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def top(self, request):
        """Top features by click count. ?level=0 for pillar-level aggregation."""
        level_param = request.query_params.get("level")
        try:
            level = int(level_param) if level_param is not None else None
        except ValueError:
            level = None
        return Response(top_features(level=level))

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def daily(self, request):
        """Clicks grouped by day. ?days=7 (default)."""
        days = int(request.query_params.get("days", 7))
        return Response(clicks_by_day(days))

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsSuperAdmin],
        url_path="dashboard",
    )
    def dashboard(self, request):
        """Full dashboard stats for admin consumers."""
        days = int(request.query_params.get("days", 7))
        client_id = request.query_params.get("client_id")
        user_id = request.query_params.get("user_id")
        feature = request.query_params.get("feature")
        feature_path = request.query_params.get("feature_path")
        event_type = request.query_params.get("event_type", "click")

        client = get_object_or_404(ClientUserInfo, uid=client_id) if client_id else None
        user = get_object_or_404(User, uid=user_id) if user_id else None

        data = dashboard_stats(
            days=days,
            client=client,
            user=user,
            event_type=event_type,
            feature=feature,
            feature_path=feature_path,
        )
        return Response(data)
    

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticatedClient, IsAuthenticatedUser],
        url_path="export-events"
    )
    def export_events(self, request):
        try:
            days = int(request.query_params.get("days", 7))
        except ValueError:
            days = 7

        client_id = request.query_params.get("client_id")
        client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None
        
        return export_events_csv(
            days=days, client=client,
            feature=request.query_params.get("feature"),
            feature_path=request.query_params.get("feature_path"),
        )

   