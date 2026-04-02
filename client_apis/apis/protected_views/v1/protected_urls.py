from django.urls import path
from client_apis.apis.protected_views.v1.analytics.views import ExampleProtectedView



urlpatterns = [
    path(
        "analytics/",
        ExampleProtectedView.as_view(),
        name="analytics-protected-view",
    ),
]