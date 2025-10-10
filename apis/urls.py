from django.urls import path, include

urlpatterns = [
    path("", include("apis.accounts.urls")),
    path("", include("apis.clients.urls")),
    path("", include("apis.tenants.urls")),
    path("", include("apis.tests.urls")),
    path("", include("apis.tests_invites.urls")),
    path("", include("apis.tests_attempt_session.urls")),
    path("", include("apis.tests_question_response.urls")),
    path("", include("apis.documents.urls")),
    path("", include("apis.coaching_conversations.urls")),
    path("", include("apis.web_auth.urls")),
    path("", include("apis.skills.urls")),
    path("", include("apis.frontend_api.urls")),
    path("", include("apis.test_bulk_upload.urls")),
    path("", include("apis.mail_box.urls")),
    path("", include("apis.legacybot.urls")),
    path("", include("apis.jobaid.urls")),
]
