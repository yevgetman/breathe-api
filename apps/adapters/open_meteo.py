"""
Open-Meteo adapter for weather data (primary provider).
Free, no API key required, global coverage, 16-day forecast.
"""
import logging
from datetime import datetime, date as date_type
from typing import Dict, List, Optional

from django.utils import timezone

from .base import BaseAdapter
from apps.weather.astronomy import compute_moon_phase, compute_golden_hour

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes (WMO 4677)
# https://open-meteo.com/en/docs
WMO_WEATHER_CODES = {
    0:  {'description': 'Clear sky',            'icon': 'clear-day'},
    1:  {'description': 'Mainly clear',         'icon': 'clear-day'},
    2:  {'description': 'Partly cloudy',        'icon': 'partly-cloudy-day'},
    3:  {'description': 'Overcast',             'icon': 'cloudy'},
    45: {'description': 'Fog',                  'icon': 'fog'},
    48: {'description': 'Depositing rime fog',  'icon': 'fog'},
    51: {'description': 'Light drizzle',        'icon': 'drizzle'},
    53: {'description': 'Moderate drizzle',     'icon': 'drizzle'},
    55: {'description': 'Dense drizzle',        'icon': 'drizzle'},
    56: {'description': 'Light freezing drizzle', 'icon': 'sleet'},
    57: {'description': 'Dense freezing drizzle', 'icon': 'sleet'},
    61: {'description': 'Slight rain',          'icon': 'rain'},
    63: {'description': 'Moderate rain',        'icon': 'rain'},
    65: {'description': 'Heavy rain',           'icon': 'rain-heavy'},
    66: {'description': 'Light freezing rain',  'icon': 'sleet'},
    67: {'description': 'Heavy freezing rain',  'icon': 'sleet'},
    71: {'description': 'Slight snow fall',     'icon': 'snow'},
    73: {'description': 'Moderate snow fall',   'icon': 'snow'},
    75: {'description': 'Heavy snow fall',      'icon': 'snow-heavy'},
    77: {'description': 'Snow grains',          'icon': 'snow'},
    80: {'description': 'Slight rain showers',  'icon': 'rain'},
    81: {'description': 'Moderate rain showers', 'icon': 'rain'},
    82: {'description': 'Violent rain showers', 'icon': 'rain-heavy'},
    85: {'description': 'Slight snow showers',  'icon': 'snow'},
    86: {'description': 'Heavy snow showers',   'icon': 'snow-heavy'},
    95: {'description': 'Thunderstorm',         'icon': 'thunderstorm'},
    96: {'description': 'Thunderstorm with slight hail', 'icon': 'thunderstorm'},
    99: {'description': 'Thunderstorm with heavy hail',  'icon': 'thunderstorm'},
}


def _decode_weather_code(code: Optional[int], is_day: int = 1) -> Dict:
    """Convert WMO weather code to description and icon.

    Handles day/night icon variants for codes 0-2 (clear/partly cloudy).
    """
    if code is None:
        return {'description': 'Unknown', 'icon': 'unknown'}
    info = WMO_WEATHER_CODES.get(code, {'description': 'Unknown', 'icon': 'unknown'})
    icon = info['icon']
    # Swap day→night icons when is_day == 0
    if not is_day:
        night_map = {
            'clear-day': 'clear-night',
            'partly-cloudy-day': 'partly-cloudy-night',
        }
        icon = night_map.get(icon, icon)
    return {'description': info['description'], 'icon': icon}


class OpenMeteoWeatherAdapter(BaseAdapter):
    """
    Adapter for Open-Meteo weather API.
    Free, no API key, global coverage, 16-day forecast.
    """

    SOURCE_NAME = "Open-Meteo"
    SOURCE_CODE = "OPEN_METEO"
    API_BASE_URL = "https://api.open-meteo.com/v1/"
    REQUIRES_API_KEY = False

    def _add_api_key(self, params: Dict, headers: Dict):
        """No API key needed for Open-Meteo."""
        pass

    def fetch_current(self, lat: float, lon: float, **kwargs) -> Optional[Dict]:
        """
        Fetch current weather and 10-day daily forecast in a single call.

        Returns:
            Dict with 'current' and 'daily_forecast' keys, or None on error.
        """
        forecast_days = kwargs.get('forecast_days', 10)

        params = {
            'latitude': lat,
            'longitude': lon,
            'current': ','.join([
                'temperature_2m', 'relative_humidity_2m', 'apparent_temperature',
                'precipitation', 'weather_code', 'cloud_cover', 'pressure_msl',
                'surface_pressure', 'wind_speed_10m', 'wind_direction_10m',
                'wind_gusts_10m', 'is_day',
            ]),
            'hourly': ','.join([
                'temperature_2m', 'relative_humidity_2m', 'dew_point_2m',
                'apparent_temperature', 'precipitation', 'precipitation_probability',
                'rain', 'showers', 'snowfall', 'weather_code', 'cloud_cover',
                'visibility', 'wind_speed_10m', 'wind_direction_10m',
                'wind_gusts_10m', 'is_day', 'uv_index',
            ]),
            'daily': ','.join([
                'weather_code', 'temperature_2m_max', 'temperature_2m_min',
                'apparent_temperature_max', 'apparent_temperature_min',
                'sunrise', 'sunset', 'uv_index_max',
                'precipitation_sum', 'precipitation_probability_max',
                'wind_speed_10m_max', 'wind_gusts_10m_max',
                'wind_direction_10m_dominant',
            ]),
            'forecast_days': forecast_days,
            'timezone': 'auto',
        }

        raw_data = self._make_request('forecast', params=params)
        if not raw_data:
            return None

        return self._normalize(raw_data, lat, lon)

    def fetch_forecast(self, lat: float, lon: float, **kwargs) -> Optional[List[Dict]]:
        """Fetch daily forecast only."""
        result = self.fetch_current(lat, lon, **kwargs)
        if result:
            return result.get('daily_forecast', [])
        return None

    def _normalize(self, raw_data: Dict, lat: float, lon: float) -> Dict:
        """Normalize Open-Meteo response to unified weather schema."""
        current_raw = raw_data.get('current', {})
        daily_raw = raw_data.get('daily', {})
        tz_name = raw_data.get('timezone', 'UTC')

        # Parse current conditions
        current_code = current_raw.get('weather_code')
        is_day = current_raw.get('is_day', 1)
        weather_info = _decode_weather_code(current_code, is_day=is_day)

        current = {
            'temperature': current_raw.get('temperature_2m'),
            'feels_like': current_raw.get('apparent_temperature'),
            'dew_point': self._calculate_dew_point(
                current_raw.get('temperature_2m'),
                current_raw.get('relative_humidity_2m'),
            ),
            'humidity': current_raw.get('relative_humidity_2m'),
            'pressure': current_raw.get('pressure_msl'),
            'visibility': None,  # Open-Meteo current doesn't include visibility
            'cloud_cover': current_raw.get('cloud_cover'),
            'uv_index': None,  # Only in daily
            'wind_speed': current_raw.get('wind_speed_10m'),
            'wind_direction': current_raw.get('wind_direction_10m'),
            'wind_gusts': current_raw.get('wind_gusts_10m'),
            'weather_code': current_code,
            'weather_description': weather_info['description'],
            'weather_icon': weather_info['icon'],
            'sunrise': None,
            'sunset': None,
            'observation_time': current_raw.get('time'),
        }

        # Get today's sunrise/sunset and UV from daily data
        if daily_raw.get('sunrise') and len(daily_raw['sunrise']) > 0:
            current['sunrise'] = daily_raw['sunrise'][0]
        if daily_raw.get('sunset') and len(daily_raw['sunset']) > 0:
            current['sunset'] = daily_raw['sunset'][0]
        if daily_raw.get('uv_index_max') and len(daily_raw['uv_index_max']) > 0:
            current['uv_index'] = daily_raw['uv_index_max'][0]

        # Parse daily forecast
        daily_forecast = []
        dates = daily_raw.get('time', [])
        for i, date_str in enumerate(dates):
            day_code = self._safe_index(daily_raw.get('weather_code', []), i)
            day_weather = _decode_weather_code(day_code, is_day=1)
            day_sunrise = self._safe_index(daily_raw.get('sunrise', []), i)
            day_sunset = self._safe_index(daily_raw.get('sunset', []), i)

            # Compute moon phase from date
            try:
                d = date_type.fromisoformat(date_str)
                moon_phase = compute_moon_phase(d)
            except (ValueError, TypeError):
                moon_phase = None

            daily_forecast.append({
                'date': date_str,
                'temp_high': self._safe_index(daily_raw.get('temperature_2m_max', []), i),
                'temp_low': self._safe_index(daily_raw.get('temperature_2m_min', []), i),
                'feels_like_high': self._safe_index(daily_raw.get('apparent_temperature_max', []), i),
                'feels_like_low': self._safe_index(daily_raw.get('apparent_temperature_min', []), i),
                'weather_code': day_code,
                'weather_description': day_weather['description'],
                'weather_icon': day_weather['icon'],
                'precipitation_sum': self._safe_index(daily_raw.get('precipitation_sum', []), i),
                'precipitation_probability': self._safe_index(daily_raw.get('precipitation_probability_max', []), i),
                'wind_speed_max': self._safe_index(daily_raw.get('wind_speed_10m_max', []), i),
                'wind_gusts_max': self._safe_index(daily_raw.get('wind_gusts_10m_max', []), i),
                'wind_direction_dominant': self._safe_index(daily_raw.get('wind_direction_10m_dominant', []), i),
                'uv_index_max': self._safe_index(daily_raw.get('uv_index_max', []), i),
                'sunrise': day_sunrise,
                'sunset': day_sunset,
                'moon_phase': moon_phase,
                'golden_hour': compute_golden_hour(day_sunrise, day_sunset),
            })

        # Parse hourly forecast (limit to 48 hours for today + tomorrow)
        hourly_raw = raw_data.get('hourly', {})
        hourly_forecast = []
        hourly_times = hourly_raw.get('time', [])
        max_hourly = min(len(hourly_times), 48)
        for i in range(max_hourly):
            h_code = self._safe_index(hourly_raw.get('weather_code', []), i)
            h_is_day = self._safe_index(hourly_raw.get('is_day', []), i) or 0
            h_weather = _decode_weather_code(h_code, is_day=h_is_day)

            hourly_forecast.append({
                'time': hourly_times[i],
                'temperature': self._safe_index(hourly_raw.get('temperature_2m', []), i),
                'feels_like': self._safe_index(hourly_raw.get('apparent_temperature', []), i),
                'dew_point': self._safe_index(hourly_raw.get('dew_point_2m', []), i),
                'humidity': self._safe_index(hourly_raw.get('relative_humidity_2m', []), i),
                'precipitation': self._safe_index(hourly_raw.get('precipitation', []), i),
                'precipitation_probability': self._safe_index(hourly_raw.get('precipitation_probability', []), i),
                'weather_code': h_code,
                'weather_description': h_weather['description'],
                'weather_icon': h_weather['icon'],
                'cloud_cover': self._safe_index(hourly_raw.get('cloud_cover', []), i),
                'visibility': self._safe_index(hourly_raw.get('visibility', []), i),
                'wind_speed': self._safe_index(hourly_raw.get('wind_speed_10m', []), i),
                'wind_direction': self._safe_index(hourly_raw.get('wind_direction_10m', []), i),
                'wind_gusts': self._safe_index(hourly_raw.get('wind_gusts_10m', []), i),
                'is_day': h_is_day,
                'uv_index': self._safe_index(hourly_raw.get('uv_index', []), i),
            })

        return {
            'current': current,
            'hourly_forecast': hourly_forecast,
            'daily_forecast': daily_forecast,
            'source': self.SOURCE_CODE,
            'timezone': tz_name,
        }

    @staticmethod
    def _safe_index(lst: list, idx: int):
        """Safely index into a list, returning None if out of bounds."""
        if lst and 0 <= idx < len(lst):
            return lst[idx]
        return None

    @staticmethod
    def _calculate_dew_point(temp: Optional[float], humidity: Optional[float]) -> Optional[float]:
        """Calculate dew point from temperature and relative humidity (Magnus formula)."""
        if temp is None or humidity is None:
            return None
        if humidity <= 0:
            return None
        import math
        a, b = 17.27, 237.7
        alpha = (a * temp) / (b + temp) + math.log(humidity / 100.0)
        dew_point = (b * alpha) / (a - alpha)
        return round(dew_point, 1)
