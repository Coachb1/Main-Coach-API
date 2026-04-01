import time
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle
from rest_framework.exceptions import Throttled


class APIKeyRateThrottle(BaseThrottle):
    """
    Sliding-window rate limiter keyed to the ClientAPIKey.
    Reads `requests_per_minute` from the key's tier configuration.

    Falls back gracefully if no API key is present (i.e. when a different
    authenticator is used on the same view).
    """

    def get_cache_key(self, request, view):
        api_key = getattr(request, "auth", None)
        if api_key is None:
            return None  # Not an API-key request — skip throttle
        return f"ratelimit:apikey:{api_key.pk}"

    def allow_request(self, request, view):
        api_key = getattr(request, "auth", None)
        if api_key is None:
            return True  # Not our concern

        limit    = api_key.requests_per_minute
        window   = 60  # seconds
        now      = time.time()
        cache_key = f"ratelimit:apikey:{api_key.pk}"

        # Fetch existing timestamps list
        history: list = cache.get(cache_key, [])

        # Drop timestamps outside the window
        history = [t for t in history if now - t < window]

        self.num_requests = limit
        self.duration     = window
        self.wait_time    = None

        if len(history) >= limit:
            # Compute how long until the oldest request falls outside the window
            self.wait_time = window - (now - history[0])
            return False

        history.append(now)
        cache.set(cache_key, history, timeout=window)
        return True

    def wait(self):
        return self.wait_time


class APIKeyBurstThrottle(BaseThrottle):
    """
    Short burst guard — max 20 requests per 5 seconds regardless of tier.
    Stack this with APIKeyRateThrottle for double protection.
    """

    BURST_LIMIT  = 20
    BURST_WINDOW = 5  # seconds

    def allow_request(self, request, view):
        api_key = getattr(request, "auth", None)
        if api_key is None:
            return True

        now       = time.time()
        cache_key = f"burst:apikey:{api_key.pk}"
        history   = cache.get(cache_key, [])
        history   = [t for t in history if now - t < self.BURST_WINDOW]

        if len(history) >= self.BURST_LIMIT:
            self.wait_time = self.BURST_WINDOW - (now - history[0])
            return False

        history.append(now)
        cache.set(cache_key, history, timeout=self.BURST_WINDOW)
        return True

    def wait(self):
        return getattr(self, "wait_time", None)