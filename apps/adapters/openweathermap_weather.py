"""
OpenWeatherMap weather adapter (fallback provider).
Reuses the existing OPENWEATHERMAP API key for standard weather data.
"""
import logging
import math
from collections import defaultdict
from datetime import datetime, date
from typing import Dict, List, Optional

from django.utils import timezone

from .base import BaseAdapter

logger = logging.getLogger(__name__)

# OWM icon code to generic icon name mapping
OWM_ICON_MAP = {
    '01d': 'clear-day',       '01n': 'clear-night',
    '02d': 'partly-cloudy-day', '02n': 'partly-cloudy-night',
    '03d': 'cloudy',          '03n': 'cloudy',
    '04d': 'cloudy',          '04n': 'cloudy',
    '09d': 'rain',            '09n': 'rain',
    '10d': 'rain',            '10n': 'rain',
    '11d': 'thunderstorm',    '11n': 'thunderstorm',
    '13d': 'snow',            '13n': 'snow',
    '50d': 'fog',             '50n': 'fog',
}


class OWMWeatherAdapter(BaseAdapter):
    """
    Adapter for OpenWeatherMap standard weather endpoints.
    Fallback provider — uses the same API key as the air pollution adapter.
    Free tier: current weather + 5-day/3h forecast.
    """

    SOURCE_NAME = "OpenWeatherMap Weather"
    SOURCE_CODE = "OWM_WEATHER"
    API_KEY_SETTINGS_NAME = "OPENWEATHERMAP"
    API_BASE_URL = "https://api.openweathermap.org/data/2.5/"
    REQUIRES_API_KEY = True

    def _add_api_key(self, params: Dict, headers: Dict):
        """OpenWeatherMap uses 'appid' parameter."""
        if self.api_key:
            params['appid'] = self.api_key

    def fetch_current(self, lat: float, lon: float, **kwargs) -> Optional[Dict]:
        """
        Fetch current weather from /data/2.5/weather.

        Returns:
            Dict with 'current' and 'daily_forecast' keys, or None on error.
        """
        params = {
            'lat': lat,
            'lon': lon,
            'units': 'metric',
        }

        raw_data = self._make_request('weather', params=params)
        if not raw_data:
            return None

        current = self._normalize_current(raw_data)

        # Also fetch 5-day forecast
        daily_forecast = self.fetch_forecast(lat, lon) or []

        return {
            'current': current,
            'daily_forecast': daily_forecast,
            'source': self.SOURCE_CODE,
            'timezone': None,
        }

    def fetch_forecast(self, lat: float, lon: float, **kwargs) -> Optional[List[Dict]]:
        """
        Fetch 5-day/3h forecast from /data/2.5/forecast and aggregate to daily.
        """
        params = {
            'lat': lat,
            'lon': lon,
            'units': 'metric',
        }

        raw_data = self._make_request('forecast', params=params)
        if not raw_data or 'list' not in raw_data:
            return None

        return self._aggregate_to_daily(raw_data['list'])

    def _normalize_current(self, raw: Dict) -> Dict:
        """Normalize OWM /weather response to unified schema."""
        main = raw.get('main', {})
        wind = raw.get('wind', {})
        clouds = raw.get('clouds', {})
        sys = raw.get('sys', {})
        weather_list = raw.get('weather', [{}])
        weather = weather_list[0] if weather_list else {}

        temp = main.get('temp')
        humidity = main.get('humidity')

        sunrise_ts = sys.get('sunrise')
        sunset_ts = sys.get('sunset')

        return {
            'temperature': temp,
            'feels_like': main.get('feels_like'),
            'dew_point': self._calculate_dew_point(temp, humidity),
            'humidity': humidity,
            'pressure': main.get('pressure'),
            'visibility': raw.get('visibility'),
            'cloud_cover': clouds.get('all'),
            'uv_index': None,  # Not available in free tier /weather
            'wind_speed': wind.get('speed'),
            'wind_direction': wind.get('deg'),
            'wind_gusts': wind.get('gust'),
            'weather_description': weather.get('description', '').capitalize(),
            'weather_icon': OWM_ICON_MAP.get(weather.get('icon', ''), 'unknown'),
            'sunrise': datetime.fromtimestamp(sunrise_ts, tz=timezone.utc).isoformat() if sunrise_ts else None,
            'sunset': datetime.fromtimestamp(sunset_ts, tz=timezone.utc).isoformat() if sunset_ts else None,
            'observation_time': datetime.fromtimestamp(raw.get('dt', 0), tz=timezone.utc).isoformat(),
        }

    def _aggregate_to_daily(self, forecast_list: List[Dict]) -> List[Dict]:
        """Aggregate 3-hour forecast entries into daily summaries."""
        days = defaultdict(lambda: {
            'temps': [], 'feels': [], 'weather_codes': [],
            'descriptions': [], 'icons': [], 'precip': [],
            'wind_speeds': [], 'wind_gusts': [], 'wind_dirs': [],
        })

        for entry in forecast_list:
            try:
                dt = datetime.fromtimestamp(entry.get('dt', 0), tz=timezone.utc)
                day_key = dt.date().isoformat()
                main = entry.get('main', {})
                wind = entry.get('wind', {})
                weather = entry.get('weather', [{}])[0] if entry.get('weather') else {}
                rain = entry.get('rain', {})

                days[day_key]['temps'].append(main.get('temp'))
                days[day_key]['feels'].append(main.get('feels_like'))
                days[day_key]['descriptions'].append(weather.get('description', ''))
                days[day_key]['icons'].append(weather.get('icon', ''))
                days[day_key]['precip'].append(rain.get('3h', 0.0))
                days[day_key]['wind_speeds'].append(wind.get('speed'))
                days[day_key]['wind_gusts'].append(wind.get('gust'))
                days[day_key]['wind_dirs'].append(wind.get('deg'))
            except Exception as e:
                logger.error(f"Error aggregating OWM forecast entry: {e}")
                continue

        daily = []
        for day_key in sorted(days.keys()):
            d = days[day_key]
            temps = [t for t in d['temps'] if t is not None]
            feels = [f for f in d['feels'] if f is not None]
            speeds = [s for s in d['wind_speeds'] if s is not None]
            gusts = [g for g in d['wind_gusts'] if g is not None]
            dirs_ = [dr for dr in d['wind_dirs'] if dr is not None]

            # Pick most common description
            desc = max(set(d['descriptions']), key=d['descriptions'].count) if d['descriptions'] else ''
            icon_raw = max(set(d['icons']), key=d['icons'].count) if d['icons'] else ''

            daily.append({
                'date': day_key,
                'temp_high': max(temps) if temps else None,
                'temp_low': min(temps) if temps else None,
                'feels_like_high': max(feels) if feels else None,
                'feels_like_low': min(feels) if feels else None,
                'weather_description': desc.capitalize(),
                'weather_icon': OWM_ICON_MAP.get(icon_raw, 'unknown'),
                'precipitation_sum': round(sum(d['precip']), 2) if d['precip'] else None,
                'precipitation_probability': None,  # Not in free tier
                'wind_speed_max': max(speeds) if speeds else None,
                'wind_gusts_max': max(gusts) if gusts else None,
                'wind_direction_dominant': round(sum(dirs_) / len(dirs_)) if dirs_ else None,
                'uv_index_max': None,  # Not in free tier
                'sunrise': None,  # Not in 5-day forecast
                'sunset': None,
            })

        return daily

    @staticmethod
    def _calculate_dew_point(temp: Optional[float], humidity: Optional[float]) -> Optional[float]:
        """Calculate dew point using Magnus formula."""
        if temp is None or humidity is None or humidity <= 0:
            return None
        a, b = 17.27, 237.7
        alpha = (a * temp) / (b + temp) + math.log(humidity / 100.0)
        return round((b * alpha) / (a - alpha), 1)
