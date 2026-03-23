"""
AirVisual (IQAir) adapter for global air quality data.
"""
import logging
from datetime import datetime
from typing import List, Dict

from django.utils import timezone
from apps.core.utils import calculate_distance_km

from .base import BaseAdapter
from .models import SourceData

logger = logging.getLogger(__name__)


class AirVisualAdapter(BaseAdapter):
    """
    Adapter for AirVisual (IQAir) API.
    Provides global air quality data with station and model data.
    """
    
    SOURCE_NAME = "AirVisual"
    SOURCE_CODE = "AIRVISUAL"
    API_BASE_URL = "https://api.airvisual.com/v2/"
    REQUIRES_API_KEY = True
    QUALITY_LEVEL = "model"
    
    def _add_api_key(self, params: Dict, headers: Dict):
        """AirVisual uses 'key' parameter."""
        if self.api_key:
            params['key'] = self.api_key
    
    def fetch_current(self, lat: float, lon: float, **kwargs) -> List[SourceData]:
        """
        Fetch current air quality data for nearest city.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            List of SourceData objects
        """
        # AirVisual API uses nearest_city endpoint with coordinates
        params = {
            'lat': lat,
            'lon': lon,
        }
        
        raw_data = self._make_request('nearest_city', params=params)
        
        if not raw_data or raw_data.get('status') != 'success':
            return []
        
        return self.normalize_data(raw_data, lat, lon)
    
    def normalize_data(self, raw_data: Dict, query_lat: float, query_lon: float) -> List[SourceData]:
        """
        Normalize AirVisual response to SourceData objects.
        """
        if 'data' not in raw_data:
            return []
        
        data = raw_data['data']
        
        try:
            # Get location info
            location = data.get('location', {})
            city = location.get('city', 'Unknown')
            
            # Get coordinates
            coordinates = location.get('coordinates', [])
            if len(coordinates) == 2:
                station_lon = coordinates[0]
                station_lat = coordinates[1]
                distance = calculate_distance_km(
                    query_lat, query_lon,
                    float(station_lat), float(station_lon)
                )
            else:
                station_lat = query_lat
                station_lon = query_lon
                distance = 0.0
            
            # Get current pollution data
            current = data.get('current', {})
            pollution = current.get('pollution', {})
            
            # AirVisual uses US EPA AQI scale
            aqi = pollution.get('aqius')  # US AQI
            if aqi is None or aqi == -1:
                return []
            
            # Get timestamp
            timestamp_str = pollution.get('ts')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if not timezone.is_aware(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                except Exception:
                    timestamp = timezone.now()
            else:
                timestamp = timezone.now()
            
            # Extract main pollutant identifier.
            # Note: AirVisual free tier does NOT provide raw concentrations,
            # only AQI values. We intentionally skip pollutant storage here
            # to avoid blending AQI numbers with actual concentrations from
            # other sources.
            pollutants = {}

            source_data = SourceData(
                source=self.SOURCE_CODE,
                lat=station_lat,
                lon=station_lon,
                timestamp=timestamp,
                aqi=aqi,
                pollutants=pollutants,
                quality_level=self.QUALITY_LEVEL,
                distance_km=round(distance, 2),
                confidence_score=75.0,  # Model-based data
                station_name=city,
            )
            
            return [source_data]
            
        except Exception as e:
            logger.error(f"Error parsing AirVisual data: {e}")
            return []
    
    def fetch_forecast(self, lat: float, lon: float, **kwargs) -> List[Dict]:
        """
        AirVisual free tier doesn't support forecasts.
        This would require a paid plan.
        
        Returns empty list.
        """
        logger.info("AirVisual forecast requires paid plan")
        return []
