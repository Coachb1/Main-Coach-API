from django.urls import include
from django.urls import path
from rest_framework import routers

from .views import CoachingConversationViewSet

router = routers.SimpleRouter()

router.register("v1/coaching-conversations",
                CoachingConversationViewSet,
                "coaching_conversations_v1")

urlpatterns = [
    path("", include(router.urls))
]
