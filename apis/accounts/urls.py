from django.urls import include
from django.urls import path
from rest_framework import routers

from .views import AccountsViewSet

router = routers.SimpleRouter()

router.register("v1/accounts", AccountsViewSet, "accounts_v1")

urlpatterns = [
    path("", include(router.urls))
]
