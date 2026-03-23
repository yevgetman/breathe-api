"""
PurpleAir adapter for community sensor data.
"""
import logging
from datetime import datetime
from typing import List, Dict

from django.utils import timezone
from apps.core.utils import calculate_distance_km, apply_purpleair_epa_correction

from .base import BaseAdapter
from .models import SourceData

logger = logging.getLogger(__name__)


class PurpleAirAdapter(BaseAdapter):
    """
    Adapter for PurpleAir API.
    Community-sourced PM2.5 sensors with real-time data.
    """
    
    SOURCE_NAME = "PurpleAir"
    SOURCE_CODE = "PURPLEAIR"
    API_BASE_URL = "https://api.purpleair.com/v1/"
    REQUIRES_API_KEY = True
    QUALITY_LEVEL = "sensor"
    
    def _add_api_key(self, params: Dict, headers: Dict):
        """PurpleAir uses X-API-Key header."""
        if self.api_key:
            headers['X-API-Key'] = self.api_key
    
    def fetch_current(self, lat: float, lon: float, **kwargs) -> List[SourceData]:
        """
        Fetch current PM2.5 data from nearby PurpleAir sensors.
        
        Args:
            lat: Latitude
            lon: Longitude
            radius_km: Search radius in kilometers (default: 25)
            max_sensors: Maximum number of sensors to return (default: 10)
            
        Returns:
            List of SourceData objects
        """
        radius_km = kwargs.get('radius_km', 25)
        max_sensors = kwargs.get('max_sensors', 10)
        
        # Convert km to miles for nwlat/selng bounding box calculation
        # Approximate: 1 degree ≈ 111 km
        degree_offset = radius_km / 111.0
        
        params = {
            'fields': 'name,latitude,longitude,pm2.5_atm,pm2.5_atm_a,pm2.5_atm_b,confidence,last_seen,humidity,temperature',
            'location_type': '0',  # Outside sensors only
            'max_age': '3600',     # Data within last hour
            'nwlat': lat + degree_offset,
            'nwlng': lon - degree_offset,
            'selat': lat - degree_offset,
            'selng': lon + degree_offset,
        }
        
        raw_data = self._make_request('sensors', params=params)
        
        if not raw_data or 'data' not in raw_data:
            return []
        
        return self.normalize_data(raw_data, lat, lon, max_sensors=max_sensors)
    
    def normalize_data(self, raw_data: Dict, query_lat: float, query_lon: float, max_sensors: int = 10) -> List[SourceData]:
        """
        Normalize PurpleAir response to SourceData objects.
        
        PurpleAir sensors have dual channels (A and B). We average them.
        Apply EPA correction factor if enabled in settings.
        """
        if not raw_data.get('data'):
            return []
        
        fields = raw_data.get('fields', [])
        data = raw_data.get('data', [])
        
        # Create field index map
        field_indices = {field: idx for idx, field in enumerate(fields)}
        
        source_data_list = []
        
        def _get_field(row, field_name, default=None):
            """Safely get a field value from a sensor data row."""
            idx = field_indices.get(field_name)
            if idx is None or idx >= len(row):
                return default
            return row[idx]

        for sensor_data in data:
            try:
                # Extract sensor info
                sensor_name = _get_field(sensor_data, 'name', 'Unknown')
                sensor_lat = _get_field(sensor_data, 'latitude')
                sensor_lon = _get_field(sensor_data, 'longitude')

                if sensor_lat is None or sensor_lon is None:
                    continue

                # Get PM2.5 readings
                pm25_atm = _get_field(sensor_data, 'pm2.5_atm')
                pm25_a = _get_field(sensor_data, 'pm2.5_atm_a')
                pm25_b = _get_field(sensor_data, 'pm2.5_atm_b')
                
                # Average dual channels if both present
                if pm25_a is not None and pm25_b is not None:
                    pm25_raw = (pm25_a + pm25_b) / 2
                else:
                    pm25_raw = pm25_atm or pm25_a or pm25_b
                
                if pm25_raw is None:
                    continue
                
                # Apply EPA correction if enabled
                apply_correction = self.settings.get('PURPLEAIR_EPA_CORRECTION', True)
                if apply_correction:
                    pm25_corrected = apply_purpleair_epa_correction(pm25_raw)
                else:
                    pm25_corrected = pm25_raw
                
                # Get confidence and quality metrics
                confidence = _get_field(sensor_data, 'confidence')
                min_confidence = self.settings.get('PURPLEAIR_MIN_CONFIDENCE', 80)

                if confidence is not None and confidence < min_confidence:
                    continue  # Skip low-confidence sensors

                # Calculate distance
                distance = calculate_distance_km(
                    query_lat, query_lon,
                    float(sensor_lat), float(sensor_lon)
                )

                # Get timestamp
                last_seen = _get_field(sensor_data, 'last_seen')
                if last_seen:
                    timestamp = datetime.fromtimestamp(last_seen, tz=timezone.utc)
                else:
                    timestamp = timezone.now()
                
                # Convert PM2.5 to AQI (EPA formula)
                aqi = self._pm25_to_aqi(pm25_corrected)
                
                source_data = SourceData(
                    source=self.SOURCE_CODE,
                    lat=sensor_lat,
                    lon=sensor_lon,
                    timestamp=timestamp,
                    aqi=aqi,
                    pollutants={'pm25': round(pm25_corrected, 2)},
                    quality_level=self.QUALITY_LEVEL,
                    distance_km=round(distance, 2),
                    confidence_score=confidence,
                    station_name=sensor_name,
                )
                
                source_data_list.append((distance, source_data))
                
            except Exception as e:
                logger.error(f"Error parsing PurpleAir sensor data: {e}")
                continue
        
        # Sort by distance and limit to max_sensors
        source_data_list.sort(key=lambda x: x[0])
        return [sd for _, sd in source_data_list[:max_sensors]]
    
    def _pm25_to_aqi(self, pm25: float) -> int:
        """
        Convert PM2.5 concentration to AQI using EPA breakpoints.
        
        Args:
            pm25: PM2.5 concentration in µg/m³
            
        Returns:
            AQI value
        """
        # EPA PM2.5 breakpoints
        breakpoints = [
            (0.0, 12.0, 0, 50),
            (12.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 150.4, 151, 200),
            (150.5, 250.4, 201, 300),
            (250.5, 350.4, 301, 400),
            (350.5, 500.4, 401, 500),
        ]
        
        for c_low, c_high, aqi_low, aqi_high in breakpoints:
            if c_low <= pm25 <= c_high:
                # Linear interpolation
                aqi = ((aqi_high - aqi_low) / (c_high - c_low)) * (pm25 - c_low) + aqi_low
                return round(aqi)
        
        # If beyond range, return max
        if pm25 > 500.4:
            return 500
        
        return 0
