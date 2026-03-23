"""
EPA AirNow adapter for U.S. air quality data.
"""
import logging
from datetime import datetime
from typing import List, Dict

from django.utils import timezone
from apps.core.utils import calculate_distance_km

from .base import BaseAdapter
from .models import SourceData

logger = logging.getLogger(__name__)


class AirNowAdapter(BaseAdapter):
    """
    Adapter for EPA AirNow API.
    Official U.S. air quality data with current observations and forecasts.
    """
    
    SOURCE_NAME = "EPA AirNow"
    SOURCE_CODE = "EPA_AIRNOW"
    API_KEY_SETTINGS_NAME = "AIRNOW"
    API_BASE_URL = "https://www.airnowapi.org/aq/"
    REQUIRES_API_KEY = True
    QUALITY_LEVEL = "verified"
    
    def _add_api_key(self, params: Dict, headers: Dict):
        """AirNow uses 'API_KEY' parameter."""
        if self.api_key:
            params['API_KEY'] = self.api_key
            params['format'] = 'application/json'
    
    def fetch_current(self, lat: float, lon: float, **kwargs) -> List[SourceData]:
        """
        Fetch current AQI observations for coordinates.
        
        Args:
            lat: Latitude
            lon: Longitude
            distance: Search distance in miles (default: 25)
            
        Returns:
            List of SourceData objects
        """
        distance = kwargs.get('distance', 25)
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'distance': distance,
        }
        
        raw_data = self._make_request('observation/latLong/current/', params=params)
        
        if not raw_data:
            return []
        
        return self.normalize_data(raw_data, lat, lon)
    
    def fetch_forecast(self, lat: float, lon: float, **kwargs) -> List[Dict]:
        """
        Fetch AQI forecast for coordinates.
        
        Args:
            lat: Latitude
            lon: Longitude
            date: Forecast date (YYYY-MM-DD), defaults to today
            distance: Search distance in miles (default: 25)
            
        Returns:
            List of forecast dictionaries
        """
        distance = kwargs.get('distance', 25)
        date = kwargs.get('date', timezone.now().strftime('%Y-%m-%d'))
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'distance': distance,
            'date': date,
        }
        
        raw_data = self._make_request('forecast/latLong/', params=params)
        
        if not raw_data:
            return []
        
        return self._normalize_forecast(raw_data, lat, lon)
    
    def normalize_data(self, raw_data: Dict, query_lat: float, query_lon: float) -> List[SourceData]:
        """
        Normalize AirNow response to SourceData objects.
        
        AirNow returns a list of observations, one per pollutant.
        We need to group by station and combine pollutants.
        """
        if not isinstance(raw_data, list):
            return []
        
        # Group observations by reporting area
        stations = {}
        
        for observation in raw_data:
            area_name = observation.get('ReportingArea', 'Unknown')
            
            if area_name not in stations:
                stations[area_name] = {
                    'station_name': area_name,
                    'lat': observation.get('Latitude'),
                    'lon': observation.get('Longitude'),
                    'aqi': None,
                    'pollutants': {},
                    'timestamp': observation.get('DateObserved'),
                }
            
            # Get pollutant data
            parameter = observation.get('ParameterName', '').lower()
            aqi_value = observation.get('AQI')
            concentration = observation.get('Value')
            
            # Map parameter names
            pollutant_map = {
                'pm2.5': 'pm25',
                'pm10': 'pm10',
                'o3': 'o3',
                'ozone': 'o3',
                'no2': 'no2',
                'co': 'co',
                'so2': 'so2',
            }
            
            pollutant_key = pollutant_map.get(parameter, parameter)
            
            if pollutant_key in pollutant_map.values():
                stations[area_name]['pollutants'][pollutant_key] = concentration
            
            # Use highest AQI value
            if aqi_value:
                current_aqi = stations[area_name]['aqi']
                if current_aqi is None or aqi_value > current_aqi:
                    stations[area_name]['aqi'] = aqi_value
        
        # Convert to SourceData objects
        source_data_list = []
        
        for station in stations.values():
            # Parse timestamp
            try:
                timestamp_str = f"{station['timestamp']} 00:00:00"
                timestamp = timezone.make_aware(
                    datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                )
            except Exception:
                timestamp = timezone.now()
            
            # Calculate distance
            if station['lat'] and station['lon']:
                distance = calculate_distance_km(
                    query_lat, query_lon,
                    float(station['lat']), float(station['lon'])
                )
            else:
                distance = None
            
            source_data = SourceData(
                source=self.SOURCE_CODE,
                lat=station['lat'] or query_lat,
                lon=station['lon'] or query_lon,
                timestamp=timestamp,
                aqi=station['aqi'],
                pollutants=station['pollutants'],
                quality_level=self.QUALITY_LEVEL,
                distance_km=distance,
                confidence_score=100.0,  # AirNow is verified
                station_name=station['station_name'],
            )
            
            source_data_list.append(source_data)
        
        return source_data_list
    
    def _normalize_forecast(self, raw_data: List, query_lat: float, query_lon: float) -> List[Dict]:
        """Normalize forecast data."""
        if not isinstance(raw_data, list):
            return []
        
        forecasts = []
        
        for item in raw_data:
            try:
                date_str = item.get('DateForecast', '')
                timestamp = timezone.make_aware(
                    datetime.strptime(date_str, '%Y-%m-%d')
                )
                
                forecasts.append({
                    'timestamp': timestamp.isoformat(),
                    'aqi': item.get('AQI'),
                    'category': item.get('Category', {}).get('Name'),
                    'source': self.SOURCE_CODE,
                    'location': item.get('ReportingArea'),
                })
            except Exception as e:
                logger.error(f"Error parsing AirNow forecast: {e}")
                continue
        
        return forecasts
