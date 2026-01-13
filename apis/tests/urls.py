from django.urls import path, include
from rest_framework import routers

from apis.tests.courese_view import CourseViewSet
from apis.tests.views import TestCSVExportViewSet, TestViewSet

router = routers.SimpleRouter()
router.register("v1/tests", TestViewSet, "tests_v1")
router.register("v1/courses", CourseViewSet, "courses_v1")
router.register("v1/test-export", TestCSVExportViewSet, "test_export_v1")

urlpatterns = [
    path("", include(router.urls)),
]
