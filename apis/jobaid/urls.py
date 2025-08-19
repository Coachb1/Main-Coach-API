from django.urls import path, include
from rest_framework import routers

from apis.jobaid.views import JobAidViewSet

router = routers.SimpleRouter()

router.register("v1/job-aid", JobAidViewSet, "jobaid_v1")

urlpatterns = [
    path("", include(router.urls))
]
