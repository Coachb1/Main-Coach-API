from django.urls import include
from django.urls import path
from rest_framework import routers

from .views import ClientViewSet

router = routers.SimpleRouter()

router.register("v1/clients", ClientViewSet, "clients_v1")

urlpatterns = [
    path("", include(router.urls))
]
