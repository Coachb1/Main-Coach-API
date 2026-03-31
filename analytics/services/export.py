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
from identities.helpers import get_users_by_client
from .queries import event_qs, concept_session_qs
import io
import zipfile
from commons.export_excel import ExcelExporter, Sheet, Column, Theme

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


def export_pillar_events_csv(
    *,
    days: int = 7,
    client=None,
    user=None,
    feature: str = None,
    feature_path: str = None,
) -> HttpResponse:
    """Export pillar-level click event stats as a CSV file."""

    qs = event_qs(days=days, user=user, client=client, feature=feature, feature_path=feature_path).filter(event_type=Event.CLICK)

    total_clicks_all = qs.count() or 1

    pillars = {}
    for ev in qs.only("feature_path", "created").iterator(chunk_size=2000):
        path = ev.get_path_list()
        if not path:
            continue
        pillar = path[0]
        if pillar not in pillars:
            pillars[pillar] = {"clicks": 0, "last_activity": ev.created}
        
        pillars[pillar]["clicks"] += 1
        if ev.created > pillars[pillar]["last_activity"]:
            pillars[pillar]["last_activity"] = ev.created

    response = HttpResponse(content_type="text/csv")
    timestamp = now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = (
        f'attachment; filename="analytics_events_{days}d_{timestamp}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Pillar", "Total Clicks", "Last Activity", "Usage %"])

    sorted_pillars = sorted(pillars.items(), key=lambda x: x[1]["clicks"], reverse=True)

    for pillar, stats in sorted_pillars:
        pct = round((stats["clicks"] / total_clicks_all) * 100, 2)
        writer.writerow([
            pillar, stats["clicks"], stats["last_activity"].date(), f"{pct}%"
        ])

    return response





def export_all_data_zip(days, client=None, feature=None, feature_path=None, case_mapping=None):
    # Create in-memory zip
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, 'w') as zf:
        # Get event CSV response
        event_response = export_pillar_events_csv(
            days=days,
            client=client,
            feature=feature,
            feature_path=feature_path,
        )

        # Get concept CSV response
        concept_response = export_concept_sessions_csv(
            client=client,
            case_mapping=case_mapping,
            days=days,
        )

        # Add files to zip
        zf.writestr("events.csv", event_response.content)
        zf.writestr("concept_sessions.csv", concept_response.content)

    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="export_data.zip"'

    return response


def export_concept_sessions_csv(
    *,
    client=None,
    case_mapping=None,
    days: int = None,
) -> HttpResponse:
    """Export ConceptSession records as a CSV file."""

    users = None
    
    if client:
        users = get_users_by_client(tenant_id=client.tenant_id, client_id=client.uid)
    qs = (
        concept_session_qs(case_mapping=case_mapping, users=users, status="in_progress", days=days)
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
        "User Name",
        "Email",
        "Pillar",
        "Module",
        "Completion %",
        "Use case Logged",
        "Last Activity",
    ])

    for s in qs.iterator(chunk_size=500):
        if not client:
            client = s.user.get_client() if s.user else None
        user_name = client.client_name if client.library_bot_config.login_view == "no_login" else s.user.name if s.user else ""
        email = "" if client.library_bot_config.login_view == "no_login" else s.user.get_email() if s.user else ""


        if s.case_mapping:
            writer.writerow([
                user_name,
                email,
                str(s.case_mapping.collection.collection_name) if s.case_mapping else "",
                str(s.case_mapping.tab_name) if s.case_mapping else "NA",
                s.completion_percentage or "NA",
                "NA",
                s.last_activity_at.date() if s.last_activity_at else "NA",
            ])
        elif s.jobaid_attempted:
            writer.writerow([
                user_name,
                email,
                s.meta_data.get("collection_name", "NA") if s.meta_data else "NA",
                "NA",
                "NA",
                str(s.jobaid_attempted.title) if s.jobaid_attempted else "NA",
                s.last_activity_at.date() if s.last_activity_at else "NA",
            ])

    return response


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

    # ── Tab 1: Pillar events ─────────────────────────────────────────────────
    qs = event_qs(
        days=days, user=user, client=client,
        feature=feature, feature_path=feature_path
    ).filter(event_type=Event.CLICK)

    total_clicks = qs.count() or 1
    pillars = {}

    for ev in qs.only("feature_path", "created").iterator(chunk_size=2000):
        path = ev.get_path_list()
        if not path:
            continue
        pillar = path[0]
        if pillar not in pillars:
            pillars[pillar] = {"clicks": 0, "last_activity": ev.created}
        pillars[pillar]["clicks"] += 1
        if ev.created > pillars[pillar]["last_activity"]:
            pillars[pillar]["last_activity"] = ev.created

    pillar_rows = [
        [
            pillar,
            stats["clicks"],
            stats["last_activity"].date(),
            round((stats["clicks"] / total_clicks) * 100, 2),
        ]
        for pillar, stats in sorted(pillars.items(), key=lambda x: x[1]["clicks"], reverse=True)
    ]

    pillar_sheet = Sheet(
        name="📌 Pillar Events",
        subtitle=f"Click activity by pillar — last {days} days",
        columns=[
            Column("Pillar",        width=28, bold_col=True),
            Column("Total Clicks",  width=14, fmt="#,##0", align="center"),
            Column("Last Activity", width=16,              align="center"),
            Column("Usage %",       width=12, fmt="0.00",  align="center"),
        ],
        rows=pillar_rows,
        summary={
            "TOTAL": "",
            " ":     f"=SUM(B4:B{len(pillar_rows) + 4})",
            "  ":    "",
            "   ":   "",
        },
    )

    # ── Tab 2: Concept sessions ──────────────────────────────────────────────
    users = []
    if client:
        users = get_users_by_client(tenant_id=client.tenant_id, client_id=client.uid)

    session_qs = (
        concept_session_qs(
            case_mapping=case_mapping, users=users,
            days=days,
            gte_completion_percent=1
        )
        .order_by("case_mapping__id", "user__id", "-started_at")
    )

    qs = (
        concept_session_qs(case_mapping=case_mapping, users=users, status="in_progress", days=days)
        .order_by("case_mapping__id", "user__id", "-started_at")
    )

    session_rows = []
    _client = client

    for s in session_qs.iterator(chunk_size=500):
        if not _client:
            _client = s.user.get_client() if s.user else None

        no_login  = _client and _client.library_bot_config.login_view == "no_login"
        user_name = _client.client_name if no_login else (s.user.name if s.user else "")
        email     = "" if no_login else (s.user.get_email() if s.user else "")

        if s.case_mapping:
            session_rows.append([
                user_name, email,
                str(s.case_mapping.collection.collection_name) if s.case_mapping else "",
                str(s.case_mapping.tab_name)                   if s.case_mapping else "NA",
                s.completion_percentage or "NA",
                "NA",
                s.last_activity_at.date() if s.last_activity_at else "NA",
            ])
        elif s.jobaid_attempted:
            session_rows.append([
                user_name, email,
                s.meta_data.get("collection_name", "NA") if s.meta_data else "NA",
                "NA", "NA",
                str(s.jobaid_attempted.title) if s.jobaid_attempted else "NA",
                s.last_activity_at.date() if s.last_activity_at else "NA",
            ])

    session_sheet = Sheet(
        name="🧠 Concept Sessions",
        subtitle="In-progress/completed concept sessions",
        columns=[
            Column("User Name",     width=24, bold_col=True),
            Column("Email",         width=30),
            Column("Pillar",        width=22),
            Column("Module",        width=24),
            Column("Completion %",  width=14, align="center"),
            Column("Use Case",      width=26),
            Column("Last Activity", width=16, align="center"),
        ],
        rows=session_rows,
    )

    # ── Combine & return ─────────────────────────────────────────────────────
    slug      = f"_{case_mapping.uid}" if case_mapping else ""
    timestamp = now().strftime("%Y%m%d_%H%M%S")

    return (
        ExcelExporter(
            title=f"Analytics Export — Last {days} days",
            theme=Theme.navy(),
            meta={
                "Period":       f"{days} days",
                "Client":       str(client)       if client       else "All",
            },
        )
        .add_sheet(pillar_sheet)
        .add_sheet(session_sheet)
        .to_django_response(f"analytics{slug}_{days}d_{timestamp}.xlsx")
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
        days=days, user=user, client=client,
        feature=feature, feature_path=feature_path
    ).filter(event_type=Event.CLICK)

    total_clicks = qs.count() or 1

    # ── Aggregate pillars ────────────────────────────────────────────────────
    pillars = {}
    for ev in qs.only("feature_path", "created").iterator(chunk_size=2000):
        path = ev.get_path_list()
        if not path:
            continue
        pillar = path[0]
        if pillar not in pillars:
            pillars[pillar] = {"clicks": 0, "last_activity": ev.created}
        pillars[pillar]["clicks"] += 1
        if ev.created > pillars[pillar]["last_activity"]:
            pillars[pillar]["last_activity"] = ev.created

    sorted_pillars = sorted(pillars.items(), key=lambda x: x[1]["clicks"], reverse=True)

    rows = [
        [
            pillar,
            stats["clicks"],
            stats["last_activity"].date(),
            round((stats["clicks"] / total_clicks) * 100, 2),
        ]
        for pillar, stats in sorted_pillars
    ]

    # ── Build sheet ──────────────────────────────────────────────────────────
    sheet = Sheet(
        name="📌 Pillars",
        subtitle=f"Click activity by pillar — last {days} days",
        columns=[
            Column("Pillar",        width=28, bold_col=True),
            Column("Total Clicks",  width=14, fmt="#,##0",  align="center"),
            Column("Last Activity", width=16,               align="center"),
            Column("Usage %",       width=12, fmt="0.00",   align="center"),
        ],
        rows=rows,
        summary={
            "TOTAL":  "",
            " ":      f"=SUM(B4:B{len(rows) + 4})",
            "  ":     "",
            "   ":    "",
        },
    )

    timestamp = now().strftime("%Y%m%d_%H%M%S")
    return (
        ExcelExporter(
            title=f"Pillar Events — Last {days} days",
            theme=Theme.navy(),
            meta={
                "Period":       f"{days} days",
                "Client":       str(client) if client else "All",
            },
        )
        .add_sheet(sheet)
        .to_django_response(f"pillar_events_{days}d_{timestamp}.xlsx")
    )


def export_concept_sessions_excel(
    *,
    client=None,
    case_mapping=None,
    days: int = None,
) -> HttpResponse:
    """Export ConceptSession records as a styled Excel file."""

    users = None
    if client:
        users = get_users_by_client(tenant_id=client.tenant_id, client_id=client.uid)

    qs = (
        concept_session_qs(
            case_mapping=case_mapping, users=users,
            days=days,
            gte_completion_percent=1
        )
        .order_by("case_mapping__id", "user__id", "-started_at")
    )

    # ── Build rows ───────────────────────────────────────────────────────────
    rows = []
    _client = client  # avoid mutating the outer variable inside the loop

    for s in qs.iterator(chunk_size=500):
        if not _client:
            _client = s.user.get_client() if s.user else None

        no_login  = _client and _client.library_bot_config.login_view == "no_login"
        user_name = _client.client_name if no_login else (s.user.name if s.user else "")
        email     = "" if no_login else (s.user.get_email() if s.user else "")

        if s.case_mapping:
            rows.append([
                user_name,
                email,
                str(s.case_mapping.collection.collection_name) if s.case_mapping else "",
                str(s.case_mapping.tab_name)                   if s.case_mapping else "NA",
                s.completion_percentage or "NA",
                "NA",
                s.last_activity_at.date() if s.last_activity_at else "NA",
            ])
        elif s.jobaid_attempted:
            rows.append([
                user_name,
                email,
                s.meta_data.get("collection_name", "NA") if s.meta_data else "NA",
                "NA",
                "NA",
                str(s.jobaid_attempted.title) if s.jobaid_attempted else "NA",
                s.last_activity_at.date() if s.last_activity_at else "NA",
            ])

    # ── Build sheet ──────────────────────────────────────────────────────────
    sheet = Sheet(
        name="🧠 Sessions",
        subtitle="In-progress/completed concept sessions",
        columns=[
            Column("User Name",     width=24, bold_col=True),
            Column("Email",         width=30),
            Column("Pillar",        width=22),
            Column("Module",        width=24),
            Column("Completion %",  width=14, align="center"),
            Column("Use Case",      width=26),
            Column("Last Activity", width=16, align="center"),
        ],
        rows=rows,
    )

    slug      = f"_{case_mapping.uid}" if case_mapping else ""
    timestamp = now().strftime("%Y%m%d_%H%M%S")
    return (
        ExcelExporter(
            title="User Concept Sessions",
            theme=Theme.navy(),
            meta={
                "Status":       "In Progress/Completed",
                "Client":       str(client)       if client       else "All",
                "Period":       f"{days} days"    if days         else "All time",
            },
        )
        .add_sheet(sheet)
        .to_django_response(f"user_sessions{slug}_{timestamp}.xlsx")
    )