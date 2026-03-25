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

        # allow caller to pass hierarchical path; if they didn't provide a
        # bare `feature` we will derive it from the path. the model's save
        # hook ensures consistency as well.
        feature = serializer.validated_data.get("feature")
        feature_path = serializer.validated_data.get("feature_path", "")
        
        if not feature and feature_path:
            # feature_path is a delimited string, extract the last element
            path_list = feature_path.split("|")
            feature = path_list[-1] if path_list else None

        Event.objects.create(
            event_type=serializer.validated_data["event_type"],
            feature=feature,
            feature_path=feature_path,
            metadata=serializer.validated_data.get("metadata", {}),
            user=user,
            client=user.get_client() if user else None,
        )

        return Response({"status": "tracked"}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def top(self, request):
        # support optional ``level`` parameter for hierarchical counts.
        level_param = request.query_params.get("level")
        try:
            level = int(level_param) if level_param is not None else None
        except ValueError:
            level = None
        data = top_features(level=level)
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



DOCUMENTATION_LINKS = {
    "AIADOPTS": [
        {
            "title": "AI Adopts Doc",
            "url": "/api/v1/ai-adopts-doc",
            "description": "Ai adopts",
            "updated_at": "2026-03-20",
            "is_pinned": True,
            "is_external": False
        }
    ],
    
}

# views.py
def docs_page(request):
    grouped_docs = DOCUMENTATION_LINKS

    pinned_docs = [
        doc
        for docs in DOCUMENTATION_LINKS.values()
        for doc in docs
        if doc.get("is_pinned")
    ]

    return render(request, "admin/docs.html", {
        "grouped_docs": grouped_docs,
        "pinned_docs": pinned_docs,
    })


def ai_adopts_doc(request):
    return render(request, "docs/aiadopts.html")