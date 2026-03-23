# Quick Start Guide - Air Quality API

Get up and running in 5 minutes!

## ⚡ Fast Setup

### 1. Run Setup Script

```bash
git clone https://github.com/yevgetman/breathe-api.git
cd breathe-api
./setup.sh
```

The script will:
- Create virtual environment
- Install all dependencies
- Create `.env` file from template
- Run database migrations
- Initialize default data
- Optionally create superuser

### 2. Add API Keys

Edit `.env` file and add your API keys:

```env
AIRNOW_API_KEY=your-key-here
PURPLEAIR_API_KEY=your-key-here
OPENWEATHERMAP_API_KEY=your-key-here
WAQI_API_KEY=your-key-here
```

**Note**: API keys are already included from your `APIKeys` file. You can use them as-is.

### 3. Start Development Server

```bash
python manage.py runserver
```

### 4. Test the API

Open your browser or use curl:

```bash
# Get air quality for Los Angeles
curl "http://localhost:8000/api/v1/air-quality/?lat=34.05&lon=-118.24"

# Get air quality with forecast
curl "http://localhost:8000/api/v1/air-quality/?lat=34.05&lon=-118.24&include_forecast=true"

# Check system health
curl "http://localhost:8000/api/v1/health/"

# List available sources
curl "http://localhost:8000/api/v1/sources/"
```

## 🎯 Example Coordinates to Test

- **Los Angeles, CA**: `lat=34.05&lon=-118.24`
- **New York, NY**: `lat=40.71&lon=-74.01`
- **San Francisco, CA**: `lat=37.77&lon=-122.42`
- **Chicago, IL**: `lat=41.88&lon=-87.63`
- **Toronto, Canada**: `lat=43.65&lon=-79.38`

## 🔍 Example Response

```json
{
  "location": {
    "lat": 34.05,
    "lon": -118.24,
    "city": "Los Angeles",
    "region": "California",
    "country": "US"
  },
  "current": {
    "aqi": 72,
    "category": "Moderate",
    "pollutants": {
      "pm25": 22.1,
      "pm10": 35.4,
      "o3": 45.2,
      "no2": 18.3
    },
    "sources": ["EPA_AIRNOW", "PURPLEAIR"],
    "last_updated": "2025-11-05T12:03:00Z"
  },
  "health_advice": "Air quality is acceptable. However, there may be a risk for some people..."
}
```

## 🛠️ Common Commands

### Run Server
```bash
python manage.py runserver
```

### Create Superuser
```bash
python manage.py createsuperuser
```

### Access Admin Interface
Navigate to: `http://localhost:8000/admin/`

### Run Migrations
```bash
python manage.py migrate
```

### Re-initialize Data
```bash
python manage.py init_data
```

### Run Tests
```bash
pytest
# Expected output: 74 passed
```

### Check for Issues
```bash
python manage.py check
```

### View Logs
```bash
tail -f logs/airquality.log
```

## 🐛 Troubleshooting

### No Data Returned

**Check adapter status:**
```bash
curl "http://localhost:8000/api/v1/sources/"
```

**View logs:**
```bash
tail -f logs/airquality.log
```

**Verify API keys in .env file**

### Database Errors

```bash
python manage.py migrate
python manage.py init_data
```

### Port Already in Use

Run on different port:
```bash
python manage.py runserver 8001
```

## 📊 Monitor Performance

### Check Cache Status
Start Redis:
```bash
redis-server
```

Test cache:
```bash
redis-cli ping
# Should return: PONG
```

### View Response Times
Check logs for execution times:
```bash
grep "execution_time_ms" logs/airquality.log
```

## 🎓 Next Steps

1. ✅ Read [README.md](README.md) for comprehensive documentation
2. ✅ Read [README-API-REFERENCE.md](README-API-REFERENCE.md) for full API reference
3. ✅ Run `pytest` to verify everything works
4. ✅ Explore Django admin at `/admin/`
5. ✅ Test different coordinates and parameters
6. ✅ Set up Redis for caching (optional but recommended)
7. ✅ Configure production settings for deployment

## 💡 Pro Tips

- Use `include_forecast=true` to get 4-day forecasts
- Adjust `radius_km` parameter to control search area for sensors (default: 25km)
- Use `no_cache=true` during testing to always fetch fresh data
- Monitor adapter health regularly via `/api/v1/sources/`
- Check `/api/v1/health/` for system status

## 🚀 Production Deployment

When ready for production:

1. Set `DEBUG=False` in `.env`
2. Configure PostgreSQL database
3. Set up Redis for caching
4. Use Gunicorn: `gunicorn config.wsgi:application`
5. Configure nginx as reverse proxy
6. Enable HTTPS/SSL
7. Set up monitoring and logging

See [README.md](README.md) for detailed deployment instructions.

---

**Need help?** Check the full documentation in README.md or review the architecture documents.
