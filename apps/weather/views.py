"""
Weather API views.
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.core.utils import validate_coordinates
from .orchestrator import WeatherOrchestrator
from .serializers import WeatherResponseSerializer

logger = logging.getLogger(__name__)


class WeatherView(APIView):
    """
    Get current weather and 10-day daily forecast.

    GET /api/v1/weather/?lat=34.05&lon=-118.24&units=metric
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator = WeatherOrchestrator()

    def get(self, request):
        """
        Query parameters:
        - lat (required): Latitude
        - lon (required): Longitude
        - units (optional): 'metric' (default) or 'imperial'
        - no_cache (optional): Skip cache (true/false)
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

        no_cache = request.query_params.get('no_cache', 'false').lower() == 'true'

        try:
            result = self.orchestrator.get_weather(
                lat=lat,
                lon=lon,
                units=units,
                use_cache=not no_cache,
            )

            serializer = WeatherResponseSerializer(data=result)
            if serializer.is_valid():
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching weather data: {e}", exc_info=True)
            is_staff = getattr(getattr(request, 'user', None), 'is_staff', False)
            return Response(
                {
                    'error': 'Internal server error',
                    'detail': str(e) if is_staff else 'Unable to fetch weather data'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
