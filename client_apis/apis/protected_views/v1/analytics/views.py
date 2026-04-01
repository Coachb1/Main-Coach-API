from client_apis.apis.authentication import APIKeyAuthentication
from client_apis.apis.permissions import HasValidAPIKey, IsActiveClient
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from commons.throttling import APIKeyRateThrottle

class ExampleProtectedView(APIView):
    """
    Example view that external clients hit using their API key.
    Replace this with your actual views.

    Usage:
        GET /api/v1/data/
        Authorization: Api-Key sk-xxxxxx...
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes     = [HasValidAPIKey, IsActiveClient]
    throttle_classes       = [APIKeyRateThrottle]

    def get(self, request):
        client  = request.user    # ClientUserInfo instance
        api_key = request.auth    # ClientAPIKey instance

        return Response({
            "message":    "Authenticated via API key.",
            "client":     client.client_name,
            "key_name":   api_key.name,
            "key_prefix": api_key.prefix,
            "rate_limit": f"{api_key.requests_per_minute} req/min",
        }, status=status.HTTP_200_OK)