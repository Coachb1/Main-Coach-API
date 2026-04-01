"""
analytics/services/dashboard.py
---------------------------------
High-level aggregations for the admin dashboard and REST API.
"""

from django.apps import apps
from django.db.models import Count, Avg, Min, Max, Q, F, Value, Case, When, CharField
from django.db.models.functions import Concat

from analytics.models import Event
from .queries import event_qs, concept_session_qs


# ------------------------------------------------------------------ #
#  Event / Click dashboard                                            #
# ------------------------------------------------------------------ #

def dashboard_stats(
    *,
    client=None,
    user=None,
    days: int = 7,
    event_type: str = Event.CLICK,
    feature: str = None,
    feature_path: str = None,
) -> dict:
    """
    Aggregate KPIs and chart data for the main analytics dashboard.

    Returns:
        dict with keys: kpis, charts, meta
    """
    qs = event_qs(
        days=days,
        event_type=event_type,
        feature=feature,
        feature_path=feature_path,
        user=user,
        client=client,
    )

    feature_usage = (
        qs.values("feature", "feature_path")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    top_feature = feature_usage.first()

    daily_usage = (
        qs.extra(select={"day": "date(created)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    return {
        "kpis": {
            "total_events": qs.count(),
            "active_users": (
                qs.exclude(user__isnull=True)
                .values("user")
                .distinct()
                .count()
            ),
            "top_feature": top_feature["feature"] if top_feature else None,
        },
        "charts": {
            "feature_usage": list(feature_usage[:10]),
            "daily_usage": list(daily_usage),
        },
        "meta": {
            "days": days,
            "event_type": event_type,
            "scope": "client" if client else "user" if user else "global",
            "feature_filter": feature,
            "feature_path_filter": feature_path,
        },
    }


def feature_detail_stats(feature: str, *, client=None, user=None, days: int = 7) -> dict:
    """Drill-down stats for a single feature."""
    from users.models import User as UserModel

    qs = event_qs(days=days, feature=feature, user=user, client=client)

    daily_usage = (
        qs.extra(select={"day": "date(created)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    users_qs = (
        qs.exclude(user__isnull=True)
        .values("user__id", "user__uid")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    user_ids = [row["user__id"] for row in users_qs]
    users_map = {u.id: u for u in UserModel.objects.filter(id__in=user_ids)}

    users = [
        {
            "uid": row["user__uid"],
            "email": users_map[row["user__id"]].get_email(),
            "total": row["total"],
        }
        for row in users_qs
        if row["user__id"] in users_map
    ]

    return {
        "feature": feature,
        "days": days,
        "total_events": qs.count(),
        "daily_usage": list(daily_usage),
        "users": users,
    }


def top_features(limit: int = 10, level: int = None) -> list[dict]:
    """
    Return most-clicked features.

    ``level=None`` uses the leaf ``feature`` field.
    ``level=0`` aggregates by the first path segment (e.g. the pillar).
    Negative values count from the end of the path.
    """
    qs = Event.objects.filter(event_type=Event.CLICK)

    if level is None:
        return list(
            qs.values("feature")
            .annotate(total=Count("id"))
            .order_by("-total")[:limit]
        )

    from collections import Counter

    counter = Counter()
    for ev in qs.only("feature_path").iterator(chunk_size=2000):
        path = ev.get_path_list()
        idx = (len(path) + level) if level < 0 else level
        if 0 <= idx < len(path):
            counter[path[idx]] += 1

    return [
        {"feature": feat, "total": cnt}
        for feat, cnt in counter.most_common(limit)
    ]


def clicks_by_day(days: int = 7) -> list[dict]:
    return list(
        event_qs(days=days, event_type=Event.CLICK)
        .extra(select={"day": "date(created)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )


# ------------------------------------------------------------------ #
#  Concept Session dashboard                                          #
# ------------------------------------------------------------------ #

def concept_session_stats(
    *,
    client=None,
    days: int = None,
    case_mapping=None,
    user=None,
    module=None,
    jobaid_session=None,
) -> dict:
    """
    Aggregate completion stats across ConceptSessions.

    When ``case_mapping`` is provided, returns per-user detail for that
    mapping. When omitted, returns a summary across all case mappings.

    Returns:
        dict with keys: summary, by_case_mapping, user_detail, meta
    """
    from identities.helpers import get_users_by_client
    ConceptSession = apps.get_model("tests", "ConceptSession")

    users_to_filter = []
    if client:
        users_to_filter = get_users_by_client(tenant_id=client.tenant_id, client_id=client.uid)
    elif user:
        users_to_filter = [user]

    qs = concept_session_qs(
        case_mapping=case_mapping,
        users=users_to_filter,
        days=days,
        module=module,
        jobaid_session=jobaid_session,
    )

    # --- Per-case-mapping rollup ---
    by_mapping = (
        qs.annotate(
            case_mapping_str=Case(
                When(case_mapping__isnull=False, then=Concat(F("case_mapping__collection__collection_name"), Value(" > "), F("case_mapping__tab_name"))),
                When(case_module__isnull=False, then=F("case_module__title")),
                When(jobaid_attempted__isnull=False, then=F("jobaid_attempted__job_aid__title")),
                default=Value("N/A"),
                output_field=CharField()
            ),
            item_type=Case(
                When(case_mapping__isnull=False, then=Value("case_mapping")),
                When(case_module__isnull=False, then=Value("case_module")),
                When(jobaid_attempted__isnull=False, then=Value("jobaid_attempted")),
                default=Value("unknown"),
                output_field=CharField()
            ),
            item_uid=Case(
                When(case_mapping__isnull=False, then=F("case_mapping__uid")),
                When(case_module__isnull=False, then=F("case_module__uid")),
                When(jobaid_attempted__isnull=False, then=F("jobaid_attempted__uid")),
                default=Value(None),
                output_field=CharField()
            ),
        ).values("case_mapping_str", "item_type", "item_uid").annotate(
            total_sessions=Count("id"),
            completed=Count("id", filter=Q(status=ConceptSession.Status.COMPLETED)),
            in_progress=Count("id", filter=Q(status=ConceptSession.Status.IN_PROGRESS)),
            started=Count("id", filter=Q(status=ConceptSession.Status.STARTED)),
            avg_completion=Avg("completion_percentage"),
            first_started=Min("started_at"),
            last_activity=Max("last_activity_at"))
        .order_by("-total_sessions")
    )

    rows = list(by_mapping)

    # Add completion_rate to each row
    for row in rows:
        total = row["total_sessions"] or 1
        row["completion_rate"] = round(row["completed"] / total * 100, 1)
        row["avg_completion"] = round(row["avg_completion"] or 0, 1)

    # --- Overall KPIs ---
    totals = qs.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status=ConceptSession.Status.COMPLETED)),
        in_progress=Count("id", filter=Q(status=ConceptSession.Status.IN_PROGRESS)),
        avg_pct=Avg("completion_percentage"),
    )

    # --- Per-user detail (only when drilling into a single case_mapping) ---
    user_detail = []
    if case_mapping:
        user_detail = list(
            qs.values(
                "user__uid",
                "status",
                "completion_percentage",
                "is_active",
                "started_at",
                "ended_at",
                "last_activity_at",
            ).order_by("-last_activity_at")
        )

    return {
        "kpis": {
            "total_sessions": totals["total"],
            "completed": totals["completed"],
            "in_progress": totals["in_progress"],
            "completion_rate": round(
                (totals["completed"] / totals["total"] * 100) if totals["total"] else 0,
                1,
            ),
            "avg_completion_pct": round(totals["avg_pct"] or 0, 1),
        },
        "by_case_mapping": rows,
        "user_detail": user_detail,
        "meta": {
            "case_mapping_id": str(case_mapping.uid) if case_mapping else None,
            "scope": "client" if client else "user" if user else "global",
            "days": days,
        },
    }
