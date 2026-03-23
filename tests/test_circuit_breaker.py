"""
Tests for the CircuitBreaker class and its integration with BaseAdapter.
"""
import time
import pytest
from unittest.mock import patch, MagicMock

from apps.adapters.base import CircuitBreaker


class TestCircuitBreaker:
    """Unit tests for the CircuitBreaker state machine."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert cb.allow_request() is False

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED
        # Need 3 more failures after reset to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED

    def test_transitions_to_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.state == CircuitBreaker.HALF_OPEN
        assert cb.allow_request() is True

    def test_half_open_closes_on_success(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitBreaker.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED

    def test_half_open_reopens_on_failure(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitBreaker.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN


class TestBaseAdapterCircuitBreaker:
    """Integration tests for circuit breaker within the adapter."""

    def test_make_request_skips_when_circuit_open(self):
        """When circuit is open, _make_request should return None immediately."""
        from apps.adapters.airnow import AirNowAdapter

        with patch.object(AirNowAdapter, '_get_api_key', return_value='test-key'):
            adapter = AirNowAdapter()

        # Force circuit open
        for _ in range(adapter.CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            adapter.circuit_breaker.record_failure()

        assert adapter.circuit_breaker.state == CircuitBreaker.OPEN

        # Should return None without making any HTTP call
        result = adapter._make_request('test/endpoint')
        assert result is None

    def test_is_available_returns_false_when_circuit_open(self):
        from apps.adapters.airnow import AirNowAdapter

        with patch.object(AirNowAdapter, '_get_api_key', return_value='test-key'):
            adapter = AirNowAdapter()

        for _ in range(adapter.CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            adapter.circuit_breaker.record_failure()

        assert adapter.is_available() is False
