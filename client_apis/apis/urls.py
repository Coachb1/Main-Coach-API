from django.urls import path, include
from .views import (
    APIKeyListCreateView,
    APIKeyDetailView,
    APIKeyUsageView,
    ClientAPIKeyUsageSummaryView,
)

# ── Key management routes (nested under /internal/) ──────────────────────────────
#
#   POST   internal/clients/<client_id>/keys/              → create key
#   GET    internal/clients/<client_id>/keys/              → list keys
#   GET    internal/clients/<client_id>/usage-summary/     → per-client summary
#   GET    internal/keys/<key_id>/                         → key detail
#   DELETE internal/keys/<key_id>/                         → revoke key
#   GET    internal/keys/<key_id>/usage/                   → usage logs

admin_urlpatterns = [
    # Client-scoped
    path(
        "clients/<int:client_id>/keys/",
        APIKeyListCreateView.as_view(),
        name="apikey-list-create",
    ),
    path(
        "clients/<int:client_id>/usage-summary/",
        ClientAPIKeyUsageSummaryView.as_view(),
        name="apikey-client-summary",
    ),

    # Key-scoped
    path(
        "keys/<int:key_id>/",
        APIKeyDetailView.as_view(),
        name="apikey-detail",
    ),
    path(
        "keys/<int:key_id>/usage/",
        APIKeyUsageView.as_view(),
        name="apikey-usage",
    ),
]

urlpatterns = [
    path("internal/",  include(admin_urlpatterns)),
    path("v1/",     include("client_apis.apis.protected_views.v1.protected_urls")),
]