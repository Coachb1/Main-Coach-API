import csv
from os import times
from django.db.models import Count, Min, Max, Q
from django.http import HttpResponse
from django.utils.timezone import now, timedelta
from analytics.models import Event
from users.models import User


def top_features(limit=10, level=None):
    """Return the most popular features.

    If *level* is None (the default) we behave as before and tally the leaf
    ``feature`` field.  When ``level`` is an integer we aggregate counts using
    the corresponding element from ``feature_path`` (0-based).  This makes it
    easy to ask for "top pillars" (level=0) or "top order buttons under a
    given pillar" etc.  If the path is too short for an event it is ignored.
    """
    qs = Event.objects.filter(event_type=Event.CLICK)

    if level is None:
        return (
            qs.values("feature")
            .annotate(total=Count("id"))
            .order_by("-total")[:limit]
        )

    # simple python aggregation rather than a complex DB expression; if the
    # dataset grows big we can revisit with JSON functions / KeyTextTransform.
    from collections import Counter

    counter = Counter()
    for ev in qs.iterator():
        path = ev.feature_path or []
        if level < 0:
            # negative indexing from the end
            idx = len(path) + level
        else:
            idx = level
        if 0 <= idx < len(path):
            counter[path[idx]] += 1
    return [
        {"feature": feat, "total": cnt}
        for feat, cnt in counter.most_common(limit)
    ]

def clicks_by_day(days=7):
    since = now() - timedelta(days=days)
    return (
        Event.objects
        .filter(event_type=Event.CLICK, created_at__gte=since)
        .extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

def feature_adoption(feature):
    return (
        Event.objects
        .filter(feature=feature)
        .values("user")
        .distinct()
        .count()
    )




def dashboard_stats(*, client=None, user=None, days=7, event_type='click', feature=None, feature_path=None):
    since = now() - timedelta(days=days)

    qs = Event.objects.filter(created__gte=since)
    qs = filter_by_actor(qs, client=client, user=user)
    
    # Filter by feature if provided
    if feature:
        qs = qs.filter(feature=feature)
    
    # Filter by feature_path prefix if provided
    if feature_path:
        qs = qs.filter(feature_path__startswith=feature_path)

    # Group by both feature and feature_path to show full context
    feature_usage = (
        qs.filter(event_type=event_type)
        .values("feature", "feature_path")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    top_feature = feature_usage.first()

    daily_usage = (
        qs.filter(event_type=event_type)
        .extra(select={"day": "date(created)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )


    return {
        "kpis": {
            "total_events": qs.filter(event_type=event_type).count(),
            "active_users": qs.exclude(user__isnull=True).filter(event_type=event_type).values("user").distinct().count(),
            "top_feature": top_feature["feature"] if top_feature else None,
        },
        "charts": {
            "feature_usage": list(feature_usage[:10]),
            "daily_usage": list(daily_usage),
        },
        "meta": {
            "days": days,
            "scope": "client" if client else "user" if user else "anonymous",
            "feature_filter": feature,
            "feature_path_filter": feature_path,
        }
    }


def filter_by_actor(queryset, *, client=None, user=None):
    """
    Priority:
    1. client
    2. user
    """
    if client:
        return queryset.filter(client=client)

    if user:
        return queryset.filter(user=user)

    return queryset


def feature_detail_stats(feature, *, client=None, days=7):
    since = now() - timedelta(days=days)

    qs = Event.objects.filter(feature=feature, created__gte=since)
    qs = filter_by_actor(qs, client=client)

    total_events = qs.count()

    daily_usage = (
        qs.extra(select={"day": "date(created)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    # 1. Aggregate events per user (1 query)
    users_qs = (
        qs.exclude(user__isnull=True)
        .values("user__id", "user__uid")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    # 2. Fetch all required users in ONE query
    user_ids = [row["user__id"] for row in users_qs]

    users_map = {
        u.id: u for u in User.objects.filter(id__in=user_ids)
    }

    # 3. Build final response (no DB hits)
    users = [
        {
            "uid": row["user__uid"],
            "email": users_map[row["user__id"]].get_email(),
            "total": row["total"],
        }
        for row in users_qs
    ]




    return {
        "feature": feature,
        "days": days,
        "client": client,
        "total_events": total_events,
        "daily_usage": list(daily_usage),
        "users": list(users),
    }


def export_events_csv(days=7, client=None, feature=None, feature_path=None):
    since = now() - timedelta(days=days)

    qs = Event.objects.filter(created__gte=since)

    if client:
        qs = qs.filter(client=client)

    if feature:
        qs = qs.filter(feature=feature)
    
    if feature_path:
        qs = qs.filter(feature_path__startswith=feature_path)

    total_events_all = qs.count() or 1  # avoid division by zero

    feature_stats = (
        qs.values("feature", "feature_path")
        .annotate(
            total_events=Count("id"),
            unique_users=Count("user", distinct=True),
            unique_clients=Count("client", distinct=True),

            click_events=Count("id", filter=Q(event_type="click")),
            view_events=Count("id", filter=Q(event_type="view")),
            submit_events=Count("id", filter=Q(event_type="submit")),

            first_seen=Min("created"),
            last_seen=Max("created"),
        )
        .order_by("-total_events")
    )

    response = HttpResponse(content_type="text/csv")
    timestamp = now().strftime("%Y%m%d_%H%M%S")
    filename = f"analytics_features_{days}d_{timestamp}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Determine max depth of feature path (excluding leaf = feature itself)
    max_path_depth = 0
    if any(row["feature_path"] for row in feature_stats):
        max_path_depth = max(
            len(row["feature_path"].split("|")) - 1  # exclude leaf
            for row in feature_stats
            if row["feature_path"]
        )

    # Build dynamic path-level headers (e.g. "Feature Path Level 1", "Level 2", ...)
    path_headers = [f"Feature Path Level {i + 1}" for i in range(max_path_depth)]

    writer.writerow(path_headers + [
        "Feature",
        "Total Events",
        "Unique Users",
        "Unique Clients",
        "Click Events",
        "View Events",
        "Submit Events",
        "Avg Events per User",
        "First Seen",
        "Last Seen",
        "Usage %",
    ])

    for row in feature_stats:
        avg_per_user = (
            round(row["total_events"] / row["unique_users"], 2)
            if row["unique_users"]
            else 0
        )
        usage_pct = round(
            (row["total_events"] / total_events_all) * 100, 2
        ) if total_events_all else 0

        # Path segments excluding the leaf (which is `feature`)
        path_parts = row["feature_path"].split("|")[:-1] if row["feature_path"] else []
        # Pad with empty strings so every row has the same number of path columns
        path_fields = path_parts + [""] * (max_path_depth - len(path_parts))

        writer.writerow(path_fields + [
            row["feature"],
            row["total_events"],
            row["unique_users"],
            row["unique_clients"],
            row["click_events"],
            row["view_events"],
            row["submit_events"],
            avg_per_user,
            row["first_seen"].date() if row["first_seen"] else "",
            row["last_seen"].date() if row["last_seen"] else "",
            f"{usage_pct}%",
        ])

    return response
