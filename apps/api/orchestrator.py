"""
Main orchestrator that coordinates all services to fetch and blend air quality data.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import Dict, List

from django.conf import settings

from apps.location.services import LocationService
from apps.adapters.airnow import AirNowAdapter
from apps.adapters.purpleair import PurpleAirAdapter
from apps.adapters.openweathermap import OpenWeatherMapAdapter
from apps.adapters.waqi import WAQIAdapter
from apps.adapters.airvisual import AirVisualAdapter
from apps.fusion.engine import FusionEngine
from apps.forecast.services import ForecastAggregator
from apps.core.utils import convert_aqi_to_category

logger = logging.getLogger(__name__)

# Per-adapter timeout for future.result().  Should be slightly above the
# adapter's own REQUEST_TIMEOUT (default 10s) + retry overhead.
_ADAPTER_FUTURE_TIMEOUT = 15  # seconds


class AirQualityOrchestrator:
    """
    Main orchestrator service that coordinates:
    1. Location resolution
    2. Data fetching from multiple sources
    3. Data fusion/blending
    4. Forecast aggregation
    5. Response generation
    """
    
    def __init__(self):
        self.location_service = LocationService()
        self.fusion_engine = FusionEngine()
        self.forecast_aggregator = ForecastAggregator()
        
        # Initialize adapters
        self.adapters = {
            'EPA_AIRNOW': AirNowAdapter(),
            'PURPLEAIR': PurpleAirAdapter(),
            'OPENWEATHERMAP': OpenWeatherMapAdapter(),
            'WAQI': WAQIAdapter(),
            'AIRVISUAL': AirVisualAdapter(),
        }
    
    def get_air_quality(
        self,
        lat: float,
        lon: float,
        include_forecast: bool = False,
        radius_km: float = 25,
        use_cache: bool = True
    ) -> Dict:
        """
        Main method to get air quality data for coordinates.
        
        Args:
            lat: Latitude
            lon: Longitude
            include_forecast: Whether to include forecast data
            radius_km: Search radius for sensors
            use_cache: Whether to use cached data
            
        Returns:
            Complete air quality response dict
        """
        # 1. Resolve location
        location_info = self.location_service.reverse_geocode(lat, lon, use_cache=use_cache)
        region_code = location_info.get('country', 'DEFAULT')
        
        # Get region-specific configuration
        region_config = self.location_service.get_region_config(region_code)
        
        # 2. Fetch current data from all available adapters (parallel)
        current_data = self._fetch_all_current(lat, lon, radius_km, region_config)
        
        # 3. Blend data from multiple sources
        blended_result = self.fusion_engine.blend(
            lat=lat,
            lon=lon,
            source_data_list=current_data,
            region_code=region_code,
            use_cache=use_cache
        )
        
        # 4. Add location info
        blended_result['location'] = location_info
        
        # 5. Add health advice
        if blended_result['current']['aqi'] is not None:
            category_info = convert_aqi_to_category(
                blended_result['current']['aqi'],
                scale=region_config.get('aqi_scale', 'EPA')
            )
            if category_info:
                blended_result['health_advice'] = category_info['health_message']
        
        # 6. Fetch and aggregate forecasts if requested
        if include_forecast:
            forecast_data = self._fetch_all_forecasts(lat, lon, region_config)
            aggregated_forecasts = self.forecast_aggregator.aggregate_forecasts(
                lat, lon, forecast_data, use_cache=use_cache
            )
            blended_result['forecast'] = aggregated_forecasts
        
        return blended_result
    
    def _fetch_all_current(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        region_config: Dict
    ) -> List:
        """
        Fetch current data from all available adapters in parallel.
        Uses per-adapter timeouts to avoid one slow source blocking the response.
        """
        all_data = []

        # Get source priority for this region
        source_priority = region_config.get('source_priority', [])

        # Determine which adapters to use based on priority and availability
        active_adapters = []
        seen = set()
        for source_code in source_priority:
            adapter = self.adapters.get(source_code)
            if adapter and adapter.is_available():
                active_adapters.append((source_code, adapter))
                seen.add(source_code)

        # Add remaining adapters not in priority list
        for source_code, adapter in self.adapters.items():
            if source_code not in seen and adapter.is_available():
                active_adapters.append((source_code, adapter))

        if not active_adapters:
            logger.warning("No active adapters available")
            return all_data

        # Fetch data in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(len(active_adapters), 5)) as executor:
            future_to_source = {}

            for source_code, adapter in active_adapters:
                future = executor.submit(
                    self._safe_fetch_current,
                    adapter,
                    lat,
                    lon,
                    radius_km
                )
                future_to_source[future] = source_code

            # Collect results with per-adapter timeout.
            # as_completed() itself can raise TimeoutError when the aggregate
            # deadline expires, so we catch it at the loop level.
            try:
                for future in as_completed(future_to_source, timeout=_ADAPTER_FUTURE_TIMEOUT + 5):
                    source_code = future_to_source[future]
                    try:
                        data = future.result(timeout=_ADAPTER_FUTURE_TIMEOUT)
                        if data:
                            all_data.extend(data)
                            logger.info(f"Fetched {len(data)} records from {source_code}")
                    except FuturesTimeoutError:
                        logger.warning(f"Timeout fetching from {source_code} – skipping")
                        future.cancel()
                    except Exception as e:
                        logger.error(f"Error fetching from {source_code}: {e}")
            except (FuturesTimeoutError, TimeoutError):
                logger.warning("Aggregate adapter fetch deadline exceeded – returning partial results")

        return all_data
    
    def _safe_fetch_current(self, adapter, lat: float, lon: float, radius_km: float) -> List:
        """Safely fetch data with error handling."""
        try:
            if hasattr(adapter, 'SOURCE_CODE') and adapter.SOURCE_CODE == 'PURPLEAIR':
                # PurpleAir uses radius_km parameter
                return adapter.fetch_current(lat, lon, radius_km=radius_km)
            else:
                return adapter.fetch_current(lat, lon)
        except Exception as e:
            logger.error(f"Error in {adapter.SOURCE_NAME}: {e}")
            return []
    
    def _fetch_all_forecasts(self, lat: float, lon: float, region_config: Dict) -> List[Dict]:
        """
        Fetch forecast data from adapters that support it.
        """
        all_forecasts = []

        # Only certain adapters support forecasts
        forecast_adapters = [
            self.adapters.get('EPA_AIRNOW'),
            self.adapters.get('OPENWEATHERMAP'),
        ]
        active = [a for a in forecast_adapters if a and a.is_available()]

        if not active:
            return all_forecasts

        with ThreadPoolExecutor(max_workers=len(active)) as executor:
            future_to_adapter = {}

            for adapter in active:
                future = executor.submit(
                    self._safe_fetch_forecast,
                    adapter,
                    lat,
                    lon
                )
                future_to_adapter[future] = adapter.SOURCE_NAME

            # Collect results
            try:
                for future in as_completed(future_to_adapter, timeout=_ADAPTER_FUTURE_TIMEOUT + 5):
                    adapter_name = future_to_adapter[future]
                    try:
                        data = future.result(timeout=_ADAPTER_FUTURE_TIMEOUT)
                        if data:
                            all_forecasts.extend(data)
                    except FuturesTimeoutError:
                        logger.warning(f"Timeout fetching forecast from {adapter_name}")
                        future.cancel()
                    except Exception as e:
                        logger.error(f"Error fetching forecast from {adapter_name}: {e}")
            except (FuturesTimeoutError, TimeoutError):
                logger.warning("Aggregate forecast fetch deadline exceeded – returning partial results")

        return all_forecasts
    
    def _safe_fetch_forecast(self, adapter, lat: float, lon: float) -> List[Dict]:
        """Safely fetch forecast with error handling."""
        try:
            return adapter.fetch_forecast(lat, lon)
        except Exception as e:
            logger.error(f"Error in {adapter.SOURCE_NAME} forecast: {e}")
            return []
