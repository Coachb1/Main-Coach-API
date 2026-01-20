import csv
from django.db.models import Count, Min, Max, Q
from django.http import HttpResponse
from django.utils.timezone import now, timedelta
from analytics.models import Event
from users.models import User


def top_features(limit=10):
    return (
        Event.objects
        .filter(event_type=Event.CLICK)
        .values("feature")
        .annotate(total=Count("id"))
        .order_by("-total")[:limit]
    )

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




def dashboard_stats(*, client=None, user=None, days=7, event_type='click'):
    since = now() - timedelta(days=days)

    qs = Event.objects.filter(created__gte=since)
    qs = filter_by_actor(qs, client=client, user=user)

    feature_usage = (
        qs.filter(event_type=event_type)
        .values("feature")
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
            "active_users": qs.exclude(user__isnull=True).values("user").distinct().count(),
            "top_feature": top_feature["feature"] if top_feature else None,
        },
        "charts": {
            "feature_usage": list(feature_usage[:10]),
            "daily_usage": list(daily_usage),
        },
        "meta": {
            "days": days,
            "scope": "client" if client else "user" if user else "anonymous",
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


def export_events_csv(days=7, client=None, feature=None):
    since = now() - timedelta(days=days)

    qs = Event.objects.filter(created__gte=since)

    if client:
        qs = qs.filter(client=client)

    if feature:
        qs = qs.filter(feature=feature)

    total_events_all = qs.count() or 1  # avoid division by zero

    feature_stats = (
        qs.values("feature")
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
    filename = f"analytics_features_{days}d.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    writer.writerow([
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
        "Usage %"
    ])

    for row in feature_stats:
        avg_per_user = (
            round(row["total_events"] / row["unique_users"], 2)
            if row["unique_users"]
            else 0
        )

        usage_pct = round(
            (row["total_events"] / total_events_all) * 100, 2
        )

        writer.writerow([
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
