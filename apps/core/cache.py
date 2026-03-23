"""
Unified Redis-backed response cache with geohash-based spatial keys.

Uses django.core.cache (backed by django_redis in production)
for all cache operations. Falls back gracefully when Redis is
unavailable — callers proceed to fetch live data on any failure.
"""
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

from . import geohash

logger = logging.getLogger(__name__)


class _CacheEncoder(json.JSONEncoder):
    """Handle Decimal, datetime, date for JSON serialization."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


class ResponseCache:
    """
    Geohash-aware cache for API response data.

    Encodes (lat, lon) into a geohash cell so nearby requests
    (~1.2km at precision 6) share the same cache entry.

    Usage::

        rc = ResponseCache(namespace='aq', default_ttl=600)

        # Try cache
        data = rc.get(34.05, -118.24)
        if data is not None:
            return data

        # ... fetch fresh data ...

        rc.set(34.05, -118.24, result)
    """

    def __init__(
        self,
        namespace: str,
        default_ttl: int = 600,
        geohash_precision: int = 6,
    ):
        self.namespace = namespace
        self.default_ttl = default_ttl
        self.precision = geohash_precision

    def make_key(self, lat: float, lon: float, *extra: str) -> str:
        """Build cache key from coordinates and optional extra segments."""
        gh = geohash.encode(float(lat), float(lon), self.precision)
        parts = [self.namespace, gh]
        if extra:
            parts.extend(str(e) for e in extra)
        return ":".join(parts)

    def get(self, lat: float, lon: float, *extra: str) -> Optional[dict]:
        """
        Get cached data for coordinates.
        Returns None on miss or backend failure.
        """
        try:
            key = self.make_key(lat, lon, *extra)
            raw = cache.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Cache read failed ({self.namespace}): {e}")
            return None

    def set(
        self,
        lat: float,
        lon: float,
        data,
        *extra: str,
        ttl: int = None,
    ) -> bool:
        """
        Cache response data for coordinates.
        Returns False on failure (non-fatal).
        """
        try:
            key = self.make_key(lat, lon, *extra)
            raw = json.dumps(data, cls=_CacheEncoder)
            cache.set(key, raw, timeout=ttl or self.default_ttl)
            return True
        except Exception as e:
            logger.warning(f"Cache write failed ({self.namespace}): {e}")
            return False

    def delete(self, lat: float, lon: float, *extra: str) -> bool:
        """Invalidate a cache entry."""
        try:
            key = self.make_key(lat, lon, *extra)
            cache.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed ({self.namespace}): {e}")
            return False
