import time
import json
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("client_apis.usage")


class APIKeyUsageLogMiddleware(MiddlewareMixin):
    """
    Logs every request that was authenticated via an API key.
    Runs AFTER DRF authentication (i.e. after the view is called).

    Add to MIDDLEWARE after SecurityMiddleware but BEFORE SessionMiddleware:
        "client_apis.middleware.APIKeyUsageLogMiddleware",

    For high-traffic APIs, replace the .create() call with a Celery task.
    """

    def process_request(self, request):
        request._api_log_start = time.time()

    def process_response(self, request, response):
        # Only log if an API key was used
        api_key = getattr(request, "api_key", None)
        print('api_key in middleware:', api_key, request)
        if api_key is None:
            return response

        elapsed_ms = int((time.time() - getattr(request, "_api_log_start", time.time())) * 1000)

        # Safely read body (already consumed by DRF)
        request_body = None
        try:
            if request.content_type == "application/json" and request.body:
                request_body = json.loads(request.body)
        except Exception:
            pass

        error_message = ""
        if response.status_code >= 400:
            try:
                error_message = response.content.decode()[:500]
            except Exception:
                pass

        try:
            _create_log(
                api_key=api_key,
                client=api_key.client,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                ip_address=_get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                request_body=request_body,
                response_ms=elapsed_ms,
                error_message=error_message,
            )
        except Exception as exc:
            logger.error("Failed to write APIKeyUsageLog: %s", exc)

        return response


def _create_log(**kwargs):
    """Import here to avoid circular imports at module load time."""
    from client_apis.models import APIKeyUsageLog
    APIKeyUsageLog.objects.create(**kwargs)


def _get_client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")