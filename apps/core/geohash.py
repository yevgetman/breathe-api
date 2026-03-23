"""
Pure-Python geohash encoding for spatial cache key generation.

Geohash encodes a (lat, lon) coordinate into a short string where
nearby points share a common prefix. At precision 6, cells are
approximately 1.2km x 0.6km.

No external dependencies required.
"""

_BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'


def encode(lat: float, lon: float, precision: int = 6) -> str:
    """
    Encode latitude/longitude into a geohash string.

    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        precision: Length of returned string (1-12). Default 6 (~1.2km cells).

    Returns:
        Geohash string of the given precision.
    """
    lat_range = (-90.0, 90.0)
    lon_range = (-180.0, 180.0)
    is_lon = True  # alternate: longitude first
    bits = 0
    bit_count = 0
    result = []

    while len(result) < precision:
        if is_lon:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                bits = (bits << 1) | 1
                lon_range = (mid, lon_range[1])
            else:
                bits = (bits << 1)
                lon_range = (lon_range[0], mid)
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                bits = (bits << 1) | 1
                lat_range = (mid, lat_range[1])
            else:
                bits = (bits << 1)
                lat_range = (lat_range[0], mid)

        is_lon = not is_lon
        bit_count += 1

        if bit_count == 5:
            result.append(_BASE32[bits])
            bits = 0
            bit_count = 0

    return ''.join(result)
