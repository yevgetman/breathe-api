"""
JASPR Weather combined API view.
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.core.utils import validate_coordinates
from .orchestrator import JasprOrchestrator
from .serializers import JasprResponseSerializer

logger = logging.getLogger(__name__)


class JasprWeatherView(APIView):
    """
    Combined weather + air quality + pollen endpoint for JASPR Weather iOS app.

    Returns current conditions, 48-hour hourly forecast, daily forecast,
    pollen data, and optionally historical AQI comparisons — all in one call.

    GET /api/v1/jaspr/?lat=34.05&lon=-118.24&units=imperial&include_historical=true
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator = JasprOrchestrator()

    def get(self, request):
        """
        Query parameters:
        - lat (required): Latitude
        - lon (required): Longitude
        - units (optional): 'metric' or 'imperial' (default: imperial)
        - include_historical (optional): Include 30-day AQI history (default: false)
        - no_cache (optional): Skip cache (default: false)
        """
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')

        if not lat or not lon:
            return Response(
                {'error': 'Missing required parameters: lat and lon'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid coordinate format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_valid, error_message = validate_coordinates(lat, lon)
        if not is_valid:
            return Response(
                {'error': error_message},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.conf import settings as django_settings
        default_units = django_settings.WEATHER_SETTINGS.get('DEFAULT_UNITS', 'imperial')
        units = request.query_params.get('units', default_units).lower()
        if units not in ('metric', 'imperial'):
            return Response(
                {'error': "units must be 'metric' or 'imperial'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        include_historical = request.query_params.get('include_historical', 'false').lower() == 'true'
        no_cache = request.query_params.get('no_cache', 'false').lower() == 'true'

        try:
            result = self.orchestrator.get_jaspr_data(
                lat=lat,
                lon=lon,
                units=units,
                include_historical=include_historical,
                use_cache=not no_cache,
            )

            serializer = JasprResponseSerializer(data=result)
            if serializer.is_valid():
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                logger.warning(f"JASPR serializer errors: {serializer.errors}")
                return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in JASPR endpoint: {e}", exc_info=True)
            is_staff = getattr(getattr(request, 'user', None), 'is_staff', False)
            return Response(
                {
                    'error': 'Internal server error',
                    'detail': str(e) if is_staff else 'Unable to fetch JASPR data'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
