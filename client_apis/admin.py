from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from client_apis.email import send_api_key_creation_email
from .models import ClientAPIKey, APIKeyUsageLog
from .models import generate_api_key, hash_api_key

import logging
logger = logging.getLogger(__name__)

@admin.register(ClientAPIKey)
class ClientAPIKeyAdmin(admin.ModelAdmin):
    list_display  = [
        "client", "name", "prefix_display", "rate_limit_tier",
        "is_active", "is_expired_display", "last_used_at", "created",
    ]
    list_filter   = ["is_active", "rate_limit_tier", "client"]
    search_fields = ["client__client_name", "name", "prefix"]
    readonly_fields = [
        "prefix", "hashed_key", "created", "last_used_at",
        "revoked_at", "revoke_reason",
    ]
    actions = ["revoke_selected_keys"]

    fieldsets = (
        ("Key Info", {
            "fields": ("client", "name", "prefix", "hashed_key", "created_by"),
        }),
        ("Status", {
            "fields": ("is_active", "expires_at", "revoked_at", "revoke_reason"),
        }),
        ("Rate Limiting", {
            "fields": ("rate_limit_tier", "custom_rate_limit"),
        }),
        ("Security", {
            "fields": ("allowed_ips",),
        }),
        ("Timestamps", {
            "fields": ("created", "last_used_at"),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            raw_key = generate_api_key()
            obj.prefix = raw_key[:8]
            obj.hashed_key = hash_api_key(raw_key)
            try:
                send_api_key_creation_email(
                    to_email  = obj.created_by,
                    client    = obj.client,
                    key_name  = obj.name,
                    raw_key   = raw_key,
                    prefix    = obj.prefix,
                    expires_at= obj.expires_at,
                    rate_limit= obj.requests_per_minute,
                )
            except Exception as exc:
                logger.error("API key email failed for %s: %s", obj.created_by, exc)

            self.message_user(request, f"New API Key created. Raw key (copy and save securely): {raw_key}")
        super().save_model(request, obj, form, change)

    def prefix_display(self, obj):
        return f"{obj.prefix}…"
    prefix_display.short_description = "Key prefix"

    def is_expired_display(self, obj):
        if obj.is_expired:
            return format_html('<span style="color:red;">Expired</span>')
        if obj.expires_at:
            return format_html('<span style="color:green;">Valid until {}</span>', obj.expires_at.date())
        return format_html('<span style="color:grey;">No expiry</span>')
    is_expired_display.short_description = "Expiry status"

    @admin.action(description="Revoke selected API keys")
    def revoke_selected_keys(self, request, queryset):
        count = 0
        for key in queryset.filter(is_active=True):
            key.revoke(reason="Bulk revoked via admin")
            count += 1
        self.message_user(request, f"{count} key(s) revoked.")


@admin.register(APIKeyUsageLog)
class APIKeyUsageLogAdmin(admin.ModelAdmin):
    list_display  = ["timestamp", "client", "api_key", "method", "endpoint", "status_code", "response_ms"]
    list_filter   = ["method", "status_code", "client"]
    search_fields = ["endpoint", "ip_address", "client__client_name"]
    readonly_fields = [f.name for f in APIKeyUsageLog._meta.fields]

    def has_add_permission(self, request):
        return False   # Logs are system-generated only

    def has_change_permission(self, request, obj=None):
        return False