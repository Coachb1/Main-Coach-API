from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apis.web_auth.serializers import LoginSerializer, PasswordResetSerializer
from commons.viewset import ApiViewSet
from tenants.helpers import tenant_from_subdomain_prefix
from users.helpers import login_user, logout_user, update_user_account, reset_password_with_secret_code
from apis.frontend_api.serializers import FrontendAccessTokenSerializer
from users.models import User
from web_auth.helpers import get_new_access_token
import logging

logger = logging.getLogger(__name__)

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
        client_id = serializer.validated_data.get("client_id")

        identity_type = identity_context["identity_type"]
        identity_value = identity_context["value"]

        tokens = login_user(
            tenant=tenant_from_subdomain_prefix(subdomain_prefix),
            identity_type=identity_type,
            identity_value=identity_value,
            password=password,
            client_id=client_id
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

    @action(methods=["POST"], detail=False, url_path="reset-password-secret")
    def reset_password_with_secret_code_view(self, request, *args, **kwargs):
        """
        Handles password reset using secret code.
        
        Validates the reset password data and calls the reset_password_with_secret_code function
        to reset the user's password using the secret code.
        
        Args:
        - request: The HTTP request object with user_id, secret_code, and new_password.
        - args: Additional positional arguments.
        - kwargs: Additional keyword arguments.
        
        Returns:
        - Response: The HTTP response object with success or error message.
        """
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        
        secret_code = serializer.validated_data["secret_code"]
        new_password = serializer.validated_data["new_password"]

        subdomain_prefix = serializer.validated_data["subdomain_prefix"]
        identity_context = serializer.validated_data["identity_context"]

        identity_type = identity_context["identity_type"]
        identity_value = identity_context["value"]
        
        try:
            result = reset_password_with_secret_code(
                tenant=tenant_from_subdomain_prefix(subdomain_prefix),
                identity_type=identity_type,
                identity_value=identity_value,
                secret_code=secret_code,
                new_password=new_password
            )
            return Response(data=result, status=status.HTTP_200_OK)
        except ValueError as e:
            logger.error(f"Password reset failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Unexpected error during password reset: {e}")
            return Response({"error": "An error occurred during password reset"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(methods=["POST"], detail=False, url_path="reset-password")
    def reset_password_view(self, request, *args, **kwargs):
        user = request.auth_user
        if not user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        data = {}
        if request.data.get('password'):
            data['password'] = request.data.get('password')
        if request.data.get('name'):
            data['name'] = request.data.get('name')

        update_user_account(user.tenant_id, user.uid, data)
        return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)
