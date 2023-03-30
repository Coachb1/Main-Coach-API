from django.urls import path, include

urlpatterns = [
    path("", include("apis.accounts.urls")),
    path("", include("apis.clients.urls")),
    path("", include("apis.tenants.urls")),
    path("", include("apis.tests.urls")),
]
