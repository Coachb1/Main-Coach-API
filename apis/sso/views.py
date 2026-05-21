import logging
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed

from apis.sso.serializers import TeamsSSOTokenSerializer, TeamsSSOResponseSerializer
from commons.viewset import ApiViewSet
from tenants.helpers import tenant_from_subdomain_prefix
from sso.helpers import MicrosoftTeamsSSO, resolve_or_create_user_from_sso
from web_auth.helpers import create_new_tokens
from users.models import UserAttribute

logger = logging.getLogger(__name__)


class TeamsSSOViewSet(ApiViewSet):
    """
    Handles Microsoft Teams SSO authentication.
    
    Endpoints:
    - POST /api/v1/sso/teams/exchange/ : Exchange Teams bootstrap token for JWT
    """
    
    @action(methods=["POST"], detail=False, url_path="exchange", permission_classes=[])
    def teams_token_exchange(self, request, *args, **kwargs):
        """
        Exchange Teams bootstrap token for our JWT.
        
        Flow:
        1. Verify bootstrap token signature using Microsoft JWKS
        2. Exchange token via OBO flow to get ID token
        3. Extract user identity from ID token
        4. Resolve/create user record linked to provider identity
        5. Issue our own JWT
        
        Request body:
        {
            "teams_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
        }
        
        Returns:
        {
            "access_token": "...",
            "refresh_token": "..." (optional),
            "user": {
                "uid": "...",
                "name": "...",
                "email": "...",
                "role": "..."
            },
            "auth_type": "sso_login"
        }
        """
        try:
            # Validate request
            serializer = TeamsSSOTokenSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            teams_token = serializer.validated_data['teams_token']
            
            # Get tenant from subdomain
            subdomain_prefix = request.META.get('HTTP_X_SUBDOMAIN_PREFIX', 'default')
            try:
                tenant = tenant_from_subdomain_prefix(subdomain_prefix)
            except Exception as e:
                logger.error(f"Invalid tenant subdomain: {subdomain_prefix}")
                return Response(
                    {"detail": "Invalid tenant"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Teams SSO token exchange initiated for tenant: {tenant.uid}")
            
            # Initialize Microsoft SSO handler
            try:
                sso = MicrosoftTeamsSSO()
            except ValueError as e:
                logger.error(f"SSO configuration error: {str(e)}")
                return Response(
                    {"detail": "SSO not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Step 1: Verify bootstrap token
            try:
                bootstrap_claims = sso.verify_bootstrap_token(teams_token)
                logger.info(f"Bootstrap token verified for user: {bootstrap_claims.get('preferred_username')}")
            except AuthenticationFailed as e:
                logger.warning(f"Bootstrap token verification failed: {str(e)}")
                return Response(
                    {"detail": "Invalid token"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Step 2: Exchange token for ID token via OBO flow
            try:
                user_email = bootstrap_claims.get('preferred_username')
                token_response = sso.exchange_token_obo(teams_token, user_email)
                id_token = token_response['id_token']
            except AuthenticationFailed as e:
                logger.warning(f"Token exchange failed: {str(e)}")
                return Response(
                    {"detail": "Token exchange failed"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Step 3: Extract claims from ID token
            try:
                user_claims = sso.extract_user_claims(id_token)
                logger.info(f"Claims extracted for user: {user_claims.get('email')}")
            except AuthenticationFailed as e:
                logger.error(f"Claims extraction failed: {str(e)}")
                return Response(
                    {"detail": "Failed to extract user claims"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Step 4: Resolve or create user
            try:
                user, is_new_user, identity_provider = resolve_or_create_user_from_sso(
                    tenant=tenant,
                    provider_claims=user_claims,
                    provider='microsoft'
                )
            except AuthenticationFailed as e:
                logger.warning(f"User resolution failed: {str(e)}")
                return Response(
                    {"detail": str(e)},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            except Exception as e:
                logger.exception(f"Unexpected error during user resolution: {e}")
                return Response(
                    {"detail": "User resolution failed"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Step 5: Issue our JWT
            try:
                tokens = create_new_tokens(
                    entity_type="user",
                    entity_identifier_key="uid",
                    entity_identifier_value=user.uid
                )
                logger.info(f"JWT issued for user: {user.uid}")
            except Exception as e:
                logger.exception(f"Token creation failed: {e}")
                return Response(
                    {"detail": "Token generation failed"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Get user email from attributes
            user_email = user.get_email()
            
            # Build response
            response_data = {
                "access_token": tokens['access'],
                "refresh_token": tokens.get('refresh'),
                "user": {
                    "uid": str(user.uid),
                    "name": user.name or user_email.split('@')[0] if user_email else "User",
                    "email": user_email,
                    "role": user.role
                },
                "auth_type": "sso_login"
            }
            
            if is_new_user:
                response_data['is_new_user'] = True
            
            serializer = TeamsSSOResponseSerializer(response_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.exception(f"Unexpected error in Teams SSO endpoint: {e}")
            return Response(
                {"detail": "Authentication failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
