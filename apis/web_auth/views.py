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
    """
    A class that handles web authentication functionalities.

    Methods:
    - login_view: Handles the login functionality.
    - logout_view: Handles the logout functionality.
    - get_access_token_frontend: Handles the token refresh functionality.
    """

    @action(methods=["POST"], detail=False, url_path="login")
    def login_view(self, request, *args, **kwargs):
        """
        Handles the login functionality.

        Validates the login data, retrieves the user's subdomain prefix, identity type, identity value, and password,
        and calls the login_user function to generate new tokens for the user.

        Args:
        - request: The HTTP request object.
        - args: Additional positional arguments.
        - kwargs: Additional keyword arguments.

        Returns:
        - Response: The HTTP response object with the generated tokens.
        """
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
        """
        Handles the logout functionality.

        Logs out the user.

        Args:
        - request: The HTTP request object.
        - args: Additional positional arguments.
        - kwargs: Additional keyword arguments.

        Returns:
        - Response: The HTTP response object with status code 204.
        """
        user = request.user
        logout_user(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=False, url_path="refresh")
    def get_access_token_frontend(self, request, *args, **kwargs):
        """
        Handles the token refresh functionality.

        Validates the refresh token and calls the get_new_access_token function to generate a new access token.

        Args:
        - request: The HTTP request object.
        - args: Additional positional arguments.
        - kwargs: Additional keyword arguments.

        Returns:
        - Response: The HTTP response object with the new access token.
        """
        serializer = FrontendAccessTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data['refresh_token']
        access_token = get_new_access_token(refresh_token)

        data = {'access_token': access_token}

        return Response(data=data, status=status.HTTP_200_OK)
