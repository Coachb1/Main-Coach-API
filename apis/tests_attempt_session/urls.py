from django.urls import path, include
from rest_framework import routers

from apis.tests_attempt_session.views import TestAttemptSessionViewSet

router = routers.SimpleRouter()

router.register("v1/test-attempt-sessions", TestAttemptSessionViewSet, "test_attempt_sessions_v1")

urlpatterns = [
    path("", include(router.urls))
]
