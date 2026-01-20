from django.db import models
from tenants.models import TenantAwareModel
from users.models import User, ClientUserInfo

class Event(TenantAwareModel):
    EVENT_TYPES = (
        ("click", "Click"),
        ("view", "View"),
        ("submit", "Submit"),
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    feature = models.CharField(max_length=100)  # e.g. "login_button"
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
        db_table = 'event'
        indexes = [
            models.Index(fields=["event_type", "feature"]),
            models.Index(fields=["created"]),
        ]

    def __str__(self):
        return f"{self.event_type} | {self.feature}"
