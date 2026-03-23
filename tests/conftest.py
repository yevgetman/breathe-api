"""
Shared test fixtures for the air quality API test suite.
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from django.utils import timezone


@pytest.fixture
def sample_source_data():
    """Create a SourceData instance (unsaved) for testing."""
    from apps.adapters.models import SourceData

    return SourceData(
        source='EPA_AIRNOW',
        lat=Decimal('34.050'),
        lon=Decimal('-118.240'),
        timestamp=timezone.now() - timedelta(minutes=10),
        aqi=75,
        pollutants={'pm25': 18.5, 'o3': 42.0},
        quality_level='verified',
        distance_km=5.0,
        confidence_score=100.0,
        station_name='Los Angeles - North Main Street',
    )


@pytest.fixture
def make_source_data():
    """Factory fixture to create SourceData instances with custom values."""
    from apps.adapters.models import SourceData

    def _make(source='EPA_AIRNOW', aqi=50, distance_km=5.0,
              confidence_score=100.0, quality_level='verified',
              pollutants=None, timestamp=None, **kwargs):
        return SourceData(
            source=source,
            lat=Decimal('34.050'),
            lon=Decimal('-118.240'),
            timestamp=timestamp or (timezone.now() - timedelta(minutes=10)),
            aqi=aqi,
            pollutants=pollutants or {'pm25': 12.0},
            quality_level=quality_level,
            distance_km=distance_km,
            confidence_score=confidence_score,
            station_name=kwargs.get('station_name', 'Test Station'),
        )
    return _make


@pytest.fixture
def mock_adapter_settings():
    """Return a standard AIR_QUALITY_SETTINGS dict for tests."""
    return {
        'RESPONSE_CACHE_TTL': 600,
        'LOCATION_CACHE_TTL': 86400,
        'DEFAULT_SEARCH_RADIUS_KM': 25,
        'MAX_SEARCH_RADIUS_KM': 100,
        'MAX_DATA_AGE_HOURS': 3,
        'PREFERRED_DATA_AGE_MINUTES': 30,
        'SOURCE_WEIGHTS': {
            'EPA_AIRNOW': 1.0,
            'PURPLEAIR': 0.85,
            'OPENWEATHERMAP': 0.7,
            'AIRVISUAL': 0.75,
            'WAQI': 0.65,
        },
        'SOURCE_PRIORITY': {
            'US': ['EPA_AIRNOW', 'PURPLEAIR', 'OPENWEATHERMAP', 'AIRVISUAL', 'WAQI'],
            'DEFAULT': ['OPENWEATHERMAP', 'AIRVISUAL', 'WAQI', 'PURPLEAIR'],
        },
        'PURPLEAIR_EPA_CORRECTION': True,
        'PURPLEAIR_MIN_CONFIDENCE': 80,
        'MAX_RETRIES': 1,
        'RETRY_BACKOFF_FACTOR': 0,
        'REQUEST_TIMEOUT': 2,
    }
