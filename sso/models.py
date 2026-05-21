import logging
from django.db import models
from django.utils import timezone
from users.models import User
from tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)


class UserIdentityProvider(TenantAwareModel):
    """
    Model to track SSO identity providers linked to users.
    
    Allows linking multiple identity providers (Microsoft, Google, etc.) to a single user.
    Stores the provider-specific ID and other metadata for audit and debugging.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='identity_providers')
    provider = models.CharField(
        max_length=50,
        choices=[
            ('microsoft', 'Microsoft'),
            ('google', 'Google'),
        ],
        help_text="The SSO provider (e.g., 'microsoft', 'google')"
    )
    provider_id = models.CharField(
        max_length=255,
        help_text="Stable ID from provider (e.g., oid from Entra)"
    )
    tid = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Multi-tenant ID from provider (e.g., tid from Entra)"
    )
    email = models.EmailField(
        max_length=255,
        help_text="Last seen email from provider"
    )
    raw_claims = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full decoded claims for debugging"
    )
    first_login = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp of first login with this provider"
    )
    last_login = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp of most recent login"
    )
    
    class Meta:
        db_table = 'sso_user_identity_provider'
        unique_together = ('tid', 'provider', 'provider_id')
        indexes = [
            models.Index(fields=['tid', 'provider', 'provider_id']),
            models.Index(fields=['tid', 'email']),
            models.Index(fields=['user_id']),
        ]
    
    def __str__(self):
        return f"{self.user.uid} - {self.provider} ({self.provider_id})"
    
    def update_last_login(self):
        """Update the last login timestamp."""
        self.last_login = timezone.now()
        self.save(update_fields=['last_login'])
