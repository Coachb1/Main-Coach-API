from django.urls import path, include
from rest_framework import routers

from apis.tests_invites.views import TestInviteViewSet

router = routers.SimpleRouter()

router.register("v1/test-invites", TestInviteViewSet, "test_invites_v1")

urlpatterns = [
    path("", include(router.urls))
]
