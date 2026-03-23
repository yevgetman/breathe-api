"""
Forecast aggregation service.
"""
import logging
from typing import List, Dict
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone
from django.conf import settings

from apps.core.utils import convert_aqi_to_category
from .models import ForecastData, AggregatedForecast

logger = logging.getLogger(__name__)


class ForecastAggregator:
    """
    Service for aggregating forecast data from multiple sources.
    """
    
    def __init__(self):
        self.settings = settings.AIR_QUALITY_SETTINGS
        self.cache_ttl = self.settings.get('RESPONSE_CACHE_TTL', 600)
        from apps.core.cache import ResponseCache
        precision = getattr(settings, 'CACHE_SETTINGS', {}).get('GEOHASH_PRECISION', 6)
        self._cache = ResponseCache(namespace='fcst', default_ttl=self.cache_ttl, geohash_precision=precision)
    
    def aggregate_forecasts(
        self,
        lat: float,
        lon: float,
        forecast_list: List[Dict],
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Aggregate forecast data from multiple sources.
        
        Args:
            lat: Query latitude
            lon: Query longitude
            forecast_list: List of forecast dicts from adapters
            use_cache: Whether to use cached results
            
        Returns:
            List of aggregated forecast dicts, sorted by timestamp
        """
        if not forecast_list:
            return []
        
        # Check cache
        if use_cache:
            cached = self._get_from_cache(lat, lon)
            if cached:
                return cached
        
        # Parse and store individual forecasts
        self._store_forecasts(lat, lon, forecast_list)
        
        # Group forecasts by hour
        grouped_forecasts = self._group_by_hour(forecast_list)
        
        # Aggregate each hour
        aggregated = []
        for hour_key, forecasts in sorted(grouped_forecasts.items()):
            agg_forecast = self._aggregate_hour(forecasts)
            if agg_forecast:
                aggregated.append(agg_forecast)
        
        # Cache the result
        self._save_to_cache(lat, lon, aggregated)
        
        return aggregated
    
    def _store_forecasts(self, lat: float, lon: float, forecast_list: List[Dict]):
        """Store individual forecast data points."""
        from decimal import Decimal
        from datetime import datetime
        
        for forecast in forecast_list:
            try:
                timestamp_str = forecast.get('timestamp')
                if not timestamp_str:
                    continue
                
                # Parse timestamp
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if not timezone.is_aware(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                else:
                    timestamp = timestamp_str
                
                # Skip past timestamps
                if timestamp < timezone.now():
                    continue
                
                category_info = convert_aqi_to_category(forecast.get('aqi', 0), scale='EPA')
                category = category_info['category'] if category_info else 'Unknown'
                
                ForecastData.objects.create(
                    lat=Decimal(str(lat)),
                    lon=Decimal(str(lon)),
                    forecast_timestamp=timestamp,
                    aqi=forecast.get('aqi', 0),
                    category=category,
                    pollutants=forecast.get('pollutants', {}),
                    source=forecast.get('source', 'UNKNOWN'),
                    confidence_level='medium',
                )
                
            except Exception as e:
                logger.error(f"Error storing forecast: {e}")
                continue
    
    def _group_by_hour(self, forecast_list: List[Dict]) -> Dict:
        """Group forecasts by hour."""
        from datetime import datetime
        
        grouped = defaultdict(list)
        
        for forecast in forecast_list:
            try:
                timestamp_str = forecast.get('timestamp')
                if not timestamp_str:
                    continue
                
                # Parse timestamp
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = timestamp_str
                
                # Round to nearest hour
                hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
                grouped[hour_key].append(forecast)
                
            except Exception as e:
                logger.error(f"Error grouping forecast: {e}")
                continue
        
        return grouped
    
    def _aggregate_hour(self, forecasts: List[Dict]) -> Dict:
        """Aggregate forecasts for a single hour using simple averaging."""
        if not forecasts:
            return None
        
        # Calculate average AQI
        aqi_values = [f.get('aqi') for f in forecasts if f.get('aqi') is not None]
        if not aqi_values:
            return None
        
        avg_aqi = round(sum(aqi_values) / len(aqi_values))
        
        # Aggregate pollutants
        pollutant_data = defaultdict(list)
        for forecast in forecasts:
            for pollutant, value in forecast.get('pollutants', {}).items():
                if value is not None:
                    pollutant_data[pollutant].append(value)
        
        aggregated_pollutants = {}
        for pollutant, values in pollutant_data.items():
            if values:
                aggregated_pollutants[pollutant] = round(sum(values) / len(values), 2)
        
        # Get category
        category_info = convert_aqi_to_category(avg_aqi, scale='EPA')
        category = category_info['category'] if category_info else 'Unknown'
        
        # Get sources
        sources = list(set([f.get('source') for f in forecasts if f.get('source')]))
        
        # Get timestamp (use first forecast's timestamp)
        timestamp = forecasts[0].get('timestamp')
        
        return {
            'timestamp': timestamp,
            'aqi': avg_aqi,
            'category': category,
            'pollutants': aggregated_pollutants,
            'sources': sources,
            'source_count': len(sources),
        }
    
    def _get_from_cache(self, lat: float, lon: float) -> List[Dict]:
        """Get aggregated forecasts from Redis cache (geohash-based key)."""
        return self._cache.get(lat, lon)

    def _save_to_cache(self, lat: float, lon: float, aggregated: List[Dict]):
        """Save aggregated forecasts to Redis cache, with optional DB write-through."""
        self._cache.set(lat, lon, aggregated)

        if getattr(settings, 'CACHE_SETTINGS', {}).get('WRITE_THROUGH_TO_DB', False):
            try:
                from decimal import Decimal
                from datetime import datetime

                lat_rounded = round(Decimal(str(lat)), 3)
                lon_rounded = round(Decimal(str(lon)), 3)
                cached_until = timezone.now() + timedelta(seconds=self.cache_ttl)

                for forecast in aggregated:
                    timestamp_str = forecast.get('timestamp')
                    if isinstance(timestamp_str, str):
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if not timezone.is_aware(timestamp):
                            timestamp = timezone.make_aware(timestamp)
                    else:
                        timestamp = timestamp_str

                    AggregatedForecast.objects.update_or_create(
                        lat=lat_rounded, lon=lon_rounded,
                        forecast_timestamp=timestamp,
                        defaults={
                            'aqi': forecast.get('aqi'),
                            'category': forecast.get('category'),
                            'pollutants': forecast.get('pollutants', {}),
                            'sources': forecast.get('sources', []),
                            'source_count': len(forecast.get('sources', [])),
                            'cached_until': cached_until,
                        }
                    )
            except Exception as e:
                logger.warning(f"Forecast DB write-through failed (non-fatal): {e}")
