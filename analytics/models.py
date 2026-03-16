from django.db import models
from tenants.models import TenantAwareModel
from users.models import User, ClientUserInfo


class Event(TenantAwareModel):
    """
    Immutable event record. One row per user action.

    Event types are intentionally kept as string constants (not an Enum or
    separate table) so callers can track ad-hoc events without a migration.
    Register well-known types in EVENT_TYPES for validation; unknown types
    are still accepted and stored so nothing is silently dropped.
    """

    # ------------------------------------------------------------------ #
    #  Well-known event type constants                                     #
    # ------------------------------------------------------------------ #
    CLICK = "click"
    READ = "read"
    VIEW = "view"
    SUBMIT = "submit"

    EVENT_TYPES = (
        (CLICK, "Click"),
        (READ, "Read"),
        (VIEW, "View"),
        (SUBMIT, "Submit"),
    )

    # ------------------------------------------------------------------ #
    #  Fields                                                              #
    # ------------------------------------------------------------------ #
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)

    # Leaf feature name — kept denormalised for fast single-column lookups.
    feature = models.CharField(max_length=100, db_index=True)

    # Full hierarchical path, pipe-delimited, e.g. "pillar|section|button".
    # Storing as a delimited string keeps the schema simple while still
    # allowing prefix-based queries (LIKE 'pillar|section%').
    feature_path = models.CharField(max_length=500, default="", blank=True)

    user = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="analytics_events",
    )
    client = models.ForeignKey(
        ClientUserInfo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="analytics_events",
    )

    # Arbitrary extra data — never query inside this field; use feature/path.
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "event"
        indexes = [
            models.Index(fields=["event_type", "feature"], name="ev_type_feat_idx"),
            models.Index(fields=["feature", "feature_path"], name="ev_feat_path_idx"),
            models.Index(fields=["created"], name="ev_created_idx"),
            models.Index(fields=["client", "created"], name="ev_client_created_idx"),
            models.Index(fields=["user", "created"], name="ev_user_created_idx"),
        ]

    # ------------------------------------------------------------------ #
    #  Class-level factory                                                 #
    # ------------------------------------------------------------------ #
    @classmethod
    def track(
        cls,
        event_type: str,
        feature: str,
        *,
        feature_path=None,
        metadata: dict = None,
        user=None,
        client=None,
    ) -> "Event":
        """
        Preferred factory method. Normalises feature_path and derives
        feature from path when not explicitly supplied.

        Args:
            event_type: One of the EVENT_TYPES constants or any custom string.
            feature:    Leaf feature identifier (e.g. "workspace_btn").
            feature_path: Either a pipe-delimited string or a list of strings
                          representing the full path hierarchy.
            metadata:   Optional free-form dict stored in the JSONField.
            user:       User instance (optional).
            client:     ClientUserInfo instance (optional).
        """
        path_str = cls._normalise_path(feature_path, feature)
        if not feature and path_str:
            feature = path_str.split("|")[-1]

        return cls.objects.create(
            event_type=event_type,
            feature=feature,
            feature_path=path_str,
            metadata=metadata or {},
            user=user,
            client=client,
        )

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalise_path(feature_path, feature: str) -> str:
        if feature_path is None:
            return feature or ""
        if isinstance(feature_path, list):
            return "|".join(str(s) for s in feature_path)
        return str(feature_path)

    def get_path_list(self) -> list[str]:
        """Return feature_path as a Python list."""
        return self.feature_path.split("|") if self.feature_path else []

    def __str__(self):
        path = self.feature_path or self.feature
        return f"[{self.event_type}] {path}"
