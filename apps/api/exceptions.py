"""
Custom exception handlers for API.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    Logs errors and provides consistent error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Log the exception
    logger.error(
        f"API Exception: {exc}",
        exc_info=True,
        extra={'context': context}
    )
    
    # If DRF didn't handle it, create custom response
    if response is None:
        request = context.get('request')
        is_staff = getattr(getattr(request, 'user', None), 'is_staff', False)
        return Response(
            {
                'error': 'Internal server error',
                'detail': str(exc) if is_staff else 'An error occurred'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Customize error response format
    if isinstance(response.data, dict):
        error_data = {
            'error': response.data.get('detail', 'Error'),
            'code': response.status_code
        }
        response.data = error_data
    
    return response
