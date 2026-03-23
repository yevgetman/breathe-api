"""
Tests for weather endpoints, adapters, orchestrator, and unit conversions.
"""
import pytest
from unittest.mock import patch, MagicMock

from rest_framework.test import APIRequestFactory

from apps.weather.utils import (
    celsius_to_fahrenheit,
    mps_to_mph,
    mm_to_inches,
    meters_to_miles,
    hpa_to_inhg,
    convert_current_to_imperial,
    convert_forecast_to_imperial,
)


# ---------------------------------------------------------------------------
# Unit conversion tests
# ---------------------------------------------------------------------------

class TestUnitConversions:

    def test_celsius_to_fahrenheit(self):
        assert celsius_to_fahrenheit(0) == 32.0
        assert celsius_to_fahrenheit(100) == 212.0
        assert celsius_to_fahrenheit(-40) == -40.0

    def test_celsius_to_fahrenheit_none(self):
        assert celsius_to_fahrenheit(None) is None

    def test_mps_to_mph(self):
        result = mps_to_mph(1.0)
        assert 2.2 <= result <= 2.3

    def test_mps_to_mph_none(self):
        assert mps_to_mph(None) is None

    def test_mm_to_inches(self):
        assert mm_to_inches(25.4) == 1.0

    def test_mm_to_inches_none(self):
        assert mm_to_inches(None) is None

    def test_meters_to_miles(self):
        result = meters_to_miles(1609.344)
        assert result == 1.0

    def test_meters_to_miles_none(self):
        assert meters_to_miles(None) is None

    def test_hpa_to_inhg(self):
        result = hpa_to_inhg(1013.25)
        assert 29.9 <= result <= 30.0

    def test_hpa_to_inhg_none(self):
        assert hpa_to_inhg(None) is None

    def test_convert_current_to_imperial(self):
        current = {
            'temperature': 20.0,
            'feels_like': 18.0,
            'dew_point': 10.0,
            'pressure': 1013.25,
            'visibility': 10000,
            'wind_speed': 5.0,
            'wind_gusts': 8.0,
            'humidity': 50,
            'weather_description': 'Clear',
        }
        result = convert_current_to_imperial(current)
        assert result['temperature'] == 68.0
        assert result['humidity'] == 50  # unchanged
        assert result['weather_description'] == 'Clear'  # unchanged

    def test_convert_forecast_to_imperial(self):
        forecast = [{
            'date': '2026-03-23',
            'temp_high': 25.0,
            'temp_low': 15.0,
            'feels_like_high': 24.0,
            'feels_like_low': 14.0,
            'precipitation_sum': 5.0,
            'wind_speed_max': 10.0,
            'wind_gusts_max': 15.0,
            'weather_description': 'Rain',
        }]
        result = convert_forecast_to_imperial(forecast)
        assert result[0]['temp_high'] == 77.0
        assert result[0]['weather_description'] == 'Rain'


# ---------------------------------------------------------------------------
# Open-Meteo adapter tests
# ---------------------------------------------------------------------------

class TestOpenMeteoAdapter:

    def test_requires_no_api_key(self):
        from apps.adapters.open_meteo import OpenMeteoWeatherAdapter
        adapter = OpenMeteoWeatherAdapter()
        assert adapter.REQUIRES_API_KEY is False
        assert adapter.api_key is None

    def test_is_available_without_key(self):
        from apps.adapters.open_meteo import OpenMeteoWeatherAdapter
        adapter = OpenMeteoWeatherAdapter()
        # Should be available even without an API key
        assert adapter.is_available() is True

    def test_normalize_handles_empty_response(self):
        from apps.adapters.open_meteo import OpenMeteoWeatherAdapter
        adapter = OpenMeteoWeatherAdapter()
        result = adapter._normalize({}, 34.05, -118.24)
        assert result['current']['temperature'] is None
        assert result['daily_forecast'] == []

    def test_dew_point_calculation(self):
        from apps.adapters.open_meteo import OpenMeteoWeatherAdapter
        dp = OpenMeteoWeatherAdapter._calculate_dew_point(20.0, 50.0)
        assert dp is not None
        assert 8.0 <= dp <= 10.0

    def test_dew_point_none_inputs(self):
        from apps.adapters.open_meteo import OpenMeteoWeatherAdapter
        assert OpenMeteoWeatherAdapter._calculate_dew_point(None, 50.0) is None
        assert OpenMeteoWeatherAdapter._calculate_dew_point(20.0, None) is None

    def test_wmo_code_mapping(self):
        from apps.adapters.open_meteo import _decode_weather_code
        result = _decode_weather_code(0)
        assert result['description'] == 'Clear sky'
        assert result['icon'] == 'clear-day'

    def test_wmo_unknown_code(self):
        from apps.adapters.open_meteo import _decode_weather_code
        result = _decode_weather_code(999)
        assert result['description'] == 'Unknown'

    def test_wmo_none_code(self):
        from apps.adapters.open_meteo import _decode_weather_code
        result = _decode_weather_code(None)
        assert result['description'] == 'Unknown'


# ---------------------------------------------------------------------------
# OWM weather adapter tests
# ---------------------------------------------------------------------------

class TestOWMWeatherAdapter:

    def test_reuses_openweathermap_key(self):
        from apps.adapters.openweathermap_weather import OWMWeatherAdapter
        assert OWMWeatherAdapter.API_KEY_SETTINGS_NAME == "OPENWEATHERMAP"

    def test_dew_point_calculation(self):
        from apps.adapters.openweathermap_weather import OWMWeatherAdapter
        dp = OWMWeatherAdapter._calculate_dew_point(25.0, 60.0)
        assert dp is not None
        assert 15.0 <= dp <= 18.0

    def test_dew_point_zero_humidity(self):
        from apps.adapters.openweathermap_weather import OWMWeatherAdapter
        assert OWMWeatherAdapter._calculate_dew_point(20.0, 0) is None


# ---------------------------------------------------------------------------
# Weather view tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestWeatherViewValidation:

    def _get_view(self):
        from apps.weather.views import WeatherView
        return WeatherView.as_view()

    def test_missing_lat_lon_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/weather/')
        response = self._get_view()(request)
        assert response.status_code == 400
        assert 'lat and lon' in response.data['error']

    def test_invalid_coordinates_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/weather/', {'lat': 'abc', 'lon': '0'})
        response = self._get_view()(request)
        assert response.status_code == 400

    def test_out_of_range_lat_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/weather/', {'lat': '91', 'lon': '0'})
        response = self._get_view()(request)
        assert response.status_code == 400

    def test_invalid_units_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/weather/', {
            'lat': '34.05', 'lon': '-118.24', 'units': 'kelvin'
        })
        response = self._get_view()(request)
        assert response.status_code == 400
        assert 'units' in response.data['error']

    def test_valid_request_returns_200(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/weather/', {
            'lat': '34.05', 'lon': '-118.24'
        })

        mock_result = {
            'location': {
                'lat': 34.05, 'lon': -118.24,
                'city': 'Los Angeles', 'region': 'California',
                'country': 'US',
            },
            'current': {
                'temperature': 22.0, 'feels_like': 21.0, 'dew_point': 14.0,
                'humidity': 55, 'pressure': 1013.0, 'visibility': 10000,
                'cloud_cover': 20, 'uv_index': 5.0,
                'wind_speed': 3.0, 'wind_direction': 180, 'wind_gusts': 5.0,
                'weather_description': 'Partly cloudy',
                'weather_icon': 'partly-cloudy-day',
                'sunrise': '2026-03-23T06:42:00-07:00',
                'sunset': '2026-03-23T19:12:00-07:00',
                'observation_time': '2026-03-23T14:00:00-07:00',
            },
            'daily_forecast': [],
            'source': 'OPEN_METEO',
            'units': 'metric',
        }

        with patch('apps.weather.views.WeatherOrchestrator') as MockOrch:
            MockOrch.return_value.get_weather.return_value = mock_result
            response = self._get_view()(request)

        assert response.status_code == 200
