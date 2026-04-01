"""
analytics/trackers/progress_tracker.py
----------------------------------------
Handles concept session lifecycle: start → update → complete.

ConceptSession lives outside the analytics app (typically in `tests`).
We import it lazily via Django's app registry to avoid a hard circular
dependency — the import happens only when a method is actually called.
"""

from __future__ import annotations

from django.apps import apps
from django.utils.timezone import now

from .base import BaseTracker
import logging

logger = logging.getLogger(__name__)


def _session_model():
    """Lazy import of ConceptSession to avoid circular imports."""
    return apps.get_model("tests", "ConceptSession")

def _jobaid_session_model():
    """Lazy import of JobAidSession to avoid circular imports."""
    return apps.get_model("jobaid", "JobAidSession")

class ProgressTracker(BaseTracker):
    """
    Manages ConceptSession records for analytics purposes.

    Lifecycle
    ---------
        1. start()           — create (or resume) the active session
        2. update_progress() — advance completion_percentage + status
        3. complete()        — seal the session (ended_at, 100%, status=COMPLETED)

    All methods are idempotent:
        - start() on an already-active session returns the existing record.
        - complete() on an already-completed session is a no-op.
        - update_progress() clamps percentage to [0, 100].

    Usage
    -----
        from analytics.trackers import progress_tracker

        session = progress_tracker.start(user=user, case_mapping=case_mapping)

        session = progress_tracker.update_progress(
            user=user,
            case_mapping=case_mapping,
            completion_percentage=45.0,
        )

        session = progress_tracker.complete(user=user, case_mapping=case_mapping)
    """

    name = "progress"

    # ------------------------------------------------------------------ #
    #  Core lifecycle methods                                             #
    # ------------------------------------------------------------------ #

    def record(self, *, user, case_mapping, module, completion_percentage: float = 0.0, **kwargs):
        """
        BaseTracker contract implementation.

        Delegates to start() when completion_percentage == 0,
        complete() when == 100, and update_progress() otherwise.
        This lets the registry call tracker.record(...) uniformly.
        """
        pct = float(completion_percentage)
        if pct >= 100:
            return self.complete(user=user, case_mapping=case_mapping, module=module)
        if pct == 0:
            return self.start(user=user, case_mapping=case_mapping, module=module)
        return self.update_progress(
            user=user,
            case_mapping=case_mapping,
            module=module,
            completion_percentage=pct,
        )

    def start(self, *, user, case_mapping, module):
        """
        Create a new active session or return the existing active one.

        If a completed session exists for this (user, case_mapping) pair,
        a fresh session is created (the old one is not mutated).

        Returns:
            ConceptSession instance (status = STARTED or IN_PROGRESS).
        """
        ConceptSession = _session_model()

        # Return existing active session if present
        active = self._get_active(user, case_mapping, module)
        if active:
            return active

        # Deactivate any stale active sessions before creating a new one
        # (guards against the unique_active_session constraint)
        ConceptSession.objects.filter(
            user=user,
            case_mapping=case_mapping,
            case_module=module,
            is_active=True,
        ).update(is_active=False)

        return ConceptSession.objects.create(
            user=user,
            case_mapping=case_mapping,
            case_module=module,
            status=ConceptSession.Status.STARTED,
            completion_percentage=0.0,
            is_active=True,
        )

    def update_progress(
        self,
        *,
        user,
        case_mapping,
        module,
        completion_percentage: float,
    ):
        """
        Update completion_percentage on the active session and advance
        status to IN_PROGRESS.

        Creates the session automatically if one doesn't exist yet.

        Args:
            user:                 User instance.
            case_mapping:         CaseMappings instance.
            completion_percentage: Float in [0, 100]. Clamped automatically.

        Returns:
            Updated ConceptSession instance.
        """
        ConceptSession = _session_model()

        pct = max(0.0, min(100.0, float(completion_percentage)))

        # Shortcut: treat 100% as a completion
        if pct >= 80:
            return self.complete(user=user, case_mapping=case_mapping, module=module)

        session = self._get_active(user, case_mapping, module)
        if not session:
            session = self.start(user=user, case_mapping=case_mapping, module=module)

        session.completion_percentage = pct
        session.status = ConceptSession.Status.IN_PROGRESS
        # last_activity_at is auto_now — no need to set manually
        session.save(update_fields=["completion_percentage", "status", "last_activity_at"])
        return session

    def complete(self, *, user, case_mapping, module):
        """
        Mark the active session as completed and seal it.

        Sets:
            status              → COMPLETED
            completion_percentage → 100.0
            ended_at            → now()
            is_active           → False

        Idempotent — if no active session exists, looks for the most
        recent completed one and returns it without mutation.

        Returns:
            ConceptSession instance (status = COMPLETED).
        """
        ConceptSession = _session_model()

        session = self._get_active(user, case_mapping, module)

        if not session:
            # Already completed — return most recent record
            return (
                ConceptSession.objects.filter(
                    user=user,
                    case_mapping=case_mapping,
                    case_module=module,
                    status=ConceptSession.Status.COMPLETED,
                )
                .order_by("-started_at")
                .first()
            )

        session.status = ConceptSession.Status.COMPLETED
        session.completion_percentage = 100.0
        session.ended_at = now()
        session.is_active = False
        session.save(update_fields=[
            "status", "completion_percentage", "ended_at", "is_active", "last_activity_at"
        ])
        return session
    
    def log_jobaid_attempt(self, *, user, jobaid_session, collection):
        """
        Log a JobAid attempt as a ConceptSession.
        """
        ConceptSession = _session_model()
        if not jobaid_session:
            return None

        session, created = ConceptSession.objects.get_or_create(
            user=user,
            jobaid_attempted=jobaid_session,
            defaults={
                "status": ConceptSession.Status.COMPLETED,
                "completion_percentage": 100.0,
                "ended_at": now(),
                "is_active": False,
                "meta_data": {
                    "jobaid_session_id": jobaid_session.uid,
                    "jobaid_id": jobaid_session.id,
                    "jobaid_title": jobaid_session.job_aid.title,
                    "collection_name": collection.collection_name if collection else None,
                    "collection_id": collection.uid if collection else None,
                    }
            }
        )
        logger.info(f"Logged JobAid attempt as ConceptSession: user={user.id}, jobaid_session={jobaid_session.uid}, created={created}")
        return session
        
    # ------------------------------------------------------------------ #
    #  Query helpers                                                      #
    # ------------------------------------------------------------------ #

    def get_active(self, *, user, case_mapping, module):
        """Return the current active session or None."""
        return self._get_active(user, case_mapping, module)

    def get_latest(self, *, user, case_mapping, module):
        """Return the most recent session (any status) or None."""
        ConceptSession = _session_model()
        return (
            ConceptSession.objects.filter(user=user, case_mapping=case_mapping, case_module=module)
            .order_by("-started_at")
            .first()
        )

    def get_all_for_user(self, *, user, status: str = None):
        """
        Return all sessions for a user, optionally filtered by status.

        Args:
            user:   User instance.
            status: One of ConceptSession.Status values, or None for all.
        """
        ConceptSession = _session_model()
        qs = ConceptSession.objects.filter(user=user).select_related("case_mapping")
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("-started_at")

    # ------------------------------------------------------------------ #
    #  Private                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_active(user, case_mapping, module):
        ConceptSession = _session_model()
        return ConceptSession.objects.filter(
            user=user,
            case_mapping=case_mapping,
            case_module=module,
            is_active=True,
        ).first()
