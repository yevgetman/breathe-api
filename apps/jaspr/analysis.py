"""
Historical data analysis for JASPR Weather "Hidden Gems" feature.

Hidden Gems are factually-supported positive observations about the current day,
derived by comparing today's data to recent historical averages.
Only surfaces when claims are genuinely true — never fabricates comparisons.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def compute_hidden_gems(
    current_aqi: Optional[int],
    current_humidity: Optional[int],
    current_weather_code: Optional[int],
    historical: Optional[Dict],
) -> List[Dict]:
    """
    Generate factually-supported "Hidden Gems" by comparing current data
    to historical summary statistics.

    Returns a list of qualified gems, each with:
        - 'text': Display string (e.g., "Clearest air in 4 weeks")
        - 'type': Category (e.g., 'air_quality', 'humidity', 'weather')

    Returns empty list if no gems qualify. Never fabricate claims.
    """
    if not historical:
        return []

    gems = []
    past_days = historical.get('past_days', 30)

    # "Clearest air" — today's AQI is below the historical minimum
    hist_aqi_min = historical.get('aqi_min')
    hist_aqi_avg = historical.get('aqi_avg')
    if current_aqi is not None and hist_aqi_min is not None:
        if current_aqi <= hist_aqi_min:
            weeks = max(1, past_days // 7)
            gems.append({
                'text': f'Clearest air in {weeks} weeks',
                'type': 'air_quality',
            })
        elif hist_aqi_avg is not None and current_aqi < hist_aqi_avg * 0.6:
            gems.append({
                'text': 'Air quality is significantly better than average today',
                'type': 'air_quality',
            })

    # "Excellent air quality" — only when AQI is truly excellent
    if current_aqi is not None and current_aqi <= 25 and not any(g['type'] == 'air_quality' for g in gems):
        gems.append({
            'text': 'Excellent air quality — perfect for outdoor activities',
            'type': 'air_quality',
        })

    # Clear sky gem — WMO codes 0 or 1 mean clear/mainly clear
    if current_weather_code is not None and current_weather_code <= 1:
        gems.append({
            'text': 'Crystal clear skies today',
            'type': 'weather',
        })

    return gems


def compute_historical_summary(
    current_aqi: Optional[int],
    historical_stats: Optional[Dict],
) -> Optional[Dict]:
    """
    Build the historical comparison section for the JASPR response.

    Returns:
        {
            'aqi_avg_30d': float,
            'aqi_min_30d': int,
            'aqi_max_30d': int,
            'today_vs_avg': {
                'aqi_delta': int,     # negative = better than avg
                'trend': str,         # 'improving' | 'stable' | 'worsening'
            }
        }
        or None if insufficient data.
    """
    if not historical_stats or historical_stats.get('aqi_avg') is None:
        return None

    avg = historical_stats['aqi_avg']
    result = {
        'aqi_avg_30d': avg,
        'aqi_min_30d': historical_stats.get('aqi_min'),
        'aqi_max_30d': historical_stats.get('aqi_max'),
        'today_vs_avg': None,
    }

    if current_aqi is not None:
        delta = current_aqi - avg
        if delta < -10:
            trend = 'improving'
        elif delta > 10:
            trend = 'worsening'
        else:
            trend = 'stable'

        result['today_vs_avg'] = {
            'aqi_delta': round(delta),
            'trend': trend,
        }

    return result
