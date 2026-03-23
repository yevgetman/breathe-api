# Breathe API — CLAUDE.md

## What this project is

Django REST Framework API that aggregates air quality, weather, and pollen data from multiple sources into unified endpoints. Deployed on Heroku at `breathe-api-115e7fded77a.herokuapp.com`. The primary client is the JASPR Weather iOS app (SwiftUI).

## Quick commands

```bash
source venv/bin/activate
python manage.py runserver              # Dev server on :8000
python -m pytest tests/ -v              # Run 127+ tests
python manage.py migrate                # Apply migrations
python manage.py init_data              # Seed AQI categories, sources, regions
git push heroku master                  # Deploy to Heroku
```

## Architecture

```
Request → View → Orchestrator → [Adapters in parallel via ThreadPoolExecutor]
                                   ├── Open-Meteo (weather + hourly + daily)
                                   ├── EPA AirNow (AQ, US)
                                   ├── PurpleAir (AQ, sensors)
                                   ├── OpenWeatherMap (AQ + weather fallback)
                                   ├── WAQI (AQ, global)
                                   ├── AirVisual (AQ, global)
                                   └── Open-Meteo AQ (pollen + hourly AQI)
                              → FusionEngine (weighted averaging)
                              → ResponseCache (Redis + geohash keys)
                              → Serializer → JSON Response
```

## App structure

| App | Path | Purpose |
|-----|------|---------|
| `core` | `apps/core/` | Base models, utils (`calculate_distance_km`, `validate_coordinates`, `convert_aqi_to_category`), constants, `ResponseCache`, geohash |
| `adapters` | `apps/adapters/` | `BaseAdapter` (circuit breaker, retry, logging) + 7 subclasses. Each implements `fetch_current()` |
| `location` | `apps/location/` | `LocationService` — reverse geocoding via Nominatim with 24h cache |
| `fusion` | `apps/fusion/` | `FusionEngine` — weighted AQI blending (trust × time_decay × distance × quality) |
| `forecast` | `apps/forecast/` | `ForecastAggregator` — merges AQ forecasts by hour |
| `api` | `apps/api/` | AQ views + `AirQualityOrchestrator` (parallel fetch + fusion) |
| `weather` | `apps/weather/` | `WeatherOrchestrator` (Open-Meteo primary, OWM fallback), unit conversion, astronomy (moon phase, golden hour) |
| `jaspr` | `apps/jaspr/` | Combined `/api/v1/jaspr/` endpoint — merges weather + AQ + pollen + historical into single response for mobile |

## Key endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/jaspr/?lat=X&lon=Y&units=imperial&include_historical=true` | Combined endpoint for JASPR iOS app (weather + AQ + pollen + hourly + historical + hidden gems) |
| `GET /api/v1/weather/?lat=X&lon=Y&units=imperial` | Weather: current + 48h hourly + 10-day daily (with moon phase, golden hour) |
| `GET /api/v1/air-quality/?lat=X&lon=Y&include_forecast=true` | Air quality: current AQI (5-source fusion) + forecast |
| `GET /api/v1/health-advice/?aqi=72` | Health advice for a given AQI value |
| `GET /api/v1/sources/` | List data sources and their health status |
| `GET /api/v1/health/` | System health check (DB, cache, adapters) |

## Key files to know

- `apps/adapters/base.py` — `BaseAdapter` with circuit breaker, retry, logging. All adapters inherit from this.
- `apps/adapters/open_meteo.py` — Primary weather adapter. Fetches current + hourly + daily from Open-Meteo. `WMO_WEATHER_CODES` dict maps codes to descriptions/icons.
- `apps/adapters/open_meteo_air_quality.py` — Pollen + hourly AQI from Open-Meteo AQ API. `_classify_pollen_level()` maps grains/m3 to levels.
- `apps/fusion/engine.py` — `FusionEngine.blend()` — weighted AQI averaging. Weight = trust × time_decay × distance × quality × confidence.
- `apps/weather/orchestrator.py` — Primary/fallback pattern. Caches in Redis with geohash keys. Unit conversion at response time.
- `apps/jaspr/orchestrator.py` — `JasprOrchestrator` — parallel ThreadPoolExecutor (weather + AQ + pollen + historical). Merges hourly weather with hourly AQI by timestamp.
- `apps/jaspr/analysis.py` — Hidden Gems: compares current AQI to 30-day historical stats. Only returns factually true claims.
- `apps/weather/astronomy.py` — Moon phase (synodic period algorithm) and golden hour computation.
- `apps/core/cache.py` — `ResponseCache` — Redis-backed with geohash spatial keys (~1.2km cells at precision 6).
- `apps/core/geohash.py` — Pure-Python geohash encoding.
- `apps/weather/utils.py` — Unit conversion: `convert_current_to_imperial()`, `convert_hourly_to_imperial()`, `convert_forecast_to_imperial()`.
- `config/settings/base.py` — `AIR_QUALITY_SETTINGS`, `WEATHER_SETTINGS`, `CACHE_SETTINGS` dicts. API keys in `API_KEYS` dict.

## Settings structure

- `AIR_QUALITY_SETTINGS` — source weights, priorities by region, cache TTLs, PurpleAir correction settings
- `WEATHER_SETTINGS` — cache TTLs, forecast days, default units, timeouts
- `CACHE_SETTINGS` — geohash precision (6), DB write-through toggle
- `API_KEYS` — keyed by adapter SOURCE_CODE (e.g., `EPA_AIRNOW`, `PURPLEAIR`, `OPENWEATHERMAP`)

## Patterns to follow

- **Adapters**: Inherit from `BaseAdapter`. Implement `fetch_current(lat, lon, **kwargs)`. Use `_make_request(endpoint, params)` for HTTP. Circuit breaker and retry are automatic.
- **Caching**: Use `ResponseCache(namespace, default_ttl, geohash_precision)`. Keys are geohash-based so nearby coordinates share cache.
- **Unit conversion**: Store metric internally. Convert at response time in orchestrator.
- **Serializers**: DRF serializers validate response shape. If serializer fails, return raw dict (graceful degradation).
- **Error handling**: Adapter failures are non-fatal. Orchestrators catch exceptions and degrade gracefully. Never crash on a single adapter failure.

## Testing

Tests are in `tests/`. Run with `python -m pytest tests/ -v`. Uses `pytest-django` with `config.settings.development`. Most tests use mocks — no live API calls in tests.

## Deployment

Heroku with `Procfile` (gunicorn + release migration). PostgreSQL + Redis add-ons. Push to deploy: `git push heroku master`.
