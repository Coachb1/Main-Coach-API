import ipaddress
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone

from client_apis.models import ClientAPIKey


class APIKeyAuthentication(BaseAuthentication):
    """
    DRF authenticator.

    Clients send:
        Authorization: Api-Key sk-xxxxxxxxxxxxxxxxxxxxxxxx

    On success, sets:
        request.user         → the ClientUserInfo instance
        request.auth         → the ClientAPIKey instance
    """

    KEYWORD = "Api-Key"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "").strip()

        if not auth_header:
            return None  # Let other authenticators try

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.KEYWORD:
            return None  # Not our scheme — pass through

        raw_key = parts[1]

        api_key = ClientAPIKey.get_from_raw_key(raw_key)

        if api_key is None:
            raise AuthenticationFailed("Invalid API key.")

        if not api_key.is_active:
            raise AuthenticationFailed("This API key has been revoked.")

        if api_key.is_expired:
            raise AuthenticationFailed("This API key has expired.")

        if api_key.revoked_at:
            raise AuthenticationFailed(f"Key revoked: {api_key.revoke_reason or 'No reason given'}.")

        # Optional: IP allowlist check
        if api_key.allowed_ips:
            client_ip = _get_client_ip(request)
            if not _ip_is_allowed(client_ip, api_key.allowed_ips):
                raise AuthenticationFailed(f"IP {client_ip} is not authorised for this key.")

        # Touch last_used_at (non-blocking; swap to Celery task in production)
        api_key.touch()

        # Attach key to request so views/throttles can read it
        request._request.api_key = api_key
        # Return (user, auth) — user = client record, auth = key record
        return (api_key.client, api_key)

    def authenticate_header(self, request):
        return self.KEYWORD


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _ip_is_allowed(client_ip: str, allowed_list: list) -> bool:
    try:
        client_addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in allowed_list:
        try:
            if "/" in entry:
                if client_addr in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if client_addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue

    return False