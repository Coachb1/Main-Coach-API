from django.urls import path, include
from rest_framework import routers

from apis.documents.views import DocumentViewSet

router = routers.SimpleRouter()

router.register("v1/documents", DocumentViewSet, "documents_v1")

urlpatterns = [
    path("", include(router.urls))
]
