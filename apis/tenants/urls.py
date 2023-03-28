from django.urls import include
from django.urls import path
from rest_framework import routers

from .views import TenantViewSet

router = routers.SimpleRouter()

router.register("v1/tenants", TenantViewSet, "tenants_v1")

urlpatterns = [
    path("", include(router.urls))
]
