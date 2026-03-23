"""
Tests for API views: input validation, error responses, edge cases.
"""
import pytest
from unittest.mock import patch, MagicMock

from django.test import RequestFactory
from rest_framework.test import APIRequestFactory


@pytest.mark.django_db
class TestAirQualityViewValidation:
    """Tests for AirQualityView input validation."""

    def _get_view(self):
        from apps.api.views import AirQualityView
        return AirQualityView.as_view()

    def test_missing_lat_lon_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/air-quality/')
        response = self._get_view()(request)
        assert response.status_code == 400
        assert 'lat and lon' in response.data['error']

    def test_missing_lon_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/air-quality/', {'lat': '34.05'})
        response = self._get_view()(request)
        assert response.status_code == 400

    def test_non_numeric_lat_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/air-quality/', {'lat': 'abc', 'lon': '-118.24'})
        response = self._get_view()(request)
        assert response.status_code == 400
        assert 'Invalid coordinate' in response.data['error']

    def test_out_of_range_lat_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/air-quality/', {'lat': '91', 'lon': '-118.24'})
        response = self._get_view()(request)
        assert response.status_code == 400
        assert 'Latitude' in response.data['error']

    def test_out_of_range_lon_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/air-quality/', {'lat': '34.05', 'lon': '181'})
        response = self._get_view()(request)
        assert response.status_code == 400
        assert 'Longitude' in response.data['error']

    def test_invalid_radius_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/air-quality/', {
            'lat': '34.05', 'lon': '-118.24', 'radius_km': 'abc'
        })
        response = self._get_view()(request)
        assert response.status_code == 400
        assert 'radius_km' in response.data['error'].lower()

    def test_negative_radius_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/air-quality/', {
            'lat': '34.05', 'lon': '-118.24', 'radius_km': '-5'
        })
        response = self._get_view()(request)
        assert response.status_code == 400

    def test_radius_capped_at_100(self):
        """Valid large radius should be capped, not rejected."""
        factory = APIRequestFactory()
        request = factory.get('/api/v1/air-quality/', {
            'lat': '34.05', 'lon': '-118.24', 'radius_km': '200'
        })

        mock_result = {
            'lat': 34.05,
            'lon': -118.24,
            'current': {
                'aqi': 50,
                'category': 'Good',
                'pollutants': {},
                'sources': [],
                'last_updated': '2024-01-01T00:00:00Z',
            },
        }

        with patch('apps.api.views.AirQualityOrchestrator') as MockOrch:
            instance = MockOrch.return_value
            instance.get_air_quality.return_value = mock_result
            response = self._get_view()(request)

        # Should succeed (radius capped to 100, not rejected)
        assert response.status_code == 200


@pytest.mark.django_db
class TestHealthAdviceViewValidation:

    def _get_view(self):
        from apps.api.views import HealthAdviceView
        return HealthAdviceView.as_view()

    def test_missing_aqi_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/health-advice/')
        response = self._get_view()(request)
        assert response.status_code == 400

    def test_non_numeric_aqi_returns_400(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/health-advice/', {'aqi': 'bad'})
        response = self._get_view()(request)
        assert response.status_code == 400


class TestConvertAqiToCategory:
    """Tests for convert_aqi_to_category edge cases."""

    def test_none_returns_none(self):
        from apps.core.utils import convert_aqi_to_category
        assert convert_aqi_to_category(None) is None

    def test_string_aqi_works(self):
        from apps.core.utils import convert_aqi_to_category
        result = convert_aqi_to_category('50')
        assert result is not None
        assert result['category'] == 'Good'

    def test_invalid_string_returns_none(self):
        from apps.core.utils import convert_aqi_to_category
        assert convert_aqi_to_category('not-a-number') is None

    def test_good_category(self):
        from apps.core.utils import convert_aqi_to_category
        result = convert_aqi_to_category(25)
        assert result['category'] == 'Good'

    def test_moderate_category(self):
        from apps.core.utils import convert_aqi_to_category
        result = convert_aqi_to_category(75)
        assert result['category'] == 'Moderate'

    def test_out_of_range_returns_none(self):
        from apps.core.utils import convert_aqi_to_category
        assert convert_aqi_to_category(600) is None
