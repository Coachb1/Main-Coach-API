from rest_framework.routers import SimpleRouter
from django.urls import path, include
from apis.mail_box.views import MailBoxViewSet, AuthorizedEmailsViewSet, EmailConversationViewSet, AccountabilityIntakeViewSet

router = SimpleRouter()
router.register(r'v1/mailbox', MailBoxViewSet, basename='mailbox')
router.register(r'v1/authorized-emails', AuthorizedEmailsViewSet, basename='authorizedemails')
router.register(r'v1/email-conversation', EmailConversationViewSet, basename='emailconversation')
router.register(r'v1/accountability-intake', AccountabilityIntakeViewSet, basename='accountabilityintake')

urlpatterns = [
    path('', include(router.urls)),
]
