from django.apps import apps
from django.contrib import admin
from django.urls import path
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required

from analytics.models import Event
from analytics.services import (
    dashboard_stats,
    export_pillar_events_csv,
    feature_detail_stats,
    concept_session_stats,
    export_events_csv,
    export_concept_sessions_csv,
)
from analytics.services.export import export_concept_sessions_excel, export_pillar_events_excel
from apis.analytics.view import export_analytics_combined_excel
from jobaid.models import JobAidSession
from tests.models import Module
from users.models import ClientUserInfo, User
from tenants.admin import TenantAwareModelAdmin


# ------------------------------------------------------------------ #
#  Event views                                                        #
# ------------------------------------------------------------------ #

@staff_member_required
def analytics_dashboard_view(request):
    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7
    days = days if days in (7, 14, 30, 90) else 7

    client_id = request.GET.get("client_id")
    client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None
    user_id = request.GET.get("user_id")
    user = User.objects.filter(uid=user_id).first() if user_id else None
    feature = request.GET.get("feature")
    feature_path = request.GET.get("feature_path")
    event_type = request.GET.get("event_type", "click")

    data = dashboard_stats(
        days=days, client=client, user=user,
        event_type=event_type, feature=feature, feature_path=feature_path,
    )

    return render(request, "analytics/dashboard.html", {
        "data": data,
        "selected_days": days,
        "selected_event_type": event_type,
        "clients": ClientUserInfo.objects.all().order_by("client_name"),
        "selected_client": client,
        "selected_feature": feature,
        "selected_feature_path": feature_path,
        "distinct_features": Event.objects.values_list("feature", flat=True).distinct(),
        "distinct_feature_paths": (
            Event.objects.exclude(feature_path="")
            .values_list("feature_path", flat=True).distinct()
        ),
    })


@staff_member_required
def analytics_feature_detail_view(request):
    try:
        days = int(request.GET.get("days", 7))
        feature = request.GET.get("feature")
    except ValueError:
        days = 7
    client_id = request.GET.get("client_id")
    client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None
    data = feature_detail_stats(feature=feature, days=days, client=client)

    return render(request, "analytics/feature_detail.html", {
        **data,
        "selected_days": days,
        "clients": ClientUserInfo.objects.all().order_by("client_name"),
        "selected_client": client,
    })


@staff_member_required
def analytics_export_csv(request):
    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7
    client_id = request.GET.get("client_id")
    client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None
    return export_pillar_events_excel(
        days=days, client=client,
        feature=request.GET.get("feature"),
        feature_path=request.GET.get("feature_path"),
    )

@staff_member_required
def analytics_export_combined_csv(request):
    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7
    client_id = request.GET.get("client_id")
    client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None
    return export_analytics_combined_excel(days=days, client=client)

# ------------------------------------------------------------------ #
#  Concept Session views                                              #
# ------------------------------------------------------------------ #

@staff_member_required
def concept_session_dashboard_view(request):
    CaseMappings = apps.get_model("tests", "CaseMappings")

    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7
    days = days if days in (7, 14, 30, 90) else 7

    cm_id = request.GET.get("case_mapping_id")
    client_id = request.GET.get("client_id")
    client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None
    case_mapping = CaseMappings.objects.filter(uid=cm_id).first() if cm_id else None
    module = None
    jobaid_session = None

    if cm_id and not case_mapping:
        module = apps.get_model("tests", "Module").objects.filter(uid=cm_id).first()
        if not module:
            jobaid_session = JobAidSession.objects.filter(uid=cm_id).first()

    data = concept_session_stats(
        case_mapping=case_mapping,
        module=module,
        jobaid_session=jobaid_session,
        client=client,
        days=days,
    )


    all_mappings = CaseMappings.objects.filter(
        concept_sessions__isnull=False
    ).distinct()    
    all_modules = Module.objects.filter(
        concept_sessions__isnull=False
    ).distinct()
    all_jobaid_sessions = JobAidSession.objects.filter(
        concept_sessions__isnull=False
    ).distinct().order_by("-created")


    # Determine selected item info
    selected_item = None
    selected_item_type = None
    if case_mapping:
        selected_item = case_mapping
        selected_item_type = "case_mapping"
    elif module:
        selected_item = module
        selected_item_type = "module"
    elif jobaid_session:
        selected_item = jobaid_session
        selected_item_type = "jobaid"

    return render(request, "analytics/concept_sessions.html", {
        "data": data,
        "all_case_mappings": all_mappings,
        "all_modules": all_modules,
        "all_jobaid_sessions": all_jobaid_sessions,
        "selected_item": selected_item,
        "selected_item_type": selected_item_type,
        "clients": ClientUserInfo.objects.all().order_by("client_name"),
        "selected_client": client,
        "selected_days": days,
    })


@staff_member_required
def concept_session_export_csv(request):
    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7
    days = days if days in (7, 14, 30, 90) else 7

    client_id = request.GET.get("client_id")
    client = ClientUserInfo.objects.filter(uid=client_id).first() if client_id else None
    
    CaseMappings = apps.get_model("tests", "CaseMappings")
    cm_id = request.GET.get("case_mapping_id")
    case_mapping = CaseMappings.objects.filter(uid=cm_id).first() if cm_id else None
    module = None
    jobaid_session = None

    if cm_id and not case_mapping:
        from jobaid.models import JobAidSession
        module = apps.get_model("tests", "Module").objects.filter(uid=cm_id).first()
        if not module:
            jobaid_session = JobAidSession.objects.filter(uid=cm_id).first()

    return export_concept_sessions_excel(
        client=client,
        case_mapping=case_mapping,
        module=module,
        jobaid_session=jobaid_session,
        days=days,
    )


# ------------------------------------------------------------------ #
#  URL injection                                                      #
# ------------------------------------------------------------------ #

def inject_analytics_admin_urls():
    original_get_urls = admin.site.get_urls

    def get_urls():
        custom_urls = [
            path("analytics-dashboard/",
                 admin.site.admin_view(analytics_dashboard_view),
                 name="analytics-dashboard"),
            path("analytics/feature/",
                 admin.site.admin_view(analytics_feature_detail_view),
                 name="analytics-feature-detail"),
            path("analytics/export/",
                 admin.site.admin_view(analytics_export_csv),
                 name="analytics-export-csv"),
            # Concept sessions
            path("analytics/concept-sessions/",
                 admin.site.admin_view(concept_session_dashboard_view),
                 name="analytics-concept-sessions"),
            path("analytics/concept-sessions/export/",
                 admin.site.admin_view(concept_session_export_csv),
                 name="analytics-concept-sessions-export"),
            path("analytics/export-all/",
                 admin.site.admin_view(analytics_export_combined_csv),
                 name="analytics-export-combined-csv"),
        ]
        return custom_urls + original_get_urls()

    admin.site.get_urls = get_urls


inject_analytics_admin_urls()


# ------------------------------------------------------------------ #
#  ModelAdmin                                                         #
# ------------------------------------------------------------------ #

@admin.register(Event)
class EventAdmin(TenantAwareModelAdmin):
    list_display = ("id", "event_type", "feature", "feature_path", "user", "client", "created")
    list_filter = ("event_type", "feature", "created", "client")
    search_fields = ("feature", "feature_path", "user__email", "user__uid", "client__client_name")
    list_per_page = 25
