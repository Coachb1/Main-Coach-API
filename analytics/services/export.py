"""
analytics/services/export.py
------------------------------
CSV export helpers for events and concept sessions.
"""

import csv
from django.db.models import Count, Min, Max, Q
from django.http import HttpResponse
from django.utils.timezone import now

from analytics.models import Event
from .queries import event_qs, concept_session_qs


def export_events_csv(
    *,
    days: int = 7,
    client=None,
    user=None,
    feature: str = None,
    feature_path: str = None,
) -> HttpResponse:
    """Export event stats grouped by feature/feature_path as a CSV file."""

    qs = event_qs(days=days, feature=feature, feature_path=feature_path, user=user, client=client)

    total_events_all = qs.count() or 1

    feature_stats = (
        qs.values("feature", "feature_path")
        .annotate(
            total_events=Count("id"),
            unique_users=Count("user", distinct=True),
            unique_clients=Count("client", distinct=True),
            click_events=Count("id", filter=Q(event_type=Event.CLICK)),
            view_events=Count("id", filter=Q(event_type=Event.VIEW)),
            submit_events=Count("id", filter=Q(event_type=Event.SUBMIT)),
            first_seen=Min("created"),
            last_seen=Max("created"),
        )
        .order_by("-total_events")
    )

    response = HttpResponse(content_type="text/csv")
    timestamp = now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = (
        f'attachment; filename="analytics_events_{days}d_{timestamp}.csv"'
    )

    writer = csv.writer(response)

    rows = list(feature_stats)
    max_path_depth = 0
    if rows:
        max_path_depth = max(
            (len(r["feature_path"].split("|")) - 1 for r in rows if r["feature_path"]),
            default=0,
        )

    path_headers = [f"Feature Path Level {i + 1}" for i in range(max_path_depth)]
    writer.writerow(
        path_headers + [
            "Feature", "Total Events", "Unique Users", "Unique Clients",
            "Click Events", "View Events", "Submit Events",
            "Avg Events / User", "First Seen", "Last Seen", "Usage %",
        ]
    )

    for row in rows:
        avg = round(row["total_events"] / row["unique_users"], 2) if row["unique_users"] else 0
        pct = round((row["total_events"] / total_events_all) * 100, 2)
        path_parts = row["feature_path"].split("|")[:-1] if row["feature_path"] else []
        path_fields = path_parts + [""] * (max_path_depth - len(path_parts))

        writer.writerow(
            path_fields + [
                row["feature"], row["total_events"], row["unique_users"], row["unique_clients"],
                row["click_events"], row["view_events"], row["submit_events"],
                avg,
                row["first_seen"].date() if row["first_seen"] else "",
                row["last_seen"].date() if row["last_seen"] else "",
                f"{pct}%",
            ]
        )

    return response


def export_concept_sessions_csv(
    *,
    case_mapping=None,
    user=None,
) -> HttpResponse:
    """Export ConceptSession records as a CSV file."""

    qs = (
        concept_session_qs(case_mapping=case_mapping, user=user)
        .order_by("case_mapping__id", "user__id", "-started_at")
    )

    response = HttpResponse(content_type="text/csv")
    timestamp = now().strftime("%Y%m%d_%H%M%S")
    slug = f"_{case_mapping.uid}" if case_mapping else ""
    response["Content-Disposition"] = (
        f'attachment; filename="user_sessions{slug}_{timestamp}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "Case Mapping UID",
        "Case Mapping Name",
        "User UID",
        "User Name",
        "User Email",
        "Status",
        "Completion %",
        "Is Active",
        "Started At",
        "Ended At",
        "Last Activity At",
    ])

    for s in qs.iterator(chunk_size=500):
        writer.writerow([
            str(s.case_mapping.uid) if s.case_mapping else "",
            str(s.case_mapping) if s.case_mapping else "",
            str(s.user.uid) if s.user else "",
            s.user.name if s.user else "",
            s.user.get_email() if s.user else "",
            s.status,
            s.completion_percentage,
            s.is_active,
            s.started_at.date() if s.started_at else "",
            s.ended_at.date() if s.ended_at else "",
            s.last_activity_at.date() if s.last_activity_at else "",
        ])

    return response
