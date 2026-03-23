"""
Unit conversion utilities for weather data.
Internal storage is always metric; convert at response time if needed.
"""


def celsius_to_fahrenheit(c):
    """Convert Celsius to Fahrenheit."""
    if c is None:
        return None
    return round(c * 9 / 5 + 32, 1)


def mps_to_mph(mps):
    """Convert meters/second to miles/hour."""
    if mps is None:
        return None
    return round(mps * 2.237, 1)


def mm_to_inches(mm):
    """Convert millimeters to inches."""
    if mm is None:
        return None
    return round(mm / 25.4, 2)


def meters_to_miles(m):
    """Convert meters to miles."""
    if m is None:
        return None
    return round(m / 1609.344, 1)


def hpa_to_inhg(hpa):
    """Convert hectopascals to inches of mercury."""
    if hpa is None:
        return None
    return round(hpa * 0.02953, 2)


def convert_current_to_imperial(current: dict) -> dict:
    """Convert a current weather dict from metric to imperial units."""
    return {
        **current,
        'temperature': celsius_to_fahrenheit(current.get('temperature')),
        'feels_like': celsius_to_fahrenheit(current.get('feels_like')),
        'dew_point': celsius_to_fahrenheit(current.get('dew_point')),
        'pressure': hpa_to_inhg(current.get('pressure')),
        'visibility': meters_to_miles(current.get('visibility')),
        'wind_speed': mps_to_mph(current.get('wind_speed')),
        'wind_gusts': mps_to_mph(current.get('wind_gusts')),
    }


def convert_forecast_to_imperial(forecast: list) -> list:
    """Convert a list of daily forecast dicts from metric to imperial units."""
    converted = []
    for day in forecast:
        converted.append({
            **day,
            'temp_high': celsius_to_fahrenheit(day.get('temp_high')),
            'temp_low': celsius_to_fahrenheit(day.get('temp_low')),
            'feels_like_high': celsius_to_fahrenheit(day.get('feels_like_high')),
            'feels_like_low': celsius_to_fahrenheit(day.get('feels_like_low')),
            'precipitation_sum': mm_to_inches(day.get('precipitation_sum')),
            'wind_speed_max': mps_to_mph(day.get('wind_speed_max')),
            'wind_gusts_max': mps_to_mph(day.get('wind_gusts_max')),
        })
    return converted


def convert_hourly_to_imperial(hourly: list) -> list:
    """Convert a list of hourly forecast dicts from metric to imperial units."""
    converted = []
    for h in hourly:
        converted.append({
            **h,
            'temperature': celsius_to_fahrenheit(h.get('temperature')),
            'feels_like': celsius_to_fahrenheit(h.get('feels_like')),
            'dew_point': celsius_to_fahrenheit(h.get('dew_point')),
            'precipitation': mm_to_inches(h.get('precipitation')),
            'visibility': meters_to_miles(h.get('visibility')),
            'wind_speed': mps_to_mph(h.get('wind_speed')),
            'wind_gusts': mps_to_mph(h.get('wind_gusts')),
        })
    return converted
