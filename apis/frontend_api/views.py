from rest_framework import status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

# from apis.web_auth.serializers import LoginSerializer
from commons.viewset import ApiViewSet
from tenants.helpers import tenant_from_subdomain_prefix
from .serializers import FrontendAuthSerializer, FrontendAccessTokenSerializer
from web_auth.helpers import create_new_tokens, get_new_access_token
from settings import FRONTEND_BASE_URL


class FrontendAuthViewSet(ApiViewSet):

    @action(methods=["GET"], detail=False, url_path="get-report-url")
    def get_report_url(self, request, *args, **kwargs):
        serializer = FrontendAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        report_type = serializer.validated_data["report_type"]

        tokens = create_new_tokens('user-report', 'uid', user_id)

        refresh_token = tokens["refresh"]

        url = f"{FRONTEND_BASE_URL}/{report_type}/{refresh_token}"

        data = {
            "url": url,
        }

        return Response(data=data, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="get-access-token-frontend")
    def get_access_token_frontend(self, request, *args, **kwargs):
        serializer = FrontendAccessTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data['refresh_token']
        access_token = get_new_access_token(refresh_token)

        data = {'access_token': access_token}

        return Response(data=data, status=status.HTTP_200_OK)
