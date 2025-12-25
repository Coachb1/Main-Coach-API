from django.urls import path, include
from rest_framework import routers

from apis.company_iq.view import CompanyIQViewSet

router = routers.SimpleRouter()

router.register("v1/company-iq", CompanyIQViewSet, "company_iq_v1")

urlpatterns = [
    path("", include(router.urls)),
]
