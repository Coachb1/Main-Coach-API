from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apis.web_auth.serializers import LoginSerializer
from commons.viewset import ApiViewSet
from tenants.helpers import tenant_from_subdomain_prefix
from users.helpers import login_user, logout_user
from apis.frontend_api.serializers import FrontendAccessTokenSerializer
from web_auth.helpers import get_new_access_token


class WebAuthViewSet(ApiViewSet):

    @action(methods=["POST"], detail=False, url_path="login")
    def login_view(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subdomain_prefix = serializer.validated_data["subdomain_prefix"]
        identity_context = serializer.validated_data["identity_context"]
        password = serializer.validated_data["password"]

        identity_type = identity_context["identity_type"]
        identity_value = identity_context["value"]

        tokens = login_user(
            tenant=tenant_from_subdomain_prefix(subdomain_prefix),
            identity_type=identity_type,
            identity_value=identity_value,
            password=password
        )

        return Response(data=tokens, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=False, url_path="logout")
    def logout_view(self, request, *args, **kwargs):
        user = request.user
        logout_user(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["GET"], detail=False, url_path="refresh")
    def get_access_token_frontend(self, request, *args, **kwargs):
        serializer = FrontendAccessTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data['refresh_token']
        access_token = get_new_access_token(refresh_token)

        data = {'access_token': access_token}

        return Response(data=data, status=status.HTTP_200_OK)
