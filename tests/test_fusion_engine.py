"""
Tests for the fusion engine: weighted blending, data validation, edge cases.
"""
import math
import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.utils import timezone


@pytest.mark.django_db
class TestBlendAQI:
    """Tests for FusionEngine._blend_aqi"""

    def _get_engine(self):
        from apps.fusion.engine import FusionEngine
        return FusionEngine()

    def test_single_source(self, make_source_data):
        engine = self._get_engine()
        sources = [(make_source_data(aqi=100), 1.0)]
        assert engine._blend_aqi(sources) == 100

    def test_equal_weight_average(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(aqi=50), 1.0),
            (make_source_data(aqi=100), 1.0),
        ]
        assert engine._blend_aqi(sources) == 75

    def test_weighted_average(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(aqi=50), 2.0),
            (make_source_data(aqi=100), 1.0),
        ]
        # (50*2 + 100*1) / (2+1) = 200/3 ≈ 67
        assert engine._blend_aqi(sources) == 67

    def test_none_aqi_skipped(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(aqi=None), 1.0),
            (make_source_data(aqi=80), 1.0),
        ]
        assert engine._blend_aqi(sources) == 80

    def test_nan_aqi_skipped(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(aqi=float('nan')), 1.0),
            (make_source_data(aqi=60), 1.0),
        ]
        assert engine._blend_aqi(sources) == 60

    def test_negative_aqi_skipped(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(aqi=-10), 1.0),
            (make_source_data(aqi=50), 1.0),
        ]
        assert engine._blend_aqi(sources) == 50

    def test_aqi_over_500_skipped(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(aqi=999), 1.0),
            (make_source_data(aqi=50), 1.0),
        ]
        assert engine._blend_aqi(sources) == 50

    def test_all_invalid_returns_zero(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(aqi=None), 1.0),
            (make_source_data(aqi=float('nan')), 1.0),
        ]
        assert engine._blend_aqi(sources) == 0

    def test_zero_weight_skipped(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(aqi=100), 0.0),
            (make_source_data(aqi=50), 1.0),
        ]
        assert engine._blend_aqi(sources) == 50

    def test_result_clamped_to_500(self, make_source_data):
        engine = self._get_engine()
        sources = [(make_source_data(aqi=500), 1.0)]
        assert engine._blend_aqi(sources) == 500


@pytest.mark.django_db
class TestBlendPollutants:
    """Tests for FusionEngine._blend_pollutants"""

    def _get_engine(self):
        from apps.fusion.engine import FusionEngine
        return FusionEngine()

    def test_single_source_pollutants(self, make_source_data):
        engine = self._get_engine()
        sources = [(make_source_data(pollutants={'pm25': 20.0, 'o3': 40.0}), 1.0)]
        result = engine._blend_pollutants(sources)
        assert result['pm25'] == 20.0
        assert result['o3'] == 40.0

    def test_none_values_skipped(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(pollutants={'pm25': None, 'o3': 40.0}), 1.0),
            (make_source_data(pollutants={'pm25': 10.0}), 1.0),
        ]
        result = engine._blend_pollutants(sources)
        assert result['pm25'] == 10.0
        assert result['o3'] == 40.0

    def test_nan_values_skipped(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(pollutants={'pm25': float('nan')}), 1.0),
            (make_source_data(pollutants={'pm25': 15.0}), 1.0),
        ]
        result = engine._blend_pollutants(sources)
        assert result['pm25'] == 15.0

    def test_negative_values_skipped(self, make_source_data):
        engine = self._get_engine()
        sources = [
            (make_source_data(pollutants={'pm25': -5.0}), 1.0),
            (make_source_data(pollutants={'pm25': 20.0}), 1.0),
        ]
        result = engine._blend_pollutants(sources)
        assert result['pm25'] == 20.0

    def test_empty_pollutants_handled(self, make_source_data):
        engine = self._get_engine()
        sd = make_source_data(pollutants={})
        sd.pollutants = {}  # override default from factory
        sources = [(sd, 1.0)]
        result = engine._blend_pollutants(sources)
        assert result == {}


@pytest.mark.django_db
class TestCalculateWeight:
    """Tests for FusionEngine._calculate_weight"""

    def _get_engine(self):
        from apps.fusion.engine import FusionEngine
        return FusionEngine()

    def test_unknown_confidence_gets_conservative_default(self, make_source_data):
        engine = self._get_engine()
        sd = make_source_data(confidence_score=None)
        weight = engine._calculate_weight(sd, 'DEFAULT', 34.05, -118.24)
        # With confidence_score=None, confidence_weight should be 0.5
        assert weight > 0

    def test_full_confidence_higher_weight(self, make_source_data):
        engine = self._get_engine()
        sd_high = make_source_data(confidence_score=100.0)
        sd_low = make_source_data(confidence_score=None)
        w_high = engine._calculate_weight(sd_high, 'DEFAULT', 34.05, -118.24)
        w_low = engine._calculate_weight(sd_low, 'DEFAULT', 34.05, -118.24)
        assert w_high > w_low

    def test_closer_sensor_higher_weight(self, make_source_data):
        engine = self._get_engine()
        sd_close = make_source_data(distance_km=1.0)
        sd_far = make_source_data(distance_km=20.0)
        w_close = engine._calculate_weight(sd_close, 'DEFAULT', 34.05, -118.24)
        w_far = engine._calculate_weight(sd_far, 'DEFAULT', 34.05, -118.24)
        assert w_close > w_far
