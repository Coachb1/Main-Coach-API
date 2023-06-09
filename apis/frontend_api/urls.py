from django.urls import path, include
from rest_framework import routers

from apis.frontend_api.views import FrontendAuthViewSet

router = routers.SimpleRouter()

router.register("v1/frontend-auth", FrontendAuthViewSet, "frontend_auth_v1")

urlpatterns = [
    path("", include(router.urls)),
]
