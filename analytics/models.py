from django.db import models
from django.db.models import aggregates
from commons.db.model import MyModel
from tenants.models import TenantAwareModel
from users.models import User, ClientUserInfo


class Event(TenantAwareModel):

    @staticmethod
    def track_event(event_type, feature, feature_path=None, metadata=None, user=None, client=None):
        if feature_path is None:
            feature_path = feature
        elif isinstance(feature_path, list):
            feature_path = "|".join(feature_path) if feature_path else ""

        event = Event.objects.create(
            event_type=event_type,
            feature=feature,
            feature_path=feature_path,
            metadata=metadata or {},
            user=user,
            client=client,
        )
        return event
    

    EVENT_TYPES = (
        ("click", "Click"),
        ("view", "View"),
        ("submit", "Submit"),
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)

    # leaf feature (fast filtering)
    feature = models.CharField(max_length=100)

    # hierarchical feature path, stored as delimited string (e.g. "pillar|button1|workspace_btn")
    # delimited by "|" for fast queries in MySQL
    feature_path = models.CharField(max_length=500, default="", blank=True)

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    client = models.ForeignKey(
        ClientUserInfo,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    metadata = models.JSONField(default=dict, blank=True)
    

    class Meta:
        db_table = "event"
        indexes = [
            models.Index(fields=["event_type", "feature"]),
            models.Index(fields=["created"]),
            models.Index(fields=["feature"]),
        ]

    def get_feature_path(self):
        """Return feature_path as a list."""
        if not self.feature_path:
            return []
        return self.feature_path.split("|")

    def save(self, *args, **kwargs):
        # accept list or string for feature_path and normalize to delimited string
        if isinstance(self.feature_path, list):
            self.feature_path = "|".join(self.feature_path) if self.feature_path else ""

        path_list = self.get_feature_path()

        # keep feature + feature_path consistent
        if path_list and not self.feature:
            self.feature = path_list[-1]
        elif self.feature and not path_list:
            self.feature_path = self.feature
        elif path_list and self.feature:
            if path_list[-1] != self.feature:
                self.feature = path_list[-1]

        super().save(*args, **kwargs)

    def __str__(self):
        path_list = self.get_feature_path()
        if path_list:
            return f"{self.event_type} | {'/'.join(path_list)}"
        return f"{self.event_type} | {self.feature}"
    

