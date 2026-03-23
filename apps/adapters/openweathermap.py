"""
OpenWeatherMap adapter for global air quality data and forecasts.
"""
import logging
from datetime import datetime
from typing import List, Dict

from django.utils import timezone

from .base import BaseAdapter
from .models import SourceData

logger = logging.getLogger(__name__)


class OpenWeatherMapAdapter(BaseAdapter):
    """
    Adapter for OpenWeatherMap Air Pollution API.
    Provides global coverage with current data and 4-day forecasts.
    """
    
    SOURCE_NAME = "OpenWeatherMap"
    SOURCE_CODE = "OPENWEATHERMAP"
    API_BASE_URL = "https://api.openweathermap.org/data/2.5/"
    REQUIRES_API_KEY = True
    QUALITY_LEVEL = "model"
    
    def _add_api_key(self, params: Dict, headers: Dict):
        """OpenWeatherMap uses 'appid' parameter."""
        if self.api_key:
            params['appid'] = self.api_key
    
    def fetch_current(self, lat: float, lon: float, **kwargs) -> List[SourceData]:
        """
        Fetch current air pollution data.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            List of SourceData objects
        """
        params = {
            'lat': lat,
            'lon': lon,
        }
        
        raw_data = self._make_request('air_pollution', params=params)
        
        if not raw_data:
            return []
        
        return self.normalize_data(raw_data, lat, lon)
    
    def fetch_forecast(self, lat: float, lon: float, **kwargs) -> List[Dict]:
        """
        Fetch 4-day hourly air pollution forecast.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            List of forecast dictionaries
        """
        params = {
            'lat': lat,
            'lon': lon,
        }
        
        raw_data = self._make_request('air_pollution/forecast', params=params)
        
        if not raw_data:
            return []
        
        return self._normalize_forecast(raw_data, lat, lon)
    
    def normalize_data(self, raw_data: Dict, query_lat: float, query_lon: float) -> List[SourceData]:
        """
        Normalize OpenWeatherMap response to SourceData objects.
        
        OpenWeatherMap provides AQI on a 1-5 scale which we convert to EPA scale.
        """
        if 'list' not in raw_data or not raw_data['list']:
            return []
        
        source_data_list = []
        
        for item in raw_data['list']:
            try:
                # Get timestamp
                dt = item.get('dt')
                if dt:
                    timestamp = datetime.fromtimestamp(dt, tz=timezone.utc)
                else:
                    timestamp = timezone.now()

                # Get air quality data
                aqi_1_5 = item.get('main', {}).get('aqi')  # 1-5 scale
                components = item.get('components', {})
                
                # Convert OWM's 1-5 scale to EPA 0-500 scale (approximate)
                aqi = self._convert_owm_aqi_to_epa(aqi_1_5)
                
                # Extract pollutants
                pollutants = {
                    'co': components.get('co'),      # CO in μg/m³
                    'no2': components.get('no2'),    # NO2 in μg/m³
                    'o3': components.get('o3'),      # O3 in μg/m³
                    'so2': components.get('so2'),    # SO2 in μg/m³
                    'pm25': components.get('pm2_5'), # PM2.5 in μg/m³
                    'pm10': components.get('pm10'),  # PM10 in μg/m³
                }
                
                # Remove None values
                pollutants = {k: v for k, v in pollutants.items() if v is not None}
                
                source_data = SourceData(
                    source=self.SOURCE_CODE,
                    lat=query_lat,
                    lon=query_lon,
                    timestamp=timestamp,
                    aqi=aqi,
                    pollutants=pollutants,
                    quality_level=self.QUALITY_LEVEL,
                    distance_km=0.0,  # OWM provides data for exact coordinates
                    confidence_score=75.0,  # Model-based data
                )
                
                source_data_list.append(source_data)
                
            except Exception as e:
                logger.error(f"Error parsing OpenWeatherMap data: {e}")
                continue
        
        return source_data_list
    
    def _normalize_forecast(self, raw_data: Dict, query_lat: float, query_lon: float) -> List[Dict]:
        """Normalize forecast data."""
        if 'list' not in raw_data or not raw_data['list']:
            return []
        
        forecasts = []
        
        for item in raw_data['list']:
            try:
                dt = item.get('dt')
                if dt:
                    timestamp = datetime.fromtimestamp(dt, tz=timezone.utc)
                else:
                    continue
                
                aqi_1_5 = item.get('main', {}).get('aqi')
                aqi = self._convert_owm_aqi_to_epa(aqi_1_5)
                
                components = item.get('components', {})
                pollutants = {
                    'pm25': components.get('pm2_5'),
                    'pm10': components.get('pm10'),
                    'o3': components.get('o3'),
                    'no2': components.get('no2'),
                    'co': components.get('co'),
                    'so2': components.get('so2'),
                }
                
                forecasts.append({
                    'timestamp': timestamp.isoformat(),
                    'aqi': aqi,
                    'pollutants': pollutants,
                    'source': self.SOURCE_CODE,
                })
                
            except Exception as e:
                logger.error(f"Error parsing OpenWeatherMap forecast: {e}")
                continue
        
        return forecasts
    
    def _convert_owm_aqi_to_epa(self, aqi_1_5: int) -> int:
        """
        Convert OpenWeatherMap's 1-5 AQI scale to EPA 0-500 scale.
        
        OWM Scale:
        1 = Good
        2 = Fair
        3 = Moderate
        4 = Poor
        5 = Very Poor
        
        Approximate EPA conversion:
        """
        conversion_map = {
            1: 25,   # Good: 0-50
            2: 75,   # Fair: 51-100
            3: 125,  # Moderate: 101-150
            4: 175,  # Poor: 151-200
            5: 250,  # Very Poor: 201-300
        }
        
        return conversion_map.get(aqi_1_5, 0)
