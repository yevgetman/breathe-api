"""
Location resolution services for geocoding and region detection.
"""
import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError, GeocoderTimedOut

from .models import LocationCache, RegionConfig

logger = logging.getLogger(__name__)


class LocationService:
    """
    Service for resolving coordinates to location information.
    Uses caching to minimize external geocoding API calls.
    """
    
    def __init__(self):
        self.geocoder = Nominatim(user_agent="air-quality-api/1.0")
        self.cache_ttl_seconds = getattr(
            settings,
            'AIR_QUALITY_SETTINGS',
            {}
        ).get('LOCATION_CACHE_TTL', 86400)
        from apps.core.cache import ResponseCache
        precision = getattr(settings, 'CACHE_SETTINGS', {}).get('GEOHASH_PRECISION', 6)
        self._cache = ResponseCache(namespace='loc', default_ttl=self.cache_ttl_seconds, geohash_precision=precision)
    
    def reverse_geocode(self, lat, lon, use_cache=True):
        """
        Reverse geocode coordinates to location information.
        
        Args:
            lat: latitude
            lon: longitude
            use_cache: whether to use cached results
            
        Returns:
            dict: location information
        """
        # Round coordinates for cache key (3 decimal places ≈ 100m precision)
        lat_rounded = round(Decimal(str(lat)), 3)
        lon_rounded = round(Decimal(str(lon)), 3)
        
        # Try cache first
        if use_cache:
            cached = self._get_from_cache(lat_rounded, lon_rounded)
            if cached:
                return cached
        
        # Fetch from geocoding service
        try:
            location_data = self._fetch_geocode(lat, lon)
            
            # Cache the result
            self._save_to_cache(lat_rounded, lon_rounded, location_data)
            
            return location_data
            
        except Exception as e:
            logger.error(f"Geocoding error for ({lat}, {lon}): {e}")
            return self._get_default_location(lat, lon)
    
    def _get_from_cache(self, lat, lon):
        """Get location from Redis cache (geohash-based key)."""
        return self._cache.get(float(lat), float(lon))
    
    def _fetch_geocode(self, lat, lon):
        """Fetch geocoding data from external service."""
        try:
            location = self.geocoder.reverse(
                f"{lat}, {lon}",
                language='en',
                timeout=5
            )
            
            if not location:
                return self._get_default_location(lat, lon)
            
            address = location.raw.get('address', {})
            
            return {
                'lat': float(lat),
                'lon': float(lon),
                'city': self._extract_city(address),
                'region': self._extract_region(address),
                'country': address.get('country_code', 'unknown').upper(),
                'zip_code': address.get('postcode', ''),
                'formatted_address': location.address,
            }
            
        except (GeopyError, GeocoderTimedOut) as e:
            logger.warning(f"Geocoding service error: {e}")
            return self._get_default_location(lat, lon)
    
    def _extract_city(self, address):
        """Extract city name from address components."""
        return (
            address.get('city') or 
            address.get('town') or 
            address.get('village') or 
            address.get('hamlet') or
            address.get('suburb') or
            ''
        )
    
    def _extract_region(self, address):
        """Extract region (state/province) from address components."""
        return (
            address.get('state') or 
            address.get('province') or 
            address.get('region') or
            ''
        )
    
    def _save_to_cache(self, lat, lon, location_data):
        """Save location data to Redis cache, with optional DB write-through."""
        self._cache.set(float(lat), float(lon), location_data)

        if getattr(settings, 'CACHE_SETTINGS', {}).get('WRITE_THROUGH_TO_DB', False):
            try:
                LocationCache.objects.update_or_create(
                    lat=lat, lon=lon,
                    defaults={
                        'city': location_data.get('city', ''),
                        'region': location_data.get('region', ''),
                        'country': location_data.get('country', 'unknown'),
                        'zip_code': location_data.get('zip_code', ''),
                        'formatted_address': location_data.get('formatted_address', ''),
                    }
                )
            except Exception as e:
                logger.warning(f"DB write-through failed (non-fatal): {e}")
    
    def _get_default_location(self, lat, lon):
        """Return default location data when geocoding fails."""
        return {
            'lat': float(lat),
            'lon': float(lon),
            'city': '',
            'region': '',
            'country': 'unknown',
            'zip_code': '',
            'formatted_address': f"{lat}, {lon}",
        }
    
    def get_region_config(self, country_code):
        """
        Get region-specific configuration for data source priorities.
        
        Args:
            country_code: ISO country code (2 letters)
            
        Returns:
            dict: region configuration
        """
        try:
            config = RegionConfig.objects.get(
                country_code=country_code.upper(),
                is_active=True
            )
            return {
                'country_code': config.country_code,
                'country_name': config.country_name,
                'source_priority': config.source_priority,
                'aqi_scale': config.default_aqi_scale,
                'has_official_data': config.has_official_data,
            }
        except RegionConfig.DoesNotExist:
            # Return default configuration
            default_priority = settings.AIR_QUALITY_SETTINGS['SOURCE_PRIORITY']['DEFAULT']
            return {
                'country_code': country_code,
                'country_name': country_code,
                'source_priority': default_priority,
                'aqi_scale': 'EPA',
                'has_official_data': False,
            }
