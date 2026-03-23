"""
Astronomical calculations for JASPR Weather.
Moon phase computation and golden hour estimation.
"""
import math
from datetime import date, datetime, timedelta
from typing import Dict, Optional


# Named moon phases mapped to 0-based index out of 8 segments
_PHASE_NAMES = [
    'New Moon',
    'Waxing Crescent',
    'First Quarter',
    'Waxing Gibbous',
    'Full Moon',
    'Waning Gibbous',
    'Last Quarter',
    'Waning Crescent',
]

# Known new moon reference: January 6, 2000 18:14 UTC
_KNOWN_NEW_MOON_JD = 2451550.26

# Synodic period (mean lunation) in days
_SYNODIC_PERIOD = 29.53058867


def compute_moon_phase(d: date) -> Dict:
    """
    Compute the moon phase for a given date.

    Uses the synodic period method: days since a known new moon,
    modulo the lunation period.

    Returns:
        {
            'name': str,           # e.g. 'Waxing Crescent'
            'value': float,        # 0.0 (new) to ~1.0 (next new)
            'illumination': int,   # 0-100 percentage
        }
    """
    # Julian Date for noon on the given date
    if isinstance(d, datetime):
        d = d.date()
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    jd = d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045 + 0.5

    days_since = jd - _KNOWN_NEW_MOON_JD
    cycles = days_since / _SYNODIC_PERIOD
    phase_value = cycles - math.floor(cycles)  # 0.0 to ~1.0

    # Map to 8 segments
    segment = int(phase_value * 8) % 8
    phase_name = _PHASE_NAMES[segment]

    # Illumination: 0% at new, 100% at full, using cosine
    illumination = round((1 - math.cos(phase_value * 2 * math.pi)) / 2 * 100)

    return {
        'name': phase_name,
        'value': round(phase_value, 4),
        'illumination': illumination,
    }


def compute_golden_hour(sunrise: Optional[str], sunset: Optional[str]) -> Optional[Dict]:
    """
    Estimate golden hour windows from sunrise/sunset ISO strings.

    Golden hour is approximately the first/last ~45 minutes of sunlight,
    though this varies by latitude and season.

    Returns:
        {
            'morning': { 'start': ISO str, 'end': ISO str },
            'evening': { 'start': ISO str, 'end': ISO str },
        }
        or None if sunrise/sunset data is missing.
    """
    if not sunrise or not sunset:
        return None

    try:
        sr = _parse_iso(sunrise)
        ss = _parse_iso(sunset)
    except (ValueError, TypeError):
        return None

    golden_duration = timedelta(minutes=45)

    return {
        'morning': {
            'start': sr.isoformat(),
            'end': (sr + golden_duration).isoformat(),
        },
        'evening': {
            'start': (ss - golden_duration).isoformat(),
            'end': ss.isoformat(),
        },
    }


def _parse_iso(value: str) -> datetime:
    """Parse an ISO datetime string, handling Open-Meteo's format."""
    value = str(value).replace('Z', '+00:00')
    return datetime.fromisoformat(value)
