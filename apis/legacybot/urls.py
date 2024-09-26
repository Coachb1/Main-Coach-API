from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import LegacyBotViewSet, LegacyBotUserViewSet, ThreadViewSet, ChatConversationViewSet

router = SimpleRouter()
router.register(r'v1/legacybot', LegacyBotViewSet)
router.register(r'v1/legacybotuser', LegacyBotUserViewSet)
router.register(r'v1/thread', ThreadViewSet)
router.register(r'v1/chat-conversation', ChatConversationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
