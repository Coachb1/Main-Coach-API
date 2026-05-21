from django.urls import path, include
from rest_framework import routers

from apis.sso.views import TeamsSSOViewSet

router = routers.SimpleRouter()

router.register("v1/sso", TeamsSSOViewSet, "sso_v1")

urlpatterns = [
    path("", include(router.urls))
]
