"""
Public (no-auth) API views for the demo page.

These mirror the main air-quality and weather endpoints but require no API key.
They exist so the interactive demo at /demo/ keeps working without embedding
a secret key in client-side HTML.
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from apps.core.utils import validate_coordinates
from .orchestrator import AirQualityOrchestrator
from .serializers import AirQualityResponseSerializer
from apps.weather.orchestrator import WeatherOrchestrator
from apps.weather.serializers import WeatherResponseSerializer

logger = logging.getLogger(__name__)


class PublicAirQualityView(APIView):
    """
    Public air quality endpoint for the demo page.
    Same as /api/v1/air-quality/ but requires no API key.

    GET /api/v1/public/air-quality/?lat=34.05&lon=-118.24
    """
    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator = AirQualityOrchestrator()

    def get(self, request):
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

        include_forecast = request.query_params.get('include_forecast', 'false').lower() == 'true'
        radius_km_str = request.query_params.get('radius_km', '25')
        try:
            radius_km = float(radius_km_str)
            if radius_km <= 0:
                return Response({'error': 'radius_km must be a positive number'}, status=status.HTTP_400_BAD_REQUEST)
            radius_km = min(radius_km, 100)
        except (TypeError, ValueError):
            return Response({'error': 'radius_km must be a valid number'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = self.orchestrator.get_air_quality(
                lat=lat, lon=lon,
                include_forecast=include_forecast,
                radius_km=radius_km,
            )
            serializer = AirQualityResponseSerializer(data=result)
            if serializer.is_valid():
                return Response(serializer.data)
            return Response(result)
        except Exception as e:
            logger.error(f"Public AQ endpoint error: {e}", exc_info=True)
            return Response({'error': 'Unable to fetch air quality data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicWeatherView(APIView):
    """
    Public weather endpoint for the demo page.
    Same as /api/v1/weather/ but requires no API key.

    GET /api/v1/public/weather/?lat=34.05&lon=-118.24&units=imperial
    """
    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator = WeatherOrchestrator()

    def get(self, request):
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
            return Response({'error': "units must be 'metric' or 'imperial'"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = self.orchestrator.get_weather(lat=lat, lon=lon, units=units)
            serializer = WeatherResponseSerializer(data=result)
            if serializer.is_valid():
                return Response(serializer.data)
            return Response(result)
        except Exception as e:
            logger.error(f"Public weather endpoint error: {e}", exc_info=True)
            return Response({'error': 'Unable to fetch weather data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
