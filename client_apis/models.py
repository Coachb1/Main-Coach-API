import hashlib
import secrets
import string
from django.db import models
from django.utils import timezone
from django.core.cache import cache

from commons.db.model import MyModel


def generate_api_key():
    """Generate a secure, human-readable API key: prefix.random_part"""
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(40))
    return f"sk-{random_part}"


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of the raw key — stored in DB, never the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ClientAPIKey(MyModel):
    """
    Multiple API keys per ClientUserInfo.
    The raw key is shown ONCE on creation; only the hash is stored.
    """

    class RateLimitTier(models.TextChoices):
        LOW     = "low",    "Low (60 req/min)"
        MEDIUM  = "medium", "Medium (300 req/min)"
        HIGH    = "high",   "High (1000 req/min)"
        CUSTOM  = "custom", "Custom"

    # ── Relations ────────────────────────────────────────────────────────────
    client = models.ForeignKey(
        "users.ClientUserInfo",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )

    # ── Key material ─────────────────────────────────────────────────────────
    name           = models.CharField(max_length=120, help_text="Friendly label, e.g. 'Production key'")
    prefix         = models.CharField(max_length=10, editable=False)          # first 8 chars for identification
    hashed_key     = models.CharField(max_length=64, unique=True, editable=False)

    # ── Status & expiry ───────────────────────────────────────────────────────
    is_active      = models.BooleanField(default=True)
    expires_at     = models.DateTimeField(null=True, blank=True, help_text="Leave blank for non-expiring key")
    revoked_at     = models.DateTimeField(null=True, blank=True, editable=False)
    revoke_reason  = models.CharField(max_length=255, blank=True)

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_tier        = models.CharField(
        max_length=10, choices=RateLimitTier.choices, default=RateLimitTier.MEDIUM
    )
    custom_rate_limit      = models.IntegerField(
        null=True, blank=True,
        help_text="Requests per minute — only used when tier is 'custom'"
    )

    # ── Allowed IPs (optional extra restriction) ──────────────────────────────
    allowed_ips    = models.JSONField(
        default=list, blank=True,
        help_text="Empty list = all IPs allowed. E.g. ['192.168.1.1', '10.0.0.0/8']"
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    last_used_at   = models.DateTimeField(null=True, blank=True)
    created_by     = models.CharField(max_length=255, blank=True, help_text="email who created this key")

    class Meta:
        db_table      = "client_api_keys"
        ordering      = ["-created"]
        verbose_name  = "Client API Key"
        verbose_name_plural = "Client API Keys"

    # ── Properties ────────────────────────────────────────────────────────────
    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at < timezone.now())

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired and not self.revoked_at

    @property
    def requests_per_minute(self) -> int:
        tier_map = {
            self.RateLimitTier.LOW:    60,
            self.RateLimitTier.MEDIUM: 300,
            self.RateLimitTier.HIGH:   1000,
            self.RateLimitTier.CUSTOM: self.custom_rate_limit or 300,
        }
        return tier_map.get(self.rate_limit_tier, 300)

    # ── Class methods ─────────────────────────────────────────────────────────
    @classmethod
    def create_key(cls, client, name: str, **kwargs) -> tuple["ClientAPIKey", str]:
        """
        Create a new API key.
        Returns (instance, raw_key). raw_key is shown ONCE — store it securely.
        """
        raw_key   = generate_api_key()
        prefix    = raw_key[:8]
        hashed    = hash_api_key(raw_key)

        instance = cls.objects.create(
            client=client,
            name=name,
            prefix=prefix,
            hashed_key=hashed,
            **kwargs,
        )
        return instance, raw_key

    @classmethod
    def get_from_raw_key(cls, raw_key: str) -> "ClientAPIKey | None":
        """Look up by raw key via cache-first hash lookup."""
        hashed     = hash_api_key(raw_key)
        cache_key  = f"apikey:{hashed}"
        cached_pk  = cache.get(cache_key)

        if cached_pk:
            try:
                return cls.objects.select_related("client").get(pk=cached_pk)
            except cls.DoesNotExist:
                cache.delete(cache_key)

        try:
            key = cls.objects.select_related("client").get(hashed_key=hashed)
            cache.set(cache_key, key.pk, timeout=300)   # cache for 5 min
            return key
        except cls.DoesNotExist:
            return None

    def revoke(self, reason: str = ""):
        """Soft-revoke the key and clear its cache entry."""
        self.is_active    = False
        self.revoked_at   = timezone.now()
        self.revoke_reason = reason
        self.save(update_fields=["is_active", "revoked_at", "revoke_reason"])
        cache.delete(f"apikey:{self.hashed_key}")

    def touch(self):
        """Update last_used_at — called on each successful request."""
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    def __str__(self):
        return f"{self.client.client_name} | {self.name} ({self.prefix}…)"


# ─────────────────────────────────────────────────────────────────────────────
# Usage Log
# ─────────────────────────────────────────────────────────────────────────────

class APIKeyUsageLog(MyModel):
    """One row per API request. Write async via Celery (or sync as fallback)."""

    api_key         = models.ForeignKey(
        ClientAPIKey, on_delete=models.SET_NULL, null=True, related_name="usage_logs"
    )
    client          = models.ForeignKey(
        "users.ClientUserInfo",         
        on_delete=models.SET_NULL, null=True, related_name="api_usage_logs"
    )
    endpoint        = models.CharField(max_length=512)
    method          = models.CharField(max_length=10)
    status_code     = models.IntegerField(default=0)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    user_agent      = models.TextField(blank=True)
    request_body    = models.JSONField(null=True, blank=True)   # optional, sanitise PII before storing
    response_ms     = models.IntegerField(default=0, help_text="Response time in ms")
    error_message   = models.TextField(blank=True)
    timestamp       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = "api_key_usage_logs"
        ordering  = ["-timestamp"]
        indexes   = [
            models.Index(fields=["api_key", "timestamp"]),
            models.Index(fields=["client",  "timestamp"]),
        ]

    def __str__(self):
        return f"{self.method} {self.endpoint} → {self.status_code} @ {self.timestamp}"