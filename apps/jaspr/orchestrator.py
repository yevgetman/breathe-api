"""
JASPR Weather orchestrator — assembles combined weather + AQ + pollen response
in a single call optimized for the JASPR Weather iOS app.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Optional

from django.conf import settings
from django.utils import timezone

from apps.adapters.open_meteo_air_quality import OpenMeteoAirQualityAdapter
from apps.api.orchestrator import AirQualityOrchestrator
from apps.core.cache import ResponseCache
from apps.location.services import LocationService
from apps.weather.orchestrator import WeatherOrchestrator

from .analysis import compute_hidden_gems, compute_historical_summary

logger = logging.getLogger(__name__)

_THREAD_TIMEOUT = 20  # seconds


class JasprOrchestrator:
    """
    Coordinates parallel data fetching for the JASPR combined endpoint.

    Fetches weather, AQ, pollen, and (optionally) historical data in parallel,
    then merges everything into a single response dict.
    """

    def __init__(self):
        self.weather_orch = WeatherOrchestrator()
        self.aq_orch = AirQualityOrchestrator()
        self.om_aq_adapter = OpenMeteoAirQualityAdapter()
        self.location_service = LocationService()
        precision = getattr(settings, 'CACHE_SETTINGS', {}).get('GEOHASH_PRECISION', 6)
        self._cache = ResponseCache(namespace='jaspr', default_ttl=300, geohash_precision=precision)
        self._hist_cache = ResponseCache(namespace='jaspr_hist', default_ttl=21600, geohash_precision=precision)

    def get_jaspr_data(
        self,
        lat: float,
        lon: float,
        units: str = 'metric',
        include_historical: bool = False,
        use_cache: bool = True,
    ) -> Dict:
        """
        Fetch and assemble all data for the JASPR Weather app.

        Returns a combined dict with weather, AQ, pollen, hourly, daily,
        and optionally historical data.
        """
        # Check combined cache
        if use_cache:
            cache_extra = ('hist',) if include_historical else ()
            cached = self._cache.get(lat, lon, *cache_extra)
            if cached:
                return cached

        # Parallel data fetch
        weather_result = None
        aq_result = None
        pollen_result = None
        historical_stats = None

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}

            futures[executor.submit(
                self.weather_orch.get_weather, lat, lon, units=units, use_cache=use_cache
            )] = 'weather'

            futures[executor.submit(
                self.aq_orch.get_air_quality, lat, lon, include_forecast=True, use_cache=use_cache
            )] = 'aq'

            futures[executor.submit(
                self.om_aq_adapter.fetch_current, lat, lon, forecast_days=2
            )] = 'pollen'

            if include_historical:
                futures[executor.submit(
                    self._get_historical, lat, lon
                )] = 'historical'

            for future in as_completed(futures, timeout=_THREAD_TIMEOUT):
                key = futures[future]
                try:
                    result = future.result(timeout=5)
                    if key == 'weather':
                        weather_result = result
                    elif key == 'aq':
                        aq_result = result
                    elif key == 'pollen':
                        pollen_result = result
                    elif key == 'historical':
                        historical_stats = result
                except Exception as e:
                    logger.warning(f"JASPR {key} fetch failed: {e}")

        # Assemble combined response
        response = self._assemble(
            weather=weather_result,
            aq=aq_result,
            pollen=pollen_result,
            historical_stats=historical_stats,
            include_historical=include_historical,
            units=units,
        )

        # Cache the combined result
        if use_cache:
            cache_extra = ('hist',) if include_historical else ()
            self._cache.set(lat, lon, response, *cache_extra)

        return response

    def _get_historical(self, lat: float, lon: float) -> Optional[Dict]:
        """Fetch historical AQ data, with its own longer cache."""
        cached = self._hist_cache.get(lat, lon)
        if cached:
            return cached
        stats = self.om_aq_adapter.fetch_historical(lat, lon, past_days=30)
        if stats:
            self._hist_cache.set(lat, lon, stats)
        return stats

    def _assemble(
        self,
        weather: Optional[Dict],
        aq: Optional[Dict],
        pollen: Optional[Dict],
        historical_stats: Optional[Dict],
        include_historical: bool,
        units: str,
    ) -> Dict:
        """Merge weather, AQ, pollen, and historical into JASPR response shape."""
        weather = weather or {}
        aq = aq or {}
        pollen_data = pollen or {}

        # Location from weather (has the richest geocode data)
        location = weather.get('location', aq.get('location', {}))

        # Current conditions: merge weather + AQ + pollen
        wx_current = weather.get('current') or {}
        aq_current = aq.get('current', {})
        pollen_current = pollen_data.get('pollen', {})

        current = {
            **wx_current,
            'aqi': aq_current.get('aqi'),
            'aqi_category': aq_current.get('category', ''),
            'dominant_pollutant': self._find_dominant_pollutant(aq_current.get('pollutants', {})),
            'pollutants': aq_current.get('pollutants', {}),
            'pollen': pollen_current,
            'health_advice': aq.get('health_advice', ''),
        }

        # Hourly forecast: merge weather hourly with AQ hourly by timestamp
        wx_hourly = weather.get('hourly_forecast', [])
        aq_hourly = pollen_data.get('hourly', [])
        hourly_forecast = self._merge_hourly(wx_hourly, aq_hourly)

        # Daily forecast from weather (already has moon_phase + golden_hour)
        daily_forecast = weather.get('daily_forecast', [])

        # Historical analysis
        historical = None
        hidden_gems = []
        if include_historical and historical_stats:
            historical = compute_historical_summary(
                current_aqi=aq_current.get('aqi'),
                historical_stats=historical_stats,
            )
            hidden_gems = compute_hidden_gems(
                current_aqi=aq_current.get('aqi'),
                current_humidity=wx_current.get('humidity'),
                current_weather_code=wx_current.get('weather_code'),
                historical=historical_stats,
            )

        return {
            'location': location,
            'current': current,
            'hourly_forecast': hourly_forecast,
            'daily_forecast': daily_forecast,
            'historical': historical,
            'hidden_gems': hidden_gems,
            'source': weather.get('source', ''),
            'units': weather.get('units', units),
            'generated_at': timezone.now().isoformat(),
        }

    def _merge_hourly(self, wx_hourly: list, aq_hourly: list) -> list:
        """Merge weather hourly and AQ hourly by matching timestamps."""
        # Build lookup of AQ data by time
        aq_by_time = {}
        for entry in aq_hourly:
            t = entry.get('time', '')
            aq_by_time[t] = entry

        merged = []
        for wx in wx_hourly:
            t = wx.get('time', '')
            aq = aq_by_time.get(t, {})
            merged.append({
                **wx,
                'aqi': aq.get('aqi'),
                'aqi_category': aq.get('aqi_category', ''),
            })

        return merged

    @staticmethod
    def _find_dominant_pollutant(pollutants: Dict) -> Optional[str]:
        """Find the pollutant with the highest concentration."""
        if not pollutants:
            return None
        best = None
        best_val = -1
        for key, val in pollutants.items():
            if val is not None and val > best_val:
                best_val = val
                best = key
        return best
