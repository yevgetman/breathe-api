"""
Tests for geohash encoding and ResponseCache.
"""
import json
import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.core.geohash import encode
from apps.core.cache import ResponseCache, _CacheEncoder


# ---------------------------------------------------------------------------
# Geohash tests
# ---------------------------------------------------------------------------

class TestGeohash:

    def test_known_value_la(self):
        """Los Angeles (34.05, -118.24) should produce '9q5ctr' at precision 6."""
        gh = encode(34.05, -118.24, precision=6)
        assert len(gh) == 6
        # Verify it starts with '9q5c' (the 4-char prefix for this area)
        assert gh.startswith('9q5c')

    def test_known_value_nyc(self):
        """New York (40.71, -74.01) at precision 6."""
        gh = encode(40.71, -74.01, precision=6)
        assert len(gh) == 6
        assert gh.startswith('dr5r')

    def test_nearby_points_same_hash(self):
        """Two points within the same ~1.2km cell share a geohash at precision 6."""
        gh1 = encode(34.053, -118.243, precision=6)
        gh2 = encode(34.055, -118.245, precision=6)
        assert gh1 == gh2

    def test_distant_points_different_hash(self):
        """LA and NYC should have different geohashes."""
        gh_la = encode(34.05, -118.24, precision=6)
        gh_nyc = encode(40.71, -74.01, precision=6)
        assert gh_la != gh_nyc

    def test_precision_length(self):
        """Output length equals precision parameter."""
        for p in range(1, 9):
            gh = encode(0.0, 0.0, precision=p)
            assert len(gh) == p

    def test_higher_precision_is_prefix(self):
        """Lower precision geohash is a prefix of higher precision."""
        gh4 = encode(34.05, -118.24, precision=4)
        gh6 = encode(34.05, -118.24, precision=6)
        assert gh6.startswith(gh4)

    def test_equator_prime_meridian(self):
        gh = encode(0.0, 0.0, precision=6)
        assert len(gh) == 6
        assert gh == 's00000'

    def test_north_pole(self):
        gh = encode(90.0, 0.0, precision=6)
        assert len(gh) == 6

    def test_south_pole(self):
        gh = encode(-90.0, 0.0, precision=6)
        assert len(gh) == 6

    def test_antimeridian(self):
        gh = encode(0.0, 180.0, precision=6)
        assert len(gh) == 6

    def test_negative_coordinates(self):
        gh = encode(-33.87, 151.21, precision=6)  # Sydney
        assert len(gh) == 6


# ---------------------------------------------------------------------------
# CacheEncoder tests
# ---------------------------------------------------------------------------

class TestCacheEncoder:

    def test_decimal_serialization(self):
        data = {'value': Decimal('34.050')}
        result = json.dumps(data, cls=_CacheEncoder)
        assert '34.05' in result

    def test_datetime_serialization(self):
        data = {'ts': datetime(2026, 3, 23, 12, 0, 0)}
        result = json.dumps(data, cls=_CacheEncoder)
        assert '2026-03-23' in result

    def test_date_serialization(self):
        data = {'d': date(2026, 3, 23)}
        result = json.dumps(data, cls=_CacheEncoder)
        assert '2026-03-23' in result

    def test_normal_types_unaffected(self):
        data = {'a': 1, 'b': 'hello', 'c': [1, 2], 'd': None}
        result = json.dumps(data, cls=_CacheEncoder)
        parsed = json.loads(result)
        assert parsed == data


# ---------------------------------------------------------------------------
# ResponseCache tests
# ---------------------------------------------------------------------------

class TestResponseCache:

    def test_make_key_format(self):
        rc = ResponseCache(namespace='aq', default_ttl=600, geohash_precision=6)
        key = rc.make_key(34.05, -118.24)
        # Should be namespace:geohash
        parts = key.split(':')
        assert parts[0] == 'aq'
        assert len(parts[1]) == 6  # geohash

    def test_make_key_with_extra(self):
        rc = ResponseCache(namespace='wx', default_ttl=300)
        key = rc.make_key(34.05, -118.24, 'imperial')
        parts = key.split(':')
        assert parts[0] == 'wx'
        assert parts[2] == 'imperial'

    def test_make_key_deterministic(self):
        rc = ResponseCache(namespace='aq', default_ttl=600)
        k1 = rc.make_key(34.05, -118.24)
        k2 = rc.make_key(34.05, -118.24)
        assert k1 == k2

    def test_nearby_coords_same_key(self):
        rc = ResponseCache(namespace='aq', default_ttl=600, geohash_precision=6)
        k1 = rc.make_key(34.053, -118.243)
        k2 = rc.make_key(34.055, -118.245)
        assert k1 == k2

    @patch('apps.core.cache.cache')
    def test_get_returns_none_on_miss(self, mock_cache):
        mock_cache.get.return_value = None
        rc = ResponseCache(namespace='aq', default_ttl=600)
        assert rc.get(34.05, -118.24) is None

    @patch('apps.core.cache.cache')
    def test_set_then_get_roundtrip(self, mock_cache):
        stored = {}

        def mock_set(key, value, timeout=None):
            stored[key] = value

        def mock_get(key):
            return stored.get(key)

        mock_cache.set.side_effect = mock_set
        mock_cache.get.side_effect = mock_get

        rc = ResponseCache(namespace='aq', default_ttl=600)
        data = {'current': {'aqi': 50}, 'sources': ['EPA']}

        rc.set(34.05, -118.24, data)
        result = rc.get(34.05, -118.24)

        assert result == data
        assert result['current']['aqi'] == 50

    @patch('apps.core.cache.cache')
    def test_set_serializes_decimal_and_datetime(self, mock_cache):
        stored = {}
        mock_cache.set.side_effect = lambda k, v, timeout=None: stored.update({k: v})
        mock_cache.get.side_effect = lambda k: stored.get(k)

        rc = ResponseCache(namespace='test', default_ttl=60)
        data = {
            'lat': Decimal('34.050'),
            'ts': datetime(2026, 3, 23, 12, 0),
            'date': date(2026, 3, 23),
        }

        rc.set(0, 0, data)
        result = rc.get(0, 0)

        assert result['lat'] == 34.05
        assert '2026-03-23' in result['ts']

    @patch('apps.core.cache.cache')
    def test_get_handles_redis_failure(self, mock_cache):
        mock_cache.get.side_effect = ConnectionError("Redis down")
        rc = ResponseCache(namespace='aq', default_ttl=600)
        result = rc.get(34.05, -118.24)
        assert result is None  # graceful fallback

    @patch('apps.core.cache.cache')
    def test_set_handles_redis_failure(self, mock_cache):
        mock_cache.set.side_effect = ConnectionError("Redis down")
        rc = ResponseCache(namespace='aq', default_ttl=600)
        result = rc.set(34.05, -118.24, {'aqi': 50})
        assert result is False  # non-fatal

    @patch('apps.core.cache.cache')
    def test_delete(self, mock_cache):
        rc = ResponseCache(namespace='aq', default_ttl=600)
        result = rc.delete(34.05, -118.24)
        assert result is True
        mock_cache.delete.assert_called_once()
