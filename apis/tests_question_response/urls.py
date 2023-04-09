from django.urls import path, include
from rest_framework import routers

from apis.tests_question_response.views import TestQuestionResponseViewSet

router = routers.SimpleRouter()

router.register("v1/test-responses", TestQuestionResponseViewSet, "test_responses_v1")

urlpatterns = [
    path("", include(router.urls))
]
