"""
Tests for core utility functions.
"""
import pytest
from datetime import timedelta
from django.utils import timezone

from apps.core.utils import (
    calculate_distance_km,
    is_data_fresh,
    calculate_time_decay_weight,
    apply_purpleair_epa_correction,
    validate_coordinates,
)


class TestCalculateDistance:

    def test_same_point_zero_distance(self):
        assert calculate_distance_km(34.05, -118.24, 34.05, -118.24) == 0.0

    def test_known_distance(self):
        # LA to SF is roughly 559 km
        distance = calculate_distance_km(34.05, -118.24, 37.77, -122.42)
        assert 540 < distance < 580

    def test_antipodal_points(self):
        distance = calculate_distance_km(0, 0, 0, 180)
        # Should be roughly half the circumference ≈ 20015 km
        assert 20000 < distance < 20100


class TestIsDataFresh:

    def test_recent_data_is_fresh(self):
        ts = timezone.now() - timedelta(minutes=30)
        assert is_data_fresh(ts, max_age_hours=3) is True

    def test_old_data_is_stale(self):
        ts = timezone.now() - timedelta(hours=4)
        assert is_data_fresh(ts, max_age_hours=3) is False

    def test_iso_string_timestamp(self):
        ts = (timezone.now() - timedelta(minutes=10)).isoformat()
        assert is_data_fresh(ts) is True

    def test_invalid_string_returns_false(self):
        assert is_data_fresh("not-a-date") is False


class TestTimeDecayWeight:

    def test_recent_data_full_weight(self):
        ts = timezone.now() - timedelta(minutes=5)
        weight = calculate_time_decay_weight(ts, preferred_age_minutes=30)
        assert weight == 1.0

    def test_old_data_lower_weight(self):
        ts = timezone.now() - timedelta(hours=2)
        weight = calculate_time_decay_weight(ts, preferred_age_minutes=30)
        assert 0.1 <= weight < 0.5

    def test_minimum_weight_enforced(self):
        ts = timezone.now() - timedelta(hours=24)
        weight = calculate_time_decay_weight(ts, preferred_age_minutes=30)
        assert weight >= 0.1


class TestPurpleAirEPACorrection:

    def test_none_returns_none(self):
        assert apply_purpleair_epa_correction(None) is None

    def test_low_pm25_correction(self):
        result = apply_purpleair_epa_correction(10.0)
        assert result is not None
        # Should be lower than raw for low values
        assert result < 10.0

    def test_medium_pm25_correction(self):
        result = apply_purpleair_epa_correction(40.0)
        assert result is not None

    def test_high_pm25_correction(self):
        result = apply_purpleair_epa_correction(100.0)
        assert result is not None

    def test_very_low_pm25_never_negative(self):
        result = apply_purpleair_epa_correction(0.05)
        assert result >= 0.0

    def test_zero_pm25_never_negative(self):
        result = apply_purpleair_epa_correction(0.0)
        assert result >= 0.0


class TestValidateCoordinates:

    def test_valid_coordinates(self):
        valid, error = validate_coordinates(34.05, -118.24)
        assert valid is True
        assert error is None

    def test_lat_too_high(self):
        valid, error = validate_coordinates(91, 0)
        assert valid is False
        assert 'Latitude' in error

    def test_lat_too_low(self):
        valid, error = validate_coordinates(-91, 0)
        assert valid is False

    def test_lon_too_high(self):
        valid, error = validate_coordinates(0, 181)
        assert valid is False
        assert 'Longitude' in error

    def test_boundary_values_valid(self):
        assert validate_coordinates(90, 180)[0] is True
        assert validate_coordinates(-90, -180)[0] is True

    def test_non_numeric_returns_invalid(self):
        valid, error = validate_coordinates('abc', 0)
        assert valid is False
