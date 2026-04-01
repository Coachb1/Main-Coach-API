"""
analytics/services/queries.py
-------------------------------
Low-level queryset helpers shared by dashboard, export, and other services.
"""

from django.apps import apps
from django.utils.timezone import now, timedelta
from django.db.models import QuerySet

from analytics.models import Event


# ------------------------------------------------------------------ #
#  Event queries                                                       #
# ------------------------------------------------------------------ #

def event_qs(
    *,
    days: int = 7,
    event_type: str = None,
    feature: str = None,
    feature_path: str = None,
    user=None,
    client=None,
) -> QuerySet:
    """
    Return a filtered Event queryset.

    All parameters are optional and combinable. ``feature_path`` is matched
    as a prefix (everything under that path node).
    """
    since = now() - timedelta(days=days)
    qs = Event.objects.filter(created__gte=since)

    qs = _filter_actor(qs, user=user, client=client)

    if event_type:
        qs = qs.filter(event_type=event_type)
    if feature:
        qs = qs.filter(feature=feature)
    if feature_path:
        qs = qs.filter(feature_path__startswith=feature_path)

    return qs


# ------------------------------------------------------------------ #
#  ConceptSession queries                                              #
# ------------------------------------------------------------------ #

def concept_session_qs(
    *,
    case_mapping=None,
    module=None,
    jobaid_session=None,
    status: str = None,
    is_active: bool = None,
    users=[],
    days: int = None,
    gte_completion_percent: int = None,
) -> QuerySet:
    """
    Return a filtered ConceptSession queryset.

    All parameters are optional and combinable.
    """
    ConceptSession = apps.get_model("tests", "ConceptSession")
    qs = ConceptSession.objects.select_related("user", "case_mapping").select_related("case_module").select_related("jobaid_attempted")

    if days:
        since = now() - timedelta(days=days)
        qs = qs.filter(last_activity_at__gte=since)

    if users and len(users) > 0:
        qs = qs.filter(user__in=users)
    if case_mapping:
        qs = qs.filter(case_mapping=case_mapping)
    if module:
        qs = qs.filter(case_module=module)
    if jobaid_session:
        qs = qs.filter(jobaid_attempted=jobaid_session)
    if status:
        qs = qs.filter(status=status)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)

    # if gte_completion_percent:
    qs = qs.filter(status__in=["completed", "in_progress"])
    return qs


# ------------------------------------------------------------------ #
#  Shared                                                             #
# ------------------------------------------------------------------ #

def _filter_actor(qs: QuerySet, *, user=None, client=None) -> QuerySet:
    """Filter events by client (higher priority) or user."""
    if client:
        return qs.filter(client=client)
    if user:
        return qs.filter(user=user)
    return qs
