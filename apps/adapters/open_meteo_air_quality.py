"""
Open-Meteo Air Quality adapter for pollen data, hourly AQI, and historical AQ.
Free, no API key required, global coverage.
"""
import logging
from typing import Dict, List, Optional

from .base import BaseAdapter
from apps.core.constants import (
    POLLEN_TYPE_GROUPS,
    POLLEN_THRESHOLDS,
    POLLEN_DISPLAY_NAMES,
)

logger = logging.getLogger(__name__)


def _classify_pollen_level(value: Optional[float], category: str) -> str:
    """Classify a pollen grains/m³ value into a named level."""
    if value is None or value <= 0:
        return 'none'
    thresholds = POLLEN_THRESHOLDS.get(category, POLLEN_THRESHOLDS['tree'])
    for threshold, level in thresholds:
        if value <= threshold:
            return level
    return 'very_high'


def _aqi_to_category(aqi: Optional[int]) -> str:
    """Convert US AQI integer to category string."""
    if aqi is None:
        return 'unknown'
    if aqi <= 50:
        return 'Good'
    if aqi <= 100:
        return 'Moderate'
    if aqi <= 150:
        return 'Unhealthy for Sensitive Groups'
    if aqi <= 200:
        return 'Unhealthy'
    if aqi <= 300:
        return 'Very Unhealthy'
    return 'Hazardous'


class OpenMeteoAirQualityAdapter(BaseAdapter):
    """
    Adapter for Open-Meteo Air Quality API.
    Provides hourly AQI, pollutant concentrations, and pollen forecasts.
    Free, no API key, global coverage.
    """

    SOURCE_NAME = "Open-Meteo Air Quality"
    SOURCE_CODE = "OPEN_METEO_AQ"
    API_BASE_URL = "https://air-quality-api.open-meteo.com/v1/"
    REQUIRES_API_KEY = False
    QUALITY_LEVEL = 'model'

    _CURRENT_FIELDS = [
        'us_aqi', 'pm10', 'pm2_5', 'carbon_monoxide', 'nitrogen_dioxide',
        'sulphur_dioxide', 'ozone',
        'alder_pollen', 'birch_pollen', 'grass_pollen',
        'mugwort_pollen', 'olive_pollen', 'ragweed_pollen',
    ]

    _HOURLY_FIELDS = _CURRENT_FIELDS + ['uv_index']

    def _add_api_key(self, params: Dict, headers: Dict):
        """No API key needed for Open-Meteo."""
        pass

    def fetch_current(self, lat: float, lon: float, **kwargs) -> Optional[Dict]:
        """
        Fetch current AQ + pollen data and 48-hour hourly forecast.

        Returns dict with 'current', 'hourly', and 'pollen' sections.
        """
        forecast_days = kwargs.get('forecast_days', 2)

        params = {
            'latitude': lat,
            'longitude': lon,
            'current': ','.join(self._CURRENT_FIELDS),
            'hourly': ','.join(self._HOURLY_FIELDS),
            'forecast_days': forecast_days,
            'timezone': 'auto',
        }

        raw_data = self._make_request('air-quality', params=params)
        if not raw_data:
            return None

        return self._normalize(raw_data)

    def fetch_historical(self, lat: float, lon: float, past_days: int = 30, **kwargs) -> Optional[Dict]:
        """
        Fetch historical AQ data for Hidden Gems comparisons.

        Uses the past_days parameter to get up to 92 days of history.
        Returns summary statistics for the historical period.
        """
        past_days = min(past_days, 92)

        params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': 'us_aqi,pm2_5',
            'past_days': past_days,
            'forecast_days': 1,
            'timezone': 'auto',
        }

        raw_data = self._make_request('air-quality', params=params)
        if not raw_data:
            return None

        return self._summarize_historical(raw_data, past_days)

    def _normalize(self, raw_data: Dict) -> Dict:
        """Normalize Open-Meteo AQ response."""
        current_raw = raw_data.get('current', {})
        hourly_raw = raw_data.get('hourly', {})

        # Current AQI and pollutants
        current_aqi = current_raw.get('us_aqi')
        current = {
            'aqi': int(current_aqi) if current_aqi is not None else None,
            'aqi_category': _aqi_to_category(int(current_aqi) if current_aqi is not None else None),
            'pollutants': {
                'pm25': current_raw.get('pm2_5'),
                'pm10': current_raw.get('pm10'),
                'o3': current_raw.get('ozone'),
                'no2': current_raw.get('nitrogen_dioxide'),
                'so2': current_raw.get('sulphur_dioxide'),
                'co': current_raw.get('carbon_monoxide'),
            },
        }

        # Current pollen
        pollen = self._extract_pollen(current_raw)

        # Hourly data (limit to 48 hours)
        hourly = []
        times = hourly_raw.get('time', [])
        max_hours = min(len(times), 48)
        for i in range(max_hours):
            h_aqi = self._safe_index(hourly_raw.get('us_aqi', []), i)
            h_aqi_int = int(h_aqi) if h_aqi is not None else None

            hourly.append({
                'time': times[i],
                'aqi': h_aqi_int,
                'aqi_category': _aqi_to_category(h_aqi_int),
                'pollutants': {
                    'pm25': self._safe_index(hourly_raw.get('pm2_5', []), i),
                    'pm10': self._safe_index(hourly_raw.get('pm10', []), i),
                    'o3': self._safe_index(hourly_raw.get('ozone', []), i),
                    'no2': self._safe_index(hourly_raw.get('nitrogen_dioxide', []), i),
                    'so2': self._safe_index(hourly_raw.get('sulphur_dioxide', []), i),
                    'co': self._safe_index(hourly_raw.get('carbon_monoxide', []), i),
                },
                'pollen': self._extract_pollen_at_index(hourly_raw, i),
                'uv_index': self._safe_index(hourly_raw.get('uv_index', []), i),
            })

        return {
            'current': current,
            'pollen': pollen,
            'hourly': hourly,
            'source': self.SOURCE_CODE,
        }

    def _extract_pollen(self, data: Dict) -> Dict:
        """Extract and categorize pollen data from a data dict."""
        result = {}
        dominant_value = 0
        dominant_allergen = None

        for category, fields in POLLEN_TYPE_GROUPS.items():
            total = 0
            count = 0
            for field in fields:
                val = data.get(field)
                if val is not None:
                    total += val
                    count += 1
                    if val > dominant_value:
                        dominant_value = val
                        dominant_allergen = POLLEN_DISPLAY_NAMES.get(field, field)
            avg = total / count if count > 0 else 0
            result[category] = {
                'level': _classify_pollen_level(avg, category),
                'value': round(avg, 1),
            }

        result['dominant_allergen'] = dominant_allergen
        return result

    def _extract_pollen_at_index(self, hourly_raw: Dict, i: int) -> Dict:
        """Extract pollen data at a specific hourly index."""
        data = {}
        for field in ['alder_pollen', 'birch_pollen', 'olive_pollen',
                       'grass_pollen', 'mugwort_pollen', 'ragweed_pollen']:
            data[field] = self._safe_index(hourly_raw.get(field, []), i)
        return self._extract_pollen(data)

    def _summarize_historical(self, raw_data: Dict, past_days: int) -> Dict:
        """Compute summary statistics from historical hourly AQ data."""
        hourly_raw = raw_data.get('hourly', {})
        aqi_values = [v for v in hourly_raw.get('us_aqi', []) if v is not None]

        if not aqi_values:
            return {'past_days': past_days, 'aqi_avg': None, 'aqi_min': None, 'aqi_max': None}

        return {
            'past_days': past_days,
            'aqi_avg': round(sum(aqi_values) / len(aqi_values), 1),
            'aqi_min': int(min(aqi_values)),
            'aqi_max': int(max(aqi_values)),
            'sample_count': len(aqi_values),
        }

    @staticmethod
    def _safe_index(lst: list, idx: int):
        """Safely index into a list, returning None if out of bounds."""
        if lst and 0 <= idx < len(lst):
            return lst[idx]
        return None
