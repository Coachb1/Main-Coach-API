import re

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from client_apis.email import send_api_key_creation_email
from client_apis.models import ClientAPIKey, APIKeyUsageLog
from clients.permissions import IsAuthenticatedClient
from users.models import ClientUserInfo
from users.permissions import IsAuthenticatedUser
from .serializers import (
    ClientAPIKeyCreateSerializer,
    ClientAPIKeyReadSerializer,
    ClientAPIKeyCreatedSerializer,
    RevokeAPIKeySerializer,
    APIKeyUsageLogSerializer,
)
from commons.throttling import APIKeyRateThrottle
import logging

logger = logging.getLogger("client_apis.usage")


# ─────────────────────────────────────────────────────────────────────────────
# Key Management  (called by YOUR admin / dashboard — not by external clients)
# ─────────────────────────────────────────────────────────────────────────────

class APIKeyListCreateView(APIView):
    """
    GET  internal/clients/<client_id>/keys/   → list all keys for a client
    POST internal/clients/<client_id>/keys/   → create a new key (raw key returned ONCE)
    """
    permission_classes = [IsAuthenticatedClient, IsAuthenticatedUser]  

    def get_client(self, client_id):
        return get_object_or_404(ClientUserInfo, pk=client_id)
    

    def get(self, request, client_id):
        client = self.get_client(client_id)
        keys   = ClientAPIKey.objects.filter(client=client)
        data   = ClientAPIKeyReadSerializer(keys, many=True).data
        return Response(data)

    def post(self, request, client_id):
        client     = self.get_client(client_id)
        serializer = ClientAPIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vd = serializer.validated_data
        instance, raw_key = ClientAPIKey.create_key(
            client          = client,
            name            = vd["name"],
            expires_at      = vd.get("expires_at"),
            rate_limit_tier = vd.get("rate_limit_tier", ClientAPIKey.RateLimitTier.MEDIUM),
            custom_rate_limit = vd.get("custom_rate_limit"),
            allowed_ips     = vd.get("allowed_ips", []),
            created_by      = vd.get("created_by", client.owner_id if client.owner_id else ""),
        )

        out = ClientAPIKeyCreatedSerializer(instance).data
        out["raw_key"] = raw_key   # shown once

        try:
            send_api_key_creation_email(
                to_email  = instance.created_by,
                client    = instance.client,
                key_name  = instance.name,
                raw_key   = raw_key,
                prefix    = instance.prefix,
                expires_at= instance.expires_at,
                rate_limit= instance.requests_per_minute,
            )
        except Exception as exc:
            logger.error("API key email failed for %s: %s", instance.created_by, exc)
            # Do NOT fail the request — key is created, email is best-effort
 
        return Response(
            {
                "message": "API key created. Store the raw_key securely — it will not be shown again.",
                "key": out,
            },
            status=status.HTTP_201_CREATED,
        )


class APIKeyDetailView(APIView):
    """
    GET    /keys/<key_id>/   → key details
    DELETE /keys/<key_id>/  → revoke key
    """
    permission_classes = [IsAuthenticatedClient, IsAuthenticatedUser]  

    def get_object(self, key_id):
        return get_object_or_404(ClientAPIKey, pk=key_id)

    def get(self, request, key_id):
        key  = self.get_object(key_id)
        data = ClientAPIKeyReadSerializer(key).data
        return Response(data)

    def delete(self, request, key_id):
        key        = self.get_object(key_id)
        serializer = RevokeAPIKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        key.revoke(reason=serializer.validated_data.get("reason", ""))
        return Response(
            {"message": f"API key '{key.name}' ({key.prefix}…) has been revoked."},
            status=status.HTTP_200_OK,
        )


class APIKeyUsageView(APIView):
    """
    GET keys/<key_id>/usage/?limit=50  → last N usage logs for a key
    """
    permission_classes = [IsAuthenticatedClient, IsAuthenticatedUser]  

    def get(self, request, key_id):
        key    = get_object_or_404(ClientAPIKey, pk=key_id)
        limit  = min(int(request.query_params.get("limit", 50)), 500)
        logs   = APIKeyUsageLog.objects.filter(api_key=key)[:limit]
        data   = APIKeyUsageLogSerializer(logs, many=True).data
        return Response({"count": len(data), "results": data})


class ClientAPIKeyUsageSummaryView(APIView):
    """
    GET /clients/<client_id>/usage-summary/
    Returns per-key stats for a client's keys.
    """
    permission_classes = [IsAuthenticatedClient, IsAuthenticatedUser]  

    def get(self, request, client_id):
        client = get_object_or_404(ClientUserInfo, pk=client_id)
        keys   = ClientAPIKey.objects.filter(client=client)

        summary = []
        for key in keys:
            total      = APIKeyUsageLog.objects.filter(api_key=key).count()
            errors     = APIKeyUsageLog.objects.filter(api_key=key, status_code__gte=400).count()
            summary.append({
                "key_id":        key.pk,
                "name":          key.name,
                "prefix":        key.prefix,
                "is_valid":      key.is_valid,
                "last_used_at":  key.last_used_at,
                "total_requests": total,
                "error_requests": errors,
                "success_rate":  round((1 - errors / total) * 100, 1) if total else None,
            })

        return Response({"client": client.client_name, "keys": summary})

