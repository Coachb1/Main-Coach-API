from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apis.analytics.views.event_views import EventViewSet
from apis.analytics.views.progress_views import ConceptProgressViewSet
from apis.analytics.view import EventViewSet as AnalyticsEventViewSet, ai_adopts_doc

router = SimpleRouter()
router.register("v1/analytics", AnalyticsEventViewSet, basename="analytics")
router.register("v1/analytics-events", EventViewSet, basename="analytics-events")
router.register("v1/analytics-progress", ConceptProgressViewSet, basename="analytics-progress")

urlpatterns = [
    path("", include(router.urls)),
    path("v1/ai-adopts-doc", ai_adopts_doc, name='aiadopts_docs')
]
