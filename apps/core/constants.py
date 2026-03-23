"""
Constants and lookup data for Air Quality API.
"""

# EPA AQI Categories (US Standard)
EPA_AQI_CATEGORIES = [
    {
        'scale': 'EPA',
        'min_value': 0,
        'max_value': 50,
        'category': 'Good',
        'color_hex': '#00E400',
        'health_message': 'Air quality is satisfactory, and air pollution poses little or no risk.',
        'sensitive_groups': '',
    },
    {
        'scale': 'EPA',
        'min_value': 51,
        'max_value': 100,
        'category': 'Moderate',
        'color_hex': '#FFFF00',
        'health_message': 'Air quality is acceptable. However, there may be a risk for some people, particularly those who are unusually sensitive to air pollution.',
        'sensitive_groups': 'Unusually sensitive people',
    },
    {
        'scale': 'EPA',
        'min_value': 101,
        'max_value': 150,
        'category': 'Unhealthy for Sensitive Groups',
        'color_hex': '#FF7E00',
        'health_message': 'Members of sensitive groups may experience health effects. The general public is less likely to be affected.',
        'sensitive_groups': 'Children, elderly, people with lung disease, people with heart disease',
    },
    {
        'scale': 'EPA',
        'min_value': 151,
        'max_value': 200,
        'category': 'Unhealthy',
        'color_hex': '#FF0000',
        'health_message': 'Some members of the general public may experience health effects; members of sensitive groups may experience more serious health effects.',
        'sensitive_groups': 'Everyone, especially sensitive groups',
    },
    {
        'scale': 'EPA',
        'min_value': 201,
        'max_value': 300,
        'category': 'Very Unhealthy',
        'color_hex': '#99004C',
        'health_message': 'Health alert: The risk of health effects is increased for everyone.',
        'sensitive_groups': 'Everyone',
    },
    {
        'scale': 'EPA',
        'min_value': 301,
        'max_value': 500,
        'category': 'Hazardous',
        'color_hex': '#7E0023',
        'health_message': 'Health warning of emergency conditions: everyone is more likely to be affected.',
        'sensitive_groups': 'Everyone',
    },
]

# Canadian AQHI Categories
AQHI_CATEGORIES = [
    {
        'scale': 'AQHI',
        'min_value': 1,
        'max_value': 3,
        'category': 'Low Risk',
        'color_hex': '#00CCFF',
        'health_message': 'Enjoy your usual outdoor activities.',
        'sensitive_groups': '',
    },
    {
        'scale': 'AQHI',
        'min_value': 4,
        'max_value': 6,
        'category': 'Moderate Risk',
        'color_hex': '#FFFF00',
        'health_message': 'Consider reducing or rescheduling strenuous activities outdoors if you are experiencing symptoms.',
        'sensitive_groups': 'People with heart or breathing problems',
    },
    {
        'scale': 'AQHI',
        'min_value': 7,
        'max_value': 10,
        'category': 'High Risk',
        'color_hex': '#FF7E00',
        'health_message': 'Reduce or reschedule strenuous activities outdoors. Children and the elderly should also take it easy.',
        'sensitive_groups': 'Children, elderly, people with heart or lung conditions',
    },
    {
        'scale': 'AQHI',
        'min_value': 10,
        'max_value': 15,
        'category': 'Very High Risk',
        'color_hex': '#FF0000',
        'health_message': 'Avoid strenuous activities outdoors. Children and the elderly should also avoid outdoor physical exertion.',
        'sensitive_groups': 'Everyone, especially sensitive groups',
    },
]

# Pollutant names and properties
POLLUTANTS = {
    'pm25': {
        'name': 'PM2.5',
        'full_name': 'Fine Particulate Matter',
        'unit': 'µg/m³',
        'description': 'Particles smaller than 2.5 micrometers',
    },
    'pm10': {
        'name': 'PM10',
        'full_name': 'Particulate Matter',
        'unit': 'µg/m³',
        'description': 'Particles smaller than 10 micrometers',
    },
    'o3': {
        'name': 'O₃',
        'full_name': 'Ozone',
        'unit': 'ppb',
        'description': 'Ground-level ozone',
    },
    'no2': {
        'name': 'NO₂',
        'full_name': 'Nitrogen Dioxide',
        'unit': 'ppb',
        'description': 'Nitrogen dioxide',
    },
    'so2': {
        'name': 'SO₂',
        'full_name': 'Sulfur Dioxide',
        'unit': 'ppb',
        'description': 'Sulfur dioxide',
    },
    'co': {
        'name': 'CO',
        'full_name': 'Carbon Monoxide',
        'unit': 'ppm',
        'description': 'Carbon monoxide',
    },
}

# Source quality levels
QUALITY_LEVELS = [
    'verified',    # Government-verified station data
    'model',       # Atmospheric model data
    'sensor',      # Community sensor (calibrated)
    'estimated',   # Interpolated or estimated
]

# Data source codes
DATA_SOURCES = {
    'EPA_AIRNOW': 'EPA AirNow',
    'ECCC_AQHI': 'ECCC AQHI',
    'PURPLEAIR': 'PurpleAir',
    'OPENWEATHERMAP': 'OpenWeatherMap',
    'OPEN_METEO_AQ': 'Open-Meteo Air Quality',
    'WAQI': 'WAQI',
    'AIRVISUAL': 'AirVisual (IQAir)',
    'BREEZOMETER': 'BreezoMeter',
    'IQAIR': 'IQAir',
    'OPENAQ': 'OpenAQ',
}

# Pollen type groups: maps Open-Meteo API field names to display categories
POLLEN_TYPE_GROUPS = {
    'tree': ['alder_pollen', 'birch_pollen', 'olive_pollen'],
    'grass': ['grass_pollen'],
    'weed': ['mugwort_pollen', 'ragweed_pollen'],
}

# Pollen level thresholds (grains/m³) — levels: none, low, moderate, high, very_high
# Based on NAB (National Allergy Bureau) guidelines adapted for Open-Meteo scale
POLLEN_THRESHOLDS = {
    'tree': [
        (0, 'none'),
        (15, 'low'),
        (90, 'moderate'),
        (1500, 'high'),
        (float('inf'), 'very_high'),
    ],
    'grass': [
        (0, 'none'),
        (5, 'low'),
        (20, 'moderate'),
        (200, 'high'),
        (float('inf'), 'very_high'),
    ],
    'weed': [
        (0, 'none'),
        (10, 'low'),
        (50, 'moderate'),
        (500, 'high'),
        (float('inf'), 'very_high'),
    ],
}

# Display names for individual pollen types
POLLEN_DISPLAY_NAMES = {
    'alder_pollen': 'Alder',
    'birch_pollen': 'Birch',
    'olive_pollen': 'Olive',
    'grass_pollen': 'Grass',
    'mugwort_pollen': 'Mugwort',
    'ragweed_pollen': 'Ragweed',
}
