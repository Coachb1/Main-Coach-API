from django.contrib import admin
from django.urls import path
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required

from analytics.models import Event
from analytics.services import dashboard_stats, export_events_csv, feature_detail_stats
from users.models import ClientUserInfo, User


@staff_member_required
def analytics_dashboard_view(request):
    # ---- days ----
    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7

    if days not in (7, 14, 30, 90):
        days = 7

    # ---- client ----
    client_id = request.GET.get("client_id")
    client = None

    if client_id:
        client = ClientUserInfo.objects.filter(uid=client_id).first()

    # ---- user (optional / future) ----
    user_id = request.GET.get("user_id")
    user = User.objects.filter(uid=user_id).first() if user_id else None

    # ---- analytics ----
    data = dashboard_stats(
        days=days,
        client=client,
        user=user
    )

    # ---- available clients (SUPER ADMIN) ----
    clients = ClientUserInfo.objects.all().order_by("client_name")

    return render(
        request,
        "analytics/dashboard.html",
        {
            "data": data,
            "selected_days": days,
            "clients": clients,
            "selected_client": client,
        }
    )

@staff_member_required
def analytics_feature_detail_view(request, feature):
    # ---- filters ----
    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7

    client_id = request.GET.get("client_id")
    client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None

    data = feature_detail_stats(
        feature=feature,
        days=days,
        client=client
    )
    clients = ClientUserInfo.objects.all().order_by("client_name")

    return render(
        request,
        "analytics/feature_detail.html",
        {**data, 
            **{"selected_days": days,
            "clients": clients,
            "selected_client": client,}
        }
    )


@staff_member_required
def analytics_export_csv(request):
    # filters
    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7

    client_id = request.GET.get("client_id")
    client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None 
    feature = request.GET.get("feature")   
    return export_events_csv(days=days, client=client, feature=feature)


# 🔑 Inject URL into EXISTING admin
def inject_analytics_admin_urls():
    original_get_urls = admin.site.get_urls

    def get_urls():
        urls = original_get_urls()
        custom_urls = [
            path(
                "analytics-dashboard/",
                admin.site.admin_view(analytics_dashboard_view),
                name="analytics-dashboard",
            ),
            path(
                "analytics/feature/<str:feature>/",
                admin.site.admin_view(analytics_feature_detail_view),
                name="analytics-feature-detail",
            ),
            path(
                "analytics/export/",
                admin.site.admin_view(analytics_export_csv),
                name="analytics-export-csv",
            )
        ]
        return custom_urls + urls

    admin.site.get_urls = get_urls


inject_analytics_admin_urls()


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "feature", "user", "client","created")
    list_filter = ("event_type", "feature", "created", 'client')
    search_fields = ("feature", "metadata", "user__email", "user__uid", 'client__client_name')