from django.urls import include, path
from rest_framework.routers import SimpleRouter
from apis.analytics.views import EventViewSet

router = SimpleRouter()
router.register("v1/analytics", EventViewSet, basename="analytics")

urlpatterns = [
    path("", include(router.urls)),
]
