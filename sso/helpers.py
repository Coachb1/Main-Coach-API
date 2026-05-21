import logging
import httpx
import jwt
from typing import Dict, Optional, Any
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from sso.models import UserIdentityProvider

logger = logging.getLogger(__name__)


class MicrosoftTeamsSSO:
    """
    Handles Microsoft Teams SSO verification and token exchange.
    
    Flow:
    1. Verify bootstrap token signature using Microsoft's JWKS
    2. Exchange bootstrap token for ID token via OBO flow
    3. Extract user claims from ID token
    4. Create or lookup user record
    """
    
    MICROSOFT_JWKS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
    MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    def __init__(self):
        self.client_id = getattr(settings, 'MICROSOFT_CLIENT_ID')
        self.client_secret = getattr(settings, 'MICROSOFT_CLIENT_SECRET')
        self.tenant_id = getattr(settings, 'MICROSOFT_TENANT_ID', 'common')
        
        if not self.client_id or not self.client_secret:
            raise ValueError("MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET must be set in settings")
    
    def verify_bootstrap_token(self, token: str) -> Dict[str, Any]:
        """
        Verify the bootstrap token signature and extract claims.
        
        Args:
            token: The bootstrap token from Teams client
            
        Returns:
            Dictionary of decoded claims
            
        Raises:
            AuthenticationFailed: If token is invalid or verification fails
        """
        try:
            # Decode without verification first to get the header
            unverified = jwt.decode(token, options={"verify_signature": False})
            header = jwt.get_unverified_header(token)
            
            logger.debug(f"Bootstrap token header: {header}")
            
            # Fetch Microsoft's JWKS
            jwks = self._fetch_jwks()
            
            # Find the key matching the token's kid
            kid = header.get('kid')
            key = self._find_key_in_jwks(jwks, kid)
            
            if not key:
                logger.error(f"Could not find key with kid: {kid}")
                raise AuthenticationFailed("Invalid token: key not found")
            
            # Convert JWKS key to PEM format
            public_key = self._jwks_key_to_pem(key)
            
            # Verify token signature
            claims = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=self.client_id,
                options={"verify_aud": True}
            )
            
            logger.info(f"Successfully verified bootstrap token for user: {claims.get('preferred_username')}")
            return claims
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise AuthenticationFailed("Token has expired")
        except jwt.InvalidSignatureError:
            logger.error("Invalid token signature")
            raise AuthenticationFailed("Invalid token signature")
        except jwt.InvalidTokenError as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise AuthenticationFailed(f"Token verification failed: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error during token verification: {e}")
            raise AuthenticationFailed("Token verification failed")
    
    def exchange_token_obo(self, bootstrap_token: str, user_email: str) -> Dict[str, Any]:
        """
        Exchange bootstrap token for ID token using On-Behalf-Of flow.
        
        Args:
            bootstrap_token: The bootstrap token from Teams
            user_email: The user's email (for logging)
            
        Returns:
            Dictionary containing 'id_token'
            
        Raises:
            AuthenticationFailed: If exchange fails
        """
        try:
            token_url = self.MICROSOFT_TOKEN_URL.format(tenant_id=self.tenant_id)
            
            payload = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'assertion': bootstrap_token,
                'requested_token_use': 'on_behalf_of',
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'scope': 'https://graph.microsoft.com/.default'
            }
            
            logger.debug(f"Initiating OBO flow for user: {user_email}")
            
            with httpx.Client() as client:
                response = client.post(token_url, data=payload, timeout=10.0)
            
            if response.status_code != 200:
                error_text = response.text[:200]  # Truncate for security
                logger.error(f"OBO token exchange failed: {response.status_code} - {error_text}")
                raise AuthenticationFailed("Token exchange failed")
            
            token_response = response.json()
            
            if 'id_token' not in token_response:
                logger.error("No id_token in OBO response")
                raise AuthenticationFailed("Token exchange failed")
            
            logger.info(f"Successfully exchanged token for user: {user_email}")
            return token_response
            
        except httpx.RequestError as e:
            logger.exception(f"Network error during OBO exchange: {e}")
            raise AuthenticationFailed("Token exchange network error")
        except Exception as e:
            logger.exception(f"Unexpected error during OBO exchange: {e}")
            raise AuthenticationFailed("Token exchange failed")
    
    def extract_user_claims(self, id_token: str) -> Dict[str, Any]:
        """
        Extract user claims from ID token without verification.
        
        Args:
            id_token: The ID token from OBO exchange
            
        Returns:
            Dictionary of user claims
        """
        try:
            claims = jwt.decode(id_token, options={"verify_signature": False})
            return claims
        except Exception as e:
            logger.exception(f"Error extracting claims from ID token: {e}")
            raise AuthenticationFailed("Failed to extract user claims")
    
    def _fetch_jwks(self) -> Dict:
        """Fetch Microsoft's public keys (JWKS)."""
        try:
            with httpx.Client() as client:
                response = client.get(self.MICROSOFT_JWKS_URL, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.exception(f"Error fetching JWKS from Microsoft: {e}")
            raise AuthenticationFailed("Failed to fetch verification keys")
    
    def _find_key_in_jwks(self, jwks: Dict, kid: str) -> Optional[Dict]:
        """Find a key in JWKS by kid."""
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                return key
        return None
    
    def _jwks_key_to_pem(self, key: Dict) -> str:
        """Convert JWKS key to PEM format for JWT verification."""
        try:
            from jwt.algorithms import RSAAlgorithm
            
            # Use PyJWT's built-in method to convert JWKS to PEM
            return RSAAlgorithm.from_jwk(key)
        except Exception as e:
            logger.exception(f"Error converting JWKS key to PEM: {e}")
            raise AuthenticationFailed("Key conversion failed")


def get_or_create_identity_provider(user, provider: str, provider_id: str, 
                                    tid: Optional[str], email: str,
                                    raw_claims: Dict) -> 'UserIdentityProvider':
    """
    Get or create a UserIdentityProvider record.
    
    Args:
        user: The User object
        provider: Provider name (e.g., 'microsoft')
        provider_id: Stable ID from provider (e.g., oid)
        tid: Multi-tenant ID (e.g., tid)
        email: User's email
        raw_claims: Full decoded claims
        
    Returns:
        UserIdentityProvider instance
    """
    from sso.models import UserIdentityProvider
    
    identity_provider, created = UserIdentityProvider.objects.get_or_create(
        tenant_id=user.tenant_id,
        provider=provider,
        provider_id=provider_id,
        defaults={
            'user': user,
            'tid': tid,
            'email': email,
            'raw_claims': raw_claims,
        }
    )
    
    if not created:
        # Update last login and other fields
        identity_provider.user = user
        identity_provider.email = email
        identity_provider.raw_claims = raw_claims
        identity_provider.update_last_login()
        logger.info(f"Updated existing identity provider for user: {user.uid}")
    else:
        logger.info(f"Created new identity provider for user: {user.uid}")
    
    return identity_provider


def resolve_or_create_user_from_sso(tenant, provider_claims: Dict, provider: str = 'microsoft',
                                    identity_context_kwargs: Optional[Dict] = None) -> tuple:
    """
    Resolve or create a user from SSO provider claims.
    
    Tries to match by (provider, provider_id) first, then falls back to email.
    
    Args:
        tenant: Tenant object
        provider_claims: Claims extracted from provider's ID token
        provider: Provider name ('microsoft', 'google', etc.)
        identity_context_kwargs: Additional kwargs for identity context if creating new user
        
    Returns:
        Tuple of (user, is_new_user, identity_provider)
        
    Raises:
        AuthenticationFailed: If user resolution fails
    """
    from sso.models import UserIdentityProvider
    from users.models import User
    from identities.helpers import get_user_via_identity
    
    try:
        provider_id = provider_claims.get('oid')  # For Microsoft, 'oid' is the unique ID
        email = provider_claims.get('email') or provider_claims.get('preferred_username')
        tid = provider_claims.get('tid')  # For Microsoft
        display_name = provider_claims.get('name', email.split('@')[0] if email else 'SSO User')
        
        if not provider_id or not email:
            logger.error(f"Missing provider_id or email in claims: {list(provider_claims.keys())}")
            raise AuthenticationFailed("Invalid provider claims")
        
        # Try to find existing identity provider
        try:
            identity_provider = UserIdentityProvider.objects.get(
                tenant_id=tenant.uid,
                provider=provider,
                provider_id=provider_id
            )
            user = identity_provider.user
            logger.info(f"Found user via existing identity provider: {user.uid}")
            return user, False, identity_provider
        except UserIdentityProvider.DoesNotExist:
            pass
        
        # Try to find user by email
        from users.models import UserAttribute
        try:
            user_attr = UserAttribute.objects.filter(
                tenant_id=tenant.uid,
                deleted=False,
                attributes__email=email
            ).first()
            if user_attr:
                user = user_attr.user
                logger.info(f"Found user via email match: {user.uid}")
                identity_provider = get_or_create_identity_provider(
                    user, provider, provider_id, tid, email, provider_claims
                )
                return user, False, identity_provider
        except Exception as e:
            logger.debug(f"Error searching by email: {e}")
        
        # No existing user found - create new one
        from users.helpers import create_user_acc
        from identities.helpers import create_identity
        
        logger.info(f"Creating new user from SSO for email: {email}")
        
        user = create_user_acc(
            tenant=tenant,
            identity_type='deepchat_unique_id',
            identity_value=email
        )
        
        # Update user name from provider claims
        if display_name:
            user.name = display_name
            user.save(update_fields=['name'])
        
        identity_provider = get_or_create_identity_provider(
            user, provider, provider_id, tid, email, provider_claims
        )
        
        logger.info(f"Created new user from SSO: {user.uid}")
        return user, True, identity_provider
        
    except AuthenticationFailed:
        raise
    except Exception as e:
        logger.exception(f"Error resolving/creating user from SSO: {e}")
        raise AuthenticationFailed("User resolution failed")
