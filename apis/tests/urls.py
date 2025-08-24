from django.urls import path, include
from rest_framework import routers

from apis.tests.views import CourseViewSet, TestViewSet

router = routers.SimpleRouter()
router.register("v1/tests", TestViewSet, "tests_v1")
router.register("v1/courses", CourseViewSet, "courses_v1")

urlpatterns = [
    path("", include(router.urls)),
]
