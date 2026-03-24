"""
API key authentication for the Breathe API.

Usage:
  - Clients pass their key via the X-API-Key header.
  - Views that should be public override with: permission_classes = [AllowAny]
"""
import logging

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)

API_KEY_HEADER = 'HTTP_X_API_KEY'


class APIKeyAuthentication(BaseAuthentication):
    """
    Authenticate requests via X-API-Key header.

    - If the header is present and valid → sets request.auth to the APIKey instance.
    - If the header is present but invalid → raises 401.
    - If the header is absent → returns None (falls through to permission check).
    """

    def authenticate(self, request):
        key = request.META.get(API_KEY_HEADER)
        if not key:
            return None

        from apps.core.models import APIKey

        try:
            api_key = APIKey.objects.get(key=key, is_active=True)
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid or revoked API key.')

        return (None, api_key)

    def authenticate_header(self, request):
        return 'X-API-Key'


class HasValidAPIKey(BasePermission):
    """
    Permission that requires a valid API key.

    Passes if the request was authenticated with an APIKey
    (i.e., request.auth is an APIKey instance).
    """

    message = 'A valid API key is required. Pass it via the X-API-Key header.'

    def has_permission(self, request, view):
        from apps.core.models import APIKey
        return isinstance(request.auth, APIKey)
