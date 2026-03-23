"""
Data fusion engine for blending multiple air quality sources.
"""
import logging
import math
import time
from typing import List, Dict, Optional
from collections import defaultdict

from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from apps.core.utils import calculate_time_decay_weight, is_data_fresh, convert_aqi_to_category
from apps.adapters.models import SourceData
from .models import BlendedData, SourceWeight, FusionLog

logger = logging.getLogger(__name__)


class FusionEngine:
    """
    Engine for blending air quality data from multiple sources.
    
    Uses weighted averaging with consideration for:
    - Source trust level
    - Data freshness (time decay)
    - Distance from query point
    - Pollutant-specific confidence
    """
    
    def __init__(self):
        self.settings = settings.AIR_QUALITY_SETTINGS
        self.cache_ttl = self.settings.get('RESPONSE_CACHE_TTL', 600)
        from apps.core.cache import ResponseCache
        precision = getattr(settings, 'CACHE_SETTINGS', {}).get('GEOHASH_PRECISION', 6)
        self._cache = ResponseCache(namespace='aq', default_ttl=self.cache_ttl, geohash_precision=precision)
    
    def blend(
        self, 
        lat: float, 
        lon: float, 
        source_data_list: List[SourceData],
        region_code: str = 'DEFAULT',
        use_cache: bool = True
    ) -> Dict:
        """
        Blend multiple data sources into a single unified response.
        
        Args:
            lat: Query latitude
            lon: Query longitude
            source_data_list: List of SourceData objects from various adapters
            region_code: Region code for source prioritization
            use_cache: Whether to use cached results
            
        Returns:
            Dict with blended air quality data
        """
        start_time = time.time()
        
        # Check cache first
        if use_cache:
            cached = self._get_from_cache(lat, lon)
            if cached:
                self._log_fusion(
                    lat, lon,
                    result_aqi=cached['current']['aqi'],
                    sources_used=cached['current']['sources'],
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    cache_hit=True
                )
                return cached
        
        # Filter fresh data
        fresh_data = [
            sd for sd in source_data_list
            if is_data_fresh(sd.timestamp, max_age_hours=self.settings.get('MAX_DATA_AGE_HOURS', 3))
        ]
        
        if not fresh_data:
            logger.warning(f"No fresh data available for ({lat}, {lon})")
            return self._get_default_response(lat, lon)
        
        # Calculate weights for each source
        weighted_sources = []
        for source_data in fresh_data:
            weight = self._calculate_weight(
                source_data=source_data,
                region_code=region_code,
                query_lat=lat,
                query_lon=lon
            )
            weighted_sources.append((source_data, weight))
        
        # Blend AQI values
        blended_aqi = self._blend_aqi(weighted_sources)
        
        # Blend pollutants
        blended_pollutants = self._blend_pollutants(weighted_sources)
        
        # Get category info
        category_info = convert_aqi_to_category(blended_aqi, scale='EPA')
        category = category_info['category'] if category_info else 'Unknown'
        
        # Build response
        sources_used = list(set([sd.source for sd, _ in weighted_sources]))
        
        result = {
            'lat': float(lat),
            'lon': float(lon),
            'current': {
                'aqi': blended_aqi,
                'category': category,
                'pollutants': blended_pollutants,
                'sources': sources_used,
                'last_updated': max([sd.timestamp for sd, _ in weighted_sources]).isoformat(),
            },
            'source_details': self._get_source_details(weighted_sources),
        }
        
        # Cache the result
        self._save_to_cache(lat, lon, result)
        
        # Log fusion operation
        execution_time = int((time.time() - start_time) * 1000)
        self._log_fusion(
            lat, lon,
            result_aqi=blended_aqi,
            sources_used=sources_used,
            sources_attempted=[sd.source for sd in source_data_list],
            weight_details={'weights': [(sd.source, w) for sd, w in weighted_sources]},
            execution_time_ms=execution_time,
            cache_hit=False
        )
        
        return result
    
    def _calculate_weight(
        self,
        source_data: SourceData,
        region_code: str,
        query_lat: float,
        query_lon: float
    ) -> float:
        """
        Calculate weight for a data source considering multiple factors.
        
        Factors:
        1. Source trust level (from SourceWeight config)
        2. Data freshness (time decay)
        3. Distance from query point
        4. Quality level
        """
        # Get base trust weight
        try:
            source_weight_config = SourceWeight.objects.get(
                source_code=source_data.source,
                region_code=region_code,
                is_active=True
            )
            trust_weight = source_weight_config.trust_weight
            distance_factor = source_weight_config.distance_weight_factor
            time_factor = source_weight_config.time_decay_factor
        except SourceWeight.DoesNotExist:
            # Use defaults from settings
            trust_weight = self.settings['SOURCE_WEIGHTS'].get(source_data.source, 0.5)
            distance_factor = 1.0
            time_factor = 1.0
        
        # Time decay weight
        time_weight = calculate_time_decay_weight(
            source_data.timestamp,
            preferred_age_minutes=self.settings.get('PREFERRED_DATA_AGE_MINUTES', 30)
        )
        time_weight = time_weight * time_factor
        
        # Distance weight (inverse relationship)
        distance_km = source_data.distance_km
        if distance_km is not None and distance_km > 0:
            # Closer = higher weight, max weight at 0 km, decays with distance
            max_distance = self.settings.get('DEFAULT_SEARCH_RADIUS_KM', 25)
            distance_weight = max(0.1, 1.0 - (abs(distance_km) / max_distance))
            distance_weight = distance_weight * distance_factor
        else:
            distance_weight = 1.0
        
        # Quality level weight
        quality_weights = {
            'verified': 1.0,
            'model': 0.8,
            'sensor': 0.9,
            'estimated': 0.6,
        }
        quality_weight = quality_weights.get(source_data.quality_level, 0.5)
        
        # Confidence score weight (conservative default for unknown confidence)
        if source_data.confidence_score is not None and source_data.confidence_score > 0:
            confidence_weight = min(source_data.confidence_score, 100.0) / 100.0
        else:
            confidence_weight = 0.5
        
        # Combined weight
        final_weight = (
            trust_weight *
            time_weight *
            distance_weight *
            quality_weight *
            confidence_weight
        )
        
        return final_weight
    
    def _blend_aqi(self, weighted_sources: List[tuple]) -> int:
        """
        Blend AQI values using weighted average.

        Args:
            weighted_sources: List of (SourceData, weight) tuples

        Returns:
            Blended AQI value (0-500 range), or 0 if no valid data
        """
        total_weight = 0.0
        weighted_sum = 0.0

        for source_data, weight in weighted_sources:
            aqi = source_data.aqi
            # Skip None, NaN, and out-of-range values
            if aqi is None:
                continue
            try:
                aqi = float(aqi)
            except (TypeError, ValueError):
                continue
            if math.isnan(aqi) or math.isinf(aqi):
                continue
            if aqi < 0 or aqi > 500:
                logger.warning(f"Skipping out-of-range AQI {aqi} from {source_data.source}")
                continue

            if weight <= 0:
                continue

            weighted_sum += aqi * weight
            total_weight += weight

        if total_weight <= 0:
            return 0

        blended_aqi = weighted_sum / total_weight
        return max(0, min(500, round(blended_aqi)))
    
    def _blend_pollutants(self, weighted_sources: List[tuple]) -> Dict:
        """
        Blend pollutant concentrations using weighted average.

        Args:
            weighted_sources: List of (SourceData, weight) tuples

        Returns:
            Dict of blended pollutant values
        """
        pollutant_data = defaultdict(lambda: {'sum': 0.0, 'weight': 0.0})

        for source_data, weight in weighted_sources:
            if not source_data.pollutants or weight <= 0:
                continue
            for pollutant, value in source_data.pollutants.items():
                if value is None:
                    continue
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isnan(value) or math.isinf(value) or value < 0:
                    continue
                pollutant_data[pollutant]['sum'] += value * weight
                pollutant_data[pollutant]['weight'] += weight

        # Calculate weighted averages
        blended_pollutants = {}
        for pollutant, data in pollutant_data.items():
            if data['weight'] > 0:
                avg_value = data['sum'] / data['weight']
                blended_pollutants[pollutant] = round(avg_value, 2)

        return blended_pollutants
    
    def _get_source_details(self, weighted_sources: List[tuple]) -> List[Dict]:
        """Get detailed information about each source used."""
        details = []
        
        for source_data, weight in weighted_sources:
            details.append({
                'source': source_data.source,
                'weight': round(weight, 3),
                'aqi': source_data.aqi,
                'distance_km': source_data.distance_km,
                'timestamp': source_data.timestamp.isoformat(),
                'quality_level': source_data.quality_level,
                'station_name': source_data.station_name or None,
            })
        
        # Sort by weight (highest first)
        details.sort(key=lambda x: x['weight'], reverse=True)
        
        return details
    
    def _get_from_cache(self, lat: float, lon: float) -> Optional[Dict]:
        """Get blended data from Redis cache (geohash-based key)."""
        return self._cache.get(lat, lon)
    
    def _save_to_cache(self, lat: float, lon: float, result: Dict):
        """Save blended result to Redis cache, with optional DB write-through."""
        self._cache.set(lat, lon, result)

        # Optional DB write-through for analytics
        if getattr(settings, 'CACHE_SETTINGS', {}).get('WRITE_THROUGH_TO_DB', False):
            try:
                from decimal import Decimal
                lat_rounded = round(Decimal(str(lat)), 3)
                lon_rounded = round(Decimal(str(lon)), 3)
                cached_until = timezone.now() + timedelta(seconds=self.cache_ttl)
                BlendedData.objects.update_or_create(
                    lat=lat_rounded, lon=lon_rounded,
                    defaults={
                        'current_aqi': result['current']['aqi'],
                        'category': result['current']['category'],
                        'pollutants': result['current']['pollutants'],
                        'sources': result['current']['sources'],
                        'source_count': len(result['current']['sources']),
                        'cached_until': cached_until,
                    }
                )
            except Exception as e:
                logger.warning(f"DB write-through failed (non-fatal): {e}")
    
    def _get_default_response(self, lat: float, lon: float) -> Dict:
        """Return default response when no data is available."""
        return {
            'lat': float(lat),
            'lon': float(lon),
            'current': {
                'aqi': None,
                'category': 'Unavailable',
                'pollutants': {},
                'sources': [],
                'last_updated': timezone.now().isoformat(),
            },
            'error': 'No fresh air quality data available for this location',
        }
    
    def _log_fusion(
        self,
        lat: float,
        lon: float,
        result_aqi: int = None,
        sources_used: List[str] = None,
        sources_attempted: List[str] = None,
        sources_failed: List[str] = None,
        weight_details: Dict = None,
        execution_time_ms: int = None,
        cache_hit: bool = False,
        error_message: str = ''
    ):
        """Log fusion operation for debugging and analysis."""
        try:
            from decimal import Decimal
            
            FusionLog.objects.create(
                query_lat=Decimal(str(lat)),
                query_lon=Decimal(str(lon)),
                result_aqi=result_aqi,
                sources_used=sources_used or [],
                sources_attempted=sources_attempted or [],
                sources_failed=sources_failed or [],
                fusion_method='weighted_average',
                weight_details=weight_details or {},
                execution_time_ms=execution_time_ms,
                cache_hit=cache_hit,
                has_error=bool(error_message),
                error_message=error_message,
            )
        except Exception as e:
            logger.error(f"Failed to log fusion operation: {e}")
