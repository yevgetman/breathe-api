"""
Utility functions for Air Quality API.
"""
import math
from datetime import datetime, timedelta
from django.utils import timezone


def calculate_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two coordinates using Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


def is_data_fresh(timestamp, max_age_hours=3):
    """
    Check if data timestamp is recent enough.
    
    Args:
        timestamp: datetime object or ISO string
        max_age_hours: maximum acceptable age in hours
        
    Returns:
        bool: True if data is fresh
    """
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return False
    
    if not timezone.is_aware(timestamp):
        timestamp = timezone.make_aware(timestamp)
    
    age = timezone.now() - timestamp
    return age < timedelta(hours=max_age_hours)


def calculate_time_decay_weight(timestamp, preferred_age_minutes=30):
    """
    Calculate a weight based on data age. More recent data gets higher weight.
    
    Args:
        timestamp: datetime object
        preferred_age_minutes: age in minutes where weight = 1.0
        
    Returns:
        float: weight between 0.1 and 1.0
    """
    if not timezone.is_aware(timestamp):
        timestamp = timezone.make_aware(timestamp)
    
    age_minutes = (timezone.now() - timestamp).total_seconds() / 60
    
    if age_minutes <= preferred_age_minutes:
        return 1.0
    
    # Exponential decay: weight = e^(-age/decay_constant)
    decay_constant = preferred_age_minutes * 2
    weight = math.exp(-age_minutes / decay_constant)
    
    # Ensure minimum weight
    return max(0.1, weight)


def apply_purpleair_epa_correction(pm25_raw):
    """
    Apply EPA correction factor to PurpleAir PM2.5 readings.
    Based on EPA's recommended formula for PurpleAir sensors.
    
    Args:
        pm25_raw: raw PM2.5 value from PurpleAir
        
    Returns:
        float: corrected PM2.5 value
    """
    if pm25_raw is None:
        return None
    
    # EPA correction formula (clamped to non-negative)
    if pm25_raw < 30:
        corrected = 0.524 * pm25_raw - 0.0862
    elif pm25_raw < 50:
        corrected = 0.786 * pm25_raw - 5.1327
    elif pm25_raw < 210:
        corrected = 0.69 * pm25_raw + 2.966
    elif pm25_raw < 260:
        corrected = 0.786 * pm25_raw - 5.1327
    else:
        corrected = 0.69 * pm25_raw + 2.966
    return max(0.0, corrected)


def convert_aqi_to_category(aqi, scale='EPA'):
    """
    Convert AQI value to category information.

    Args:
        aqi: AQI value
        scale: 'EPA' or 'AQHI'

    Returns:
        dict: category information or None
    """
    if aqi is None:
        return None

    try:
        aqi = int(aqi)
    except (TypeError, ValueError):
        return None

    from .constants import EPA_AQI_CATEGORIES, AQHI_CATEGORIES

    categories = EPA_AQI_CATEGORIES if scale == 'EPA' else AQHI_CATEGORIES

    for category in categories:
        if category['min_value'] <= aqi <= category['max_value']:
            return category

    return None


def validate_coordinates(lat, lon):
    """
    Validate latitude and longitude values.
    
    Args:
        lat: latitude value
        lon: longitude value
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        lat = float(lat)
        lon = float(lon)
        
        if not (-90 <= lat <= 90):
            return False, "Latitude must be between -90 and 90"
        
        if not (-180 <= lon <= 180):
            return False, "Longitude must be between -180 and 180"
        
        return True, None
        
    except (TypeError, ValueError):
        return False, "Invalid coordinate format"
