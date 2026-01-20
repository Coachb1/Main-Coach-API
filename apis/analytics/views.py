from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import render

from analytics.models import Event
from analytics.services import clicks_by_day, dashboard_stats, top_features
from users.models import ClientUserInfo, User
from users.permissions import IsSuperAdmin
from .serializers import EventSerializer


class EventViewSet(viewsets.GenericViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_object_or_404(User, uid=serializer.validated_data["user_id"]) if serializer.validated_data.get("user_id") else None

        Event.objects.create(
            event_type=serializer.validated_data["event_type"],
            feature=serializer.validated_data["feature"],
            metadata=serializer.validated_data.get("metadata", {}),
            user=user,
            client=user.get_client() if user else None,
        )

        return Response({"status": "tracked"}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def top(self, request):
        data = top_features()
        return Response(data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def daily(self, request):
        days = int(request.query_params.get("days", 7))
        data = clicks_by_day(days)
        return Response(data)
    
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsSuperAdmin],
        url_path="dashboard"
    )
    def dashboard(self, request):
        days = int(request.query_params.get("days", 7))
        client_id = request.query_params.get("client_id")
        user_id = request.query_params.get("user_id")

        client = None
        user = None
        if client_id:
            client = get_object_or_404(ClientUserInfo, uid=client_id)
        if user_id:
            user = get_object_or_404(User, uid=user_id)

        data = dashboard_stats(days=days, client=client, user=user)
        return Response(data)





    
