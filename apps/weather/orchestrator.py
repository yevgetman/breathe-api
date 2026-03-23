"""
Weather orchestrator with primary/fallback provider pattern.
"""
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from apps.adapters.open_meteo import OpenMeteoWeatherAdapter
from apps.adapters.openweathermap_weather import OWMWeatherAdapter
from apps.location.services import LocationService

from .models import WeatherObservation, DailyForecast
from .utils import convert_current_to_imperial, convert_forecast_to_imperial

logger = logging.getLogger(__name__)


class WeatherOrchestrator:
    """
    Coordinates weather data fetching with primary/fallback strategy.

    1. Check DB cache
    2. Try primary adapter (Open-Meteo)
    3. If primary fails, try fallback adapter (OpenWeatherMap)
    4. Cache result and return
    """

    def __init__(self):
        self.primary = OpenMeteoWeatherAdapter()
        self.fallback = OWMWeatherAdapter()
        self.location_service = LocationService()
        self.settings = settings.WEATHER_SETTINGS
        from apps.core.cache import ResponseCache
        precision = getattr(settings, 'CACHE_SETTINGS', {}).get('GEOHASH_PRECISION', 6)
        self._cache = ResponseCache(
            namespace='wx',
            default_ttl=self.settings.get('CURRENT_CACHE_TTL', 300),
            geohash_precision=precision,
        )

    def get_weather(
        self,
        lat: float,
        lon: float,
        units: str = 'metric',
        use_cache: bool = True,
    ) -> Dict:
        """
        Get current weather and 10-day forecast for coordinates.

        Args:
            lat: Latitude
            lon: Longitude
            units: 'metric' or 'imperial'
            use_cache: Whether to use cached data

        Returns:
            Complete weather response dict
        """
        # Resolve location
        location_info = self.location_service.reverse_geocode(lat, lon, use_cache=use_cache)

        # Check cache
        if use_cache:
            cached = self._get_from_cache(lat, lon)
            if cached:
                if units == 'imperial':
                    cached['current'] = convert_current_to_imperial(cached['current'])
                    cached['daily_forecast'] = convert_forecast_to_imperial(cached['daily_forecast'])
                    cached['units'] = 'imperial'
                cached['location'] = location_info
                return cached

        # Fetch from providers (primary then fallback)
        forecast_days = self.settings.get('FORECAST_DAYS', 10)
        result = None

        if self.primary.is_available():
            try:
                result = self.primary.fetch_current(lat, lon, forecast_days=forecast_days)
            except Exception as e:
                logger.error(f"Primary weather adapter failed: {e}")

        if result is None and self.fallback.is_available():
            try:
                result = self.fallback.fetch_current(lat, lon)
            except Exception as e:
                logger.error(f"Fallback weather adapter failed: {e}")

        if result is None:
            return self._get_unavailable_response(lat, lon, location_info, units)

        # Cache the result (always in metric)
        self._save_to_cache(lat, lon, result)

        # Build response
        response = {
            'location': location_info,
            'current': result['current'],
            'daily_forecast': result.get('daily_forecast', []),
            'source': result['source'],
            'units': 'metric',
        }

        # Convert if imperial requested
        if units == 'imperial':
            response['current'] = convert_current_to_imperial(response['current'])
            response['daily_forecast'] = convert_forecast_to_imperial(response['daily_forecast'])
            response['units'] = 'imperial'

        return response

    def _get_from_cache(self, lat: float, lon: float) -> Optional[Dict]:
        """Get weather data from Redis cache (geohash-based key)."""
        return self._cache.get(lat, lon)

    def _save_to_cache(self, lat: float, lon: float, result: Dict):
        """Save weather data to Redis cache, with optional DB write-through."""
        self._cache.set(lat, lon, result)

        if getattr(settings, 'CACHE_SETTINGS', {}).get('WRITE_THROUGH_TO_DB', False):
            self._write_through_to_db(lat, lon, result)

    def _write_through_to_db(self, lat: float, lon: float, result: Dict):
        """Write weather data to DB models for analytics (non-fatal)."""
        try:
            lat_r = round(Decimal(str(lat)), 3)
            lon_r = round(Decimal(str(lon)), 3)
            now = timezone.now()
            current_ttl = timedelta(seconds=self.settings.get('CURRENT_CACHE_TTL', 300))
            forecast_ttl = timedelta(seconds=self.settings.get('FORECAST_CACHE_TTL', 1800))
            current = result.get('current', {})
            source = result.get('source', 'UNKNOWN')

            obs_time = current.get('observation_time')
            if isinstance(obs_time, str):
                from datetime import datetime as dt
                try:
                    obs_time = dt.fromisoformat(obs_time.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    obs_time = now
            obs_time = obs_time or now

            sunrise = self._parse_datetime(current.get('sunrise'))
            sunset = self._parse_datetime(current.get('sunset'))

            WeatherObservation.objects.update_or_create(
                lat=lat_r, lon=lon_r, source=source,
                defaults={
                    'observation_time': obs_time,
                    'temperature': current.get('temperature'),
                    'feels_like': current.get('feels_like'),
                    'dew_point': current.get('dew_point'),
                    'humidity': current.get('humidity'),
                    'pressure': current.get('pressure'),
                    'visibility': current.get('visibility'),
                    'cloud_cover': current.get('cloud_cover'),
                    'uv_index': current.get('uv_index'),
                    'wind_speed': current.get('wind_speed'),
                    'wind_direction': current.get('wind_direction'),
                    'wind_gusts': current.get('wind_gusts'),
                    'weather_description': current.get('weather_description', ''),
                    'weather_icon': current.get('weather_icon', ''),
                    'sunrise': sunrise,
                    'sunset': sunset,
                    'cached_until': now + current_ttl,
                }
            )

            for day in result.get('daily_forecast', []):
                DailyForecast.objects.update_or_create(
                    lat=lat_r, lon=lon_r, source=source,
                    forecast_date=day['date'],
                    defaults={
                        'temp_high': day.get('temp_high'),
                        'temp_low': day.get('temp_low'),
                        'feels_like_high': day.get('feels_like_high'),
                        'feels_like_low': day.get('feels_like_low'),
                        'weather_code': day.get('weather_code'),
                        'weather_description': day.get('weather_description', ''),
                        'weather_icon': day.get('weather_icon', ''),
                        'precipitation_sum': day.get('precipitation_sum'),
                        'precipitation_probability': day.get('precipitation_probability'),
                        'wind_speed_max': day.get('wind_speed_max'),
                        'wind_gusts_max': day.get('wind_gusts_max'),
                        'wind_direction_dominant': day.get('wind_direction_dominant'),
                        'uv_index_max': day.get('uv_index_max'),
                        'sunrise': self._parse_datetime(day.get('sunrise')),
                        'sunset': self._parse_datetime(day.get('sunset')),
                        'cached_until': now + forecast_ttl,
                    }
                )
        except Exception as e:
            logger.warning(f"Weather DB write-through failed (non-fatal): {e}")

    @staticmethod
    def _parse_datetime(value):
        """Parse a datetime string or return None."""
        if value is None:
            return None
        if hasattr(value, 'isoformat'):
            return value  # already a datetime
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(str(value).replace('Z', '+00:00'))
            from django.utils import timezone as tz
            if not tz.is_aware(parsed):
                parsed = tz.make_aware(parsed)
            return parsed
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _get_unavailable_response(lat, lon, location_info, units):
        """Return a response indicating weather data is unavailable."""
        return {
            'location': location_info,
            'current': None,
            'daily_forecast': [],
            'source': None,
            'units': units,
            'error': 'Weather data unavailable for this location',
        }
