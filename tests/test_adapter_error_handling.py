"""
Tests for adapter error handling: JSON parsing, API key redaction, request failures.
"""
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

import requests

from apps.adapters.base import BaseAdapter


class ConcreteAdapter(BaseAdapter):
    """Minimal concrete adapter for testing base class behavior."""
    SOURCE_NAME = "TestSource"
    SOURCE_CODE = "TEST"
    API_BASE_URL = "https://api.test.example.com/"
    REQUIRES_API_KEY = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60

    def fetch_current(self, lat, lon, **kwargs):
        return []


class TestJSONDecodeHandling:

    @patch.object(ConcreteAdapter, '_get_api_key', return_value='test-key')
    @patch.object(ConcreteAdapter, '_log_response')
    @patch.object(ConcreteAdapter, '_update_status')
    def test_malformed_json_returns_none(self, mock_status, mock_log, mock_key):
        adapter = ConcreteAdapter()

        # Mock a response that returns HTML instead of JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch.object(adapter.session, 'request', return_value=mock_response):
            result = adapter._make_request('some/endpoint')

        assert result is None
        # Should have been called with success=False
        mock_status.assert_called_once()
        call_kwargs = mock_status.call_args
        assert call_kwargs[1]['success'] is False
        assert 'Invalid JSON' in call_kwargs[1]['error_message']

    @patch.object(ConcreteAdapter, '_get_api_key', return_value='test-key')
    @patch.object(ConcreteAdapter, '_log_response')
    @patch.object(ConcreteAdapter, '_update_status')
    def test_valid_json_returned_normally(self, mock_status, mock_log, mock_key):
        adapter = ConcreteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {'data': [1, 2, 3]}

        with patch.object(adapter.session, 'request', return_value=mock_response):
            result = adapter._make_request('some/endpoint')

        assert result == {'data': [1, 2, 3]}
        mock_status.assert_called_with(success=True)


class TestParamRedaction:

    @patch.object(ConcreteAdapter, '_get_api_key', return_value='secret-api-key-123')
    def test_redact_params_replaces_sensitive_keys(self, mock_key):
        adapter = ConcreteAdapter()

        params = {
            'lat': 34.05,
            'lon': -118.24,
            'API_KEY': 'secret-api-key-123',
            'token': 'another-secret',
            'key': 'yet-another',
            'appid': 'owm-key',
        }

        redacted = adapter._redact_params(params)

        assert redacted['lat'] == 34.05
        assert redacted['lon'] == -118.24
        assert redacted['API_KEY'] == '***REDACTED***'
        assert redacted['token'] == '***REDACTED***'
        assert redacted['key'] == '***REDACTED***'
        assert redacted['appid'] == '***REDACTED***'

    @patch.object(ConcreteAdapter, '_get_api_key', return_value=None)
    def test_redact_params_handles_empty(self, mock_key):
        adapter = ConcreteAdapter()
        assert adapter._redact_params({}) == {}
        assert adapter._redact_params(None) is None


class TestErrorSanitization:

    @patch.object(ConcreteAdapter, '_get_api_key', return_value='my-secret-key-abc')
    def test_sanitize_error_removes_api_key(self, mock_key):
        adapter = ConcreteAdapter()

        error_msg = "ConnectionError: https://api.test.com/data?key=my-secret-key-abc&lat=34"
        sanitized = adapter._sanitize_error(error_msg)

        assert 'my-secret-key-abc' not in sanitized
        assert '***REDACTED***' in sanitized

    @patch.object(ConcreteAdapter, '_get_api_key', return_value=None)
    def test_sanitize_error_handles_no_key(self, mock_key):
        adapter = ConcreteAdapter()
        error_msg = "ConnectionError: timeout"
        assert adapter._sanitize_error(error_msg) == error_msg


class TestRequestFailures:

    @patch.object(ConcreteAdapter, '_get_api_key', return_value='test-key')
    @patch.object(ConcreteAdapter, '_log_response')
    @patch.object(ConcreteAdapter, '_update_status')
    def test_timeout_returns_none_and_records_failure(self, mock_status, mock_log, mock_key):
        adapter = ConcreteAdapter()

        with patch.object(
            adapter.session, 'request',
            side_effect=requests.exceptions.Timeout("Connection timed out")
        ):
            result = adapter._make_request('test/endpoint')

        assert result is None
        assert adapter.circuit_breaker._failure_count == 1

    @patch.object(ConcreteAdapter, '_get_api_key', return_value='test-key')
    @patch.object(ConcreteAdapter, '_log_response')
    @patch.object(ConcreteAdapter, '_update_status')
    def test_connection_error_returns_none(self, mock_status, mock_log, mock_key):
        adapter = ConcreteAdapter()

        with patch.object(
            adapter.session, 'request',
            side_effect=requests.exceptions.ConnectionError("DNS resolution failed")
        ):
            result = adapter._make_request('test/endpoint')

        assert result is None

    @patch.object(ConcreteAdapter, '_get_api_key', return_value='test-key')
    @patch.object(ConcreteAdapter, '_log_response')
    @patch.object(ConcreteAdapter, '_update_status')
    def test_http_500_returns_none(self, mock_status, mock_log, mock_key):
        adapter = ConcreteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error", response=mock_response
        )

        with patch.object(adapter.session, 'request', return_value=mock_response):
            result = adapter._make_request('test/endpoint')

        assert result is None
