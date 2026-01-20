from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apis.analytics.views import EventViewSet

router = DefaultRouter()
router.register("v1/analytics", EventViewSet, basename="analytics")

urlpatterns = [
    path("", include(router.urls)),
]
