"""
CSV / Excel export helpers for events and concept sessions.
"""

import csv
import io
import zipfile
from collections import defaultdict
from typing import Optional

from django.db.models import Count, Max, Min, Q
from django.http import HttpResponse
from django.utils.timezone import now

from analytics.models import Event
from commons.export_excel import Column, ExcelExporter, Sheet, Theme
from identities.helpers import get_users_by_client
from .queries import concept_session_qs, event_qs

import logging

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------

def export_timestamp() -> str:
    return now().strftime("%Y%m%d_%H%M%S")


def make_csv_response(filename: str) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def csv_filename(prefix: str, *, days: Optional[int] = None, slug: str = "") -> str:
    day_part = f"_{days}d" if days is not None else ""
    return f"{prefix}{slug}{day_part}_{export_timestamp()}.csv"


def excel_filename(prefix: str, *, days: Optional[int] = None, slug: str = "") -> str:
    day_part = f"_{days}d" if days is not None else ""
    return f"{prefix}{slug}{day_part}_{export_timestamp()}.xlsx"


def get_client_users(client):
    if not client:
        return None
    return get_users_by_client(tenant_id=client.tenant_id, client_id=client.uid)


def get_client_login_context(client):
    """
    Returns:
        (client, no_login, client_name)
    """
    if not client:
        return None, False, ""

    login_view = getattr(getattr(client, "library_bot_config", None), "login_view", "")
    no_login = login_view == "no_login"
    client_name = getattr(client, "client_name", "")
    return client, no_login, client_name


def resolve_session_identity(session, client):
    """
    Resolve the display identity for a session row.
    """
    current_client = client
    if not current_client:
        current_client = session.user.get_client() if session.user else None

    current_client, no_login, client_name = get_client_login_context(current_client)

    user_name = client_name if no_login else (session.user.name if session.user else "")
    email = "" if no_login else (session.user.get_email() if session.user else "")
    return current_client, user_name, email


def aggregate_pillar_clicks(qs):
    pillars = defaultdict(lambda: {"clicks": 0, "last_activity": None})

    for ev in qs.only("feature_path", "created").iterator(chunk_size=2000):
        path = ev.get_path_list()
        if not path:
            continue

        pillar = path[0]
        stats = pillars[pillar]
        stats["clicks"] += 1

        if stats["last_activity"] is None or ev.created > stats["last_activity"]:
            stats["last_activity"] = ev.created

    return pillars


def build_pillar_rows(pillars, total_clicks_all):
    sorted_pillars = sorted(pillars.items(), key=lambda x: x[1]["clicks"], reverse=True)

    rows = []
    for pillar, stats in sorted_pillars:
        pct = round((stats["clicks"] / total_clicks_all) * 100, 2)
        rows.append([
            pillar,
            stats["clicks"],
            stats["last_activity"].date() if stats["last_activity"] else "",
            f"{pct}%",
        ])
    return rows


def build_pillar_sheet(name: str, subtitle: str, rows):
    return Sheet(
        name=name,
        subtitle=subtitle,
        columns=[
            Column("Focus areas", width=28, bold_col=True),
            Column("Total Number of Attempts", width=20, fmt="#,##0", align="center"),
            Column("Last Activity", width=16, align="center"),
            Column("Usage %", width=12, fmt="0.00", align="center"),
        ],
        rows=rows,
        summary={
            "TOTAL": "",
            " ": f"=SUM(B4:B{len(rows) + 3})",
            "  ": "",
            "   ": "",
        },
    )


def build_session_row(session, client, *, case_module_pillar_mode: str = "empty"):
    """
    case_module_pillar_mode:
        - "empty": keeps pillar blank for case_module rows (matches your CSV export)
        - "course": uses case_module.course.title for pillar (matches your Excel export)
    """
    current_client, user_name, email = resolve_session_identity(session, client)

    if session.case_mapping:
        return [
            user_name,
            email,
            str(session.case_mapping.collection.collection_name) if session.case_mapping else "",
            str(session.case_mapping.tab_name) if session.case_mapping else "NA",
            session.completion_percentage or "NA",
            "NA",
            session.last_activity_at.date() if session.last_activity_at else "NA",
        ]

    if session.jobaid_attempted:
        return [
            user_name,
            email,
            session.meta_data.get("collection_name", "NA") if session.meta_data else "NA",
            "NA",
            "NA",
            str(session.jobaid_attempted.job_aid.title) if session.jobaid_attempted and session.jobaid_attempted.job_aid else "NA",
            session.last_activity_at.date() if session.last_activity_at else "NA",
        ]

    if session.case_module:
        if case_module_pillar_mode == "course":
            pillar_value = str(session.case_module.course.title) if getattr(session.case_module, "course", None) else "NA"
        else:
            pillar_value = ""

        return [
            user_name,
            email,
            pillar_value,
            f"{str(session.case_module.author)} - {str(session.case_module.title)}" if session.case_module else "NA",
            session.completion_percentage or "NA",
            "NA",
            session.last_activity_at.date() if session.last_activity_at else "NA",
        ]

    return None


def build_session_rows(qs, client, *, case_module_pillar_mode: str = "empty"):
    rows = []
    current_client = client

    for session in qs.iterator(chunk_size=500):
        if not current_client:
            current_client = session.user.get_client() if session.user else None

        row = build_session_row(
            session,
            current_client,
            case_module_pillar_mode=case_module_pillar_mode,
        )
        if row:
            rows.append(row)

    return rows


def build_session_sheet(name: str, subtitle: str, rows):
    return Sheet(
        name=name,
        subtitle=subtitle,
        columns=[
            Column("User Name", width=24, bold_col=True),
            Column("Email", width=30),
            Column("Focus areas", width=22),
            Column("Module", width=24),
            Column("Completion %", width=14, align="center"),
            Column("Use Case", width=26),
            Column("Last Activity", width=16, align="center"),
        ],
        rows=rows,
    )


# -----------------------------------------------------------------------------
# CSV exports
# -----------------------------------------------------------------------------

def export_events_csv(
    *,
    days: int = 7,
    client=None,
    user=None,
    feature: str = None,
    feature_path: str = None,
) -> HttpResponse:
    """Export event stats grouped by feature / feature_path as CSV."""

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

    rows = list(feature_stats)
    max_path_depth = max(
        (len(r["feature_path"].split("|")) - 1 for r in rows if r["feature_path"]),
        default=0,
    )

    path_headers = [f"Feature Path Level {i + 1}" for i in range(max_path_depth)]

    response = make_csv_response(csv_filename("analytics_events", days=days))
    writer = csv.writer(response)

    writer.writerow(
        path_headers + [
            "Feature",
            "Total Events",
            "Unique Users",
            "Unique Clients",
            "Click Events",
            "View Events",
            "Submit Events",
            "Avg Events / User",
            "First Seen",
            "Last Seen",
            "Usage %",
        ]
    )

    for row in rows:
        avg = round(row["total_events"] / row["unique_users"], 2) if row["unique_users"] else 0
        pct = round((row["total_events"] / total_events_all) * 100, 2)

        path_parts = row["feature_path"].split("|")[:-1] if row["feature_path"] else []
        path_fields = path_parts + [""] * (max_path_depth - len(path_parts))

        writer.writerow(
            path_fields + [
                row["feature"],
                row["total_events"],
                row["unique_users"],
                row["unique_clients"],
                row["click_events"],
                row["view_events"],
                row["submit_events"],
                avg,
                row["first_seen"].date() if row["first_seen"] else "",
                row["last_seen"].date() if row["last_seen"] else "",
                f"{pct}%",
            ]
        )

    return response


def export_pillar_events_csv(
    *,
    days: int = 7,
    client=None,
    user=None,
    feature: str = None,
    feature_path: str = None,
) -> HttpResponse:
    """Export pillar-level click event stats as CSV."""

    qs = event_qs(
        days=days,
        user=user,
        client=client,
        feature=feature,
        feature_path=feature_path,
    ).filter(event_type=Event.CLICK)

    total_clicks_all = qs.count() or 1
    pillars = aggregate_pillar_clicks(qs)
    rows = build_pillar_rows(pillars, total_clicks_all)

    response = make_csv_response(csv_filename("analytics_events", days=days))
    writer = csv.writer(response)
    writer.writerow(["Focus areas", "Total Clicks", "Last Activity", "Usage %"])
    writer.writerows(rows)
    return response


def export_concept_sessions_csv(
    *,
    client=None,
    case_mapping=None,
    module=None,
    jobaid_session=None,
    days: int = None,
) -> HttpResponse:
    """Export ConceptSession records as CSV."""

    users = get_client_users(client)

    qs = (
        concept_session_qs(
            case_mapping=case_mapping,
            module=module,
            jobaid_session=jobaid_session,
            users=users,
            days=days,
        )
        .order_by("case_mapping__id", "user__id", "-started_at")
    )

    rows = build_session_rows(qs, client, case_module_pillar_mode="empty")

    slug = f"_{case_mapping.uid}" if case_mapping else ""
    response = make_csv_response(csv_filename("user_sessions", days=days, slug=slug))
    writer = csv.writer(response)

    writer.writerow([
        "User Name",
        "Email",
        "Focus areas",
        "Module",
        "Completion %",
        "Use case Logged",
        "Last Activity",
    ])
    writer.writerows(rows)
    return response


# -----------------------------------------------------------------------------
# ZIP export
# -----------------------------------------------------------------------------

def export_all_data_zip(days, client=None, feature=None, feature_path=None, case_mapping=None):
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as zf:
        event_response = export_pillar_events_csv(
            days=days,
            client=client,
            feature=feature,
            feature_path=feature_path,
        )
        concept_response = export_concept_sessions_csv(
            client=client,
            case_mapping=case_mapping,
            days=days,
        )

        zf.writestr("events.csv", event_response.content)
        zf.writestr("concept_sessions.csv", concept_response.content)

    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="export_data.zip"'
    return response


# -----------------------------------------------------------------------------
# Excel exports
# -----------------------------------------------------------------------------

def export_analytics_combined_excel(
    *,
    days: int = 7,
    client=None,
    user=None,
    feature: str = None,
    feature_path: str = None,
    case_mapping=None,
) -> HttpResponse:
    """
    Export pillar events + concept sessions as two tabs in a single Excel file.
    """

    # Pillar events
    event_qs_filtered = event_qs(
        days=days,
        user=user,
        client=client,
        feature=feature,
        feature_path=feature_path,
    ).filter(event_type=Event.CLICK)

    total_clicks = event_qs_filtered.count() or 1
    pillars = aggregate_pillar_clicks(event_qs_filtered)
    pillar_rows = build_pillar_rows(pillars, total_clicks)

    pillar_sheet = build_pillar_sheet(
        name="📌 Aggregate Activity",
        subtitle=f"Click activity by 'Focus areas' — last {days} days",
        rows=pillar_rows,
    )

    # Concept sessions
    users = get_client_users(client)

    session_qs = (
        concept_session_qs(
            case_mapping=case_mapping,
            users=users,
            days=days,
            gte_completion_percent=1,
        )
        .order_by("case_mapping__id", "user__id", "-started_at")
    )

    session_rows = build_session_rows(
        session_qs,
        client,
        case_module_pillar_mode="empty",
    )

    session_sheet = build_session_sheet(
        name="🧠 User level Reporting",
        subtitle="In-progress/completed sessions",
        rows=session_rows,
    )

    slug = f"_{case_mapping.uid}" if case_mapping else ""
    return (
        ExcelExporter(
            title=f"Analytics Export — Last {days} days",
            theme=Theme.teal(),
            meta={
                "Period": f"{days} days",
                "Client": str(client) if client else "All",
            },
        )
        .add_sheet(pillar_sheet)
        .add_sheet(session_sheet)
        .to_django_response(excel_filename("analytics", days=days, slug=slug))
    )


def export_pillar_events_excel(
    *,
    days: int = 7,
    client=None,
    user=None,
    feature: str = None,
    feature_path: str = None,
) -> HttpResponse:
    """Export pillar-level click event stats as a styled Excel file."""

    qs = event_qs(
        days=days,
        user=user,
        client=client,
        feature=feature,
        feature_path=feature_path,
    ).filter(event_type=Event.CLICK)

    total_clicks = qs.count() or 1
    pillars = aggregate_pillar_clicks(qs)
    rows = build_pillar_rows(pillars, total_clicks)

    sheet = build_pillar_sheet(
        name="📌 Aggregate Activity",
        subtitle=f"Click activity by 'Focus areas' — last {days} days",
        rows=rows,
    )

    return (
        ExcelExporter(
            title=f"Aggregate Activity — Last {days} days",
            theme=Theme.teal(),
            meta={
                "Period": f"{days} days",
                "Client": str(client) if client else "All",
            },
        )
        .add_sheet(sheet)
        .to_django_response(excel_filename("aggregate_activity", days=days))
    )


def export_concept_sessions_excel(
    *,
    client=None,
    case_mapping=None,
    module=None,
    jobaid_session=None,
    days: int = None,
) -> HttpResponse:
    """Export ConceptSession records as a styled Excel file."""

    users = get_client_users(client)

    qs = (
        concept_session_qs(
            case_mapping=case_mapping,
            module=module,
            jobaid_session=jobaid_session,
            users=users,
            days=days,
            gte_completion_percent=1,
        )
        .order_by("case_mapping__id", "user__id", "-started_at")
    )

    rows = build_session_rows(qs, client, case_module_pillar_mode="empty")

    sheet = build_session_sheet(
        name="🧠 User level Reporting",
        subtitle="In-progress/completed sessions",
        rows=rows,
    )

    slug = f"_{case_mapping.uid}" if case_mapping else ""
    return (
        ExcelExporter(
            title="User level Reporting",
            theme=Theme.teal(),
            meta={
                "Status": "In Progress/Completed",
                "Client": str(client) if client else "All",
                "Period": f"{days} days" if days else "All time",
            },
        )
        .add_sheet(sheet)
        .to_django_response(excel_filename("user_level_reporting", days=days, slug=slug))
    )