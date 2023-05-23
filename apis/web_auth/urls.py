from django.urls import path, include
from rest_framework import routers

from apis.web_auth.views import WebAuthViewSet

router = routers.SimpleRouter()

router.register("v1/webauth", WebAuthViewSet, "webauth_v1")

urlpatterns = [
    path("", include(router.urls))
]
