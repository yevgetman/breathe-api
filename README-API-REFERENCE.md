# Air Quality API - Developer Reference

## 📘 Overview

The Air Quality API provides real-time and forecasted air quality data for any location worldwide. Our API aggregates data from multiple trusted sources including government agencies, sensor networks, and atmospheric models to give you the most accurate air quality information.

**Perfect for:**
- 🌍 Weather and environmental apps
- 🏃 Fitness and outdoor activity apps
- 🏥 Health monitoring applications  
- 🏠 Smart home systems
- 📊 Data analytics platforms
- 🌱 Environmental awareness tools

---

## 🚀 Quick Start

### Base URL
```
https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/
```

### Your First Request
```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=34.05&lon=-118.24"
```

### Response (200 OK)
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
      "pm25": 23.2,
      "pm10": 12.44,
      "o3": 65.83,
      "no2": 3.7,
      "so2": 0.16,
      "co": 63.36
    },
    "sources": ["PURPLEAIR", "OPENWEATHERMAP", "AIRVISUAL", "WAQI"],
    "last_updated": "2025-11-05T11:44:11Z"
  },
  "health_advice": "Air quality is acceptable. However, there may be a risk for some people, particularly those who are unusually sensitive to air pollution."
}
```

---

## 📡 API Endpoints

### 1. Get Air Quality Data
**The main endpoint** - Get current air quality information for any location.

```
GET /api/v1/air-quality/
```

#### Use Cases
- Display current AQI in your app
- Show air quality on a map
- Alert users when air quality is poor
- Provide outdoor activity recommendations
- Track air quality trends

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lat` | float | **Yes** | - | Latitude (-90 to 90) |
| `lon` | float | **Yes** | - | Longitude (-180 to 180) |
| `include_forecast` | boolean | No | false | Include 4-day hourly forecast |
| `radius_km` | float | No | 25 | Search radius for sensors (max: 100) |
| `no_cache` | boolean | No | false | Skip cache for fresh data |

#### Response Structure

```typescript
{
  location: {
    lat: number,              // Query latitude
    lon: number,              // Query longitude
    city: string,             // Nearest city name
    region: string,           // State/province
    country: string           // Country code (e.g., "US")
  },
  current: {
    aqi: number,              // Air Quality Index (0-500)
    category: string,         // "Good", "Moderate", "Unhealthy", etc.
    pollutants: {
      pm25: number,           // PM2.5 (μg/m³)
      pm10: number,           // PM10 (μg/m³)
      o3: number,             // Ozone (μg/m³)
      no2: number,            // Nitrogen Dioxide (μg/m³)
      so2: number,            // Sulfur Dioxide (μg/m³)
      co: number              // Carbon Monoxide (μg/m³)
    },
    sources: string[],        // Data sources used
    last_updated: string      // ISO 8601 timestamp
  },
  health_advice: string,      // Health recommendation
  source_details: [           // Detailed source information
    {
      source: string,
      weight: number,
      aqi: number,
      distance_km: number,
      timestamp: string,
      quality_level: string,
      station_name: string
    }
  ],
  forecast: [                 // Optional: Only if include_forecast=true
    {
      timestamp: string,
      aqi: number,
      category: string,
      pollutants: {...},
      sources: string[]
    }
  ]
}
```

#### Example Requests

**Basic Request:**
```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=40.71&lon=-74.01"
```

**With Forecast:**
```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=40.71&lon=-74.01&include_forecast=true"
```

**Custom Search Radius:**
```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=37.77&lon=-122.42&radius_km=10"
```

**Fresh Data (Skip Cache):**
```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=34.05&lon=-118.24&no_cache=true"
```

#### AQI Categories

| AQI Range | Category | Color | Health Impact |
|-----------|----------|-------|---------------|
| 0-50 | Good | 🟢 Green | Air quality is satisfactory |
| 51-100 | Moderate | 🟡 Yellow | Acceptable for most people |
| 101-150 | Unhealthy for Sensitive Groups | 🟠 Orange | Sensitive groups may experience effects |
| 151-200 | Unhealthy | 🔴 Red | Everyone may experience effects |
| 201-300 | Very Unhealthy | 🟣 Purple | Health alert |
| 301+ | Hazardous | 🟤 Maroon | Emergency conditions |

---

### 2. Get Health Advice
**Standalone endpoint** - Get health recommendations for a specific AQI value.

```
GET /api/v1/health-advice/
```

#### Use Cases
- Display health warnings
- Provide activity recommendations
- Show sensitive group information
- Create AQI color indicators
- Explain AQI values to users

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `aqi` | integer | **Yes** | - | AQI value (0-500) |
| `scale` | string | No | EPA | AQI scale: "EPA" or "AQHI" |

#### Response Structure

```typescript
{
  aqi: number,                // AQI value from request
  scale: string,              // "EPA" or "AQHI"
  category: string,           // AQI category name
  color: string,              // Hex color code (e.g., "#00E400")
  health_message: string,     // General health advice
  sensitive_groups: string    // Who should be cautious
}
```

#### Example Requests

**Good Air Quality:**
```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/health-advice/?aqi=45"
```

**Response:**
```json
{
  "aqi": 45,
  "scale": "EPA",
  "category": "Good",
  "color": "#00E400",
  "health_message": "Air quality is satisfactory, and air pollution poses little or no risk.",
  "sensitive_groups": ""
}
```

**Unhealthy Air Quality:**
```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/health-advice/?aqi=165"
```

**Response:**
```json
{
  "aqi": 165,
  "scale": "EPA",
  "category": "Unhealthy",
  "color": "#FF0000",
  "health_message": "Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects.",
  "sensitive_groups": "Children, elderly, people with lung disease, people with heart disease"
}
```

---

### 3. List Data Sources
**Informational endpoint** - Get information about all available data sources and their current status.

```
GET /api/v1/sources/
```

#### Use Cases
- Show data attribution
- Display source reliability
- Monitor API health
- Educate users about data origins
- Check which sources are available

#### Parameters
None required.

#### Response Structure

```typescript
{
  sources: [
    {
      code: string,           // Unique source identifier
      name: string,           // Display name
      type: string,           // "OFFICIAL", "SENSOR", "MODEL", "AGGREGATOR"
      description: string,    // What this source provides
      countries: string[],    // Coverage area (empty = global)
      trust_weight: number,   // Reliability score (0.0-1.0)
      status: {
        is_healthy: boolean,
        success_rate: number,
        last_success: string,
        consecutive_failures: number
      }
    }
  ]
}
```

#### Example Request

```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/sources/"
```

#### Example Response

```json
{
  "sources": [
    {
      "code": "EPA_AIRNOW",
      "name": "EPA AirNow",
      "type": "OFFICIAL",
      "description": "Official U.S. EPA air quality data",
      "countries": ["US"],
      "trust_weight": 1.0,
      "status": {
        "is_healthy": true,
        "success_rate": 98.5,
        "last_success": "2025-11-06T10:30:00Z",
        "consecutive_failures": 0
      }
    },
    {
      "code": "PURPLEAIR",
      "name": "PurpleAir",
      "type": "SENSOR",
      "description": "Community air quality sensors",
      "countries": [],
      "trust_weight": 0.85,
      "status": {
        "is_healthy": true,
        "success_rate": 100.0,
        "last_success": "2025-11-06T10:45:00Z",
        "consecutive_failures": 0
      }
    }
  ]
}
```

#### Source Types

| Type | Description | Examples |
|------|-------------|----------|
| `OFFICIAL` | Government monitoring stations | EPA AirNow, ECCC |
| `SENSOR` | Community sensor networks | PurpleAir |
| `MODEL` | Atmospheric models | OpenWeatherMap, AirVisual |
| `AGGREGATOR` | Data from multiple sources | WAQI |

---

### 4. Health Check
**System status endpoint** - Check if the API is operational.

```
GET /api/v1/health/
```

#### Use Cases
- Monitor API uptime
- Check before making requests
- Integration testing
- Load balancer health checks
- Automated monitoring

#### Parameters
None required.

#### Response Structure

```typescript
{
  status: string,             // "healthy", "degraded", or "unhealthy"
  database: boolean,          // Database connectivity
  cache: boolean,             // Cache system status
  adapters: {
    [source: string]: boolean // Status of each data adapter
  }
}
```

#### Example Request

```bash
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/health/"
```

#### Example Responses

**Healthy System:**
```json
{
  "status": "healthy",
  "database": true,
  "cache": true,
  "adapters": {
    "AIRVISUAL": true,
    "OPENWEATHERMAP": true,
    "PURPLEAIR": true,
    "WAQI": true,
    "EPA_AIRNOW": true
  }
}
```

**Degraded System:**
```json
{
  "status": "degraded",
  "database": true,
  "cache": false,
  "adapters": {
    "AIRVISUAL": true,
    "OPENWEATHERMAP": false,
    "PURPLEAIR": true,
    "WAQI": true,
    "EPA_AIRNOW": true
  }
}
```

#### Status Meanings

| Status | HTTP Code | Meaning |
|--------|-----------|---------|
| `healthy` | 200 | All systems operational |
| `degraded` | 200 | Partial functionality (e.g., cache down) |
| `unhealthy` | 503 | Critical failure (e.g., database down) |

---

## 🔍 Common Use Cases

### 1. Display Current Air Quality

**Show AQI on your homepage:**

```javascript
async function getCurrentAirQuality(lat, lon) {
  const response = await fetch(
    `https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=${lat}&lon=${lon}`
  );
  const data = await response.json();
  
  return {
    aqi: data.current.aqi,
    category: data.current.category,
    city: data.location.city
  };
}

// Usage
const airQuality = await getCurrentAirQuality(34.05, -118.24);
console.log(`${airQuality.city}: AQI ${airQuality.aqi} (${airQuality.category})`);
// Output: "Los Angeles: AQI 72 (Moderate)"
```

---

### 2. Show 4-Day Forecast

**Display hourly forecasts:**

```javascript
async function getAirQualityForecast(lat, lon) {
  const response = await fetch(
    `https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=${lat}&lon=${lon}&include_forecast=true`
  );
  const data = await response.json();
  
  return data.forecast.map(item => ({
    time: new Date(item.timestamp),
    aqi: item.aqi,
    category: item.category
  }));
}

// Usage
const forecast = await getAirQualityForecast(40.71, -74.01);
forecast.slice(0, 24).forEach(hour => {
  console.log(`${hour.time.toLocaleString()}: AQI ${hour.aqi}`);
});
```

---

### 3. Alert Users to Poor Air Quality

**Send notifications when AQI is unhealthy:**

```javascript
async function checkAirQuality(lat, lon) {
  const response = await fetch(
    `https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=${lat}&lon=${lon}`
  );
  const data = await response.json();
  
  if (data.current.aqi > 100) {
    sendNotification({
      title: "Poor Air Quality Alert",
      message: data.health_advice,
      severity: data.current.category
    });
  }
}
```

---

### 4. Show Air Quality on Map

**Display AQI markers on interactive map:**

```javascript
async function addAirQualityMarker(map, lat, lon) {
  const response = await fetch(
    `https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=${lat}&lon=${lon}`
  );
  const data = await response.json();
  
  // Get color from health advice endpoint
  const adviceResponse = await fetch(
    `https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/health-advice/?aqi=${data.current.aqi}`
  );
  const advice = await adviceResponse.json();
  
  // Add colored marker
  map.addMarker({
    position: { lat, lon },
    color: advice.color,
    label: data.current.aqi.toString(),
    popup: `${data.location.city}: ${data.current.category}`
  });
}
```

---

### 5. Outdoor Activity Recommendations

**Suggest activities based on air quality:**

```javascript
async function getActivityRecommendation(lat, lon) {
  const response = await fetch(
    `https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=${lat}&lon=${lon}`
  );
  const data = await response.json();
  
  const aqi = data.current.aqi;
  
  if (aqi <= 50) {
    return "Perfect day for outdoor activities! ☀️";
  } else if (aqi <= 100) {
    return "Good for most outdoor activities. 🌤️";
  } else if (aqi <= 150) {
    return "Limit prolonged outdoor exertion. ⚠️";
  } else {
    return "Consider indoor activities today. 🏠";
  }
}
```

---

## ⚠️ Error Handling

### Error Response Format

All errors return a consistent JSON structure:

```json
{
  "error": "Error message",
  "detail": "Additional context (optional)"
}
```

### Common HTTP Status Codes

| Code | Meaning | Cause |
|------|---------|-------|
| `200` | Success | Request completed successfully |
| `400` | Bad Request | Missing or invalid parameters |
| `404` | Not Found | Endpoint doesn't exist |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Server issue |
| `503` | Service Unavailable | System is down (check `/health/`) |

### Example Error Responses

**Missing Parameters (400):**
```json
{
  "error": "Missing required parameters: lat and lon"
}
```

**Invalid Coordinates (400):**
```json
{
  "error": "Latitude must be between -90 and 90"
}
```

**Rate Limit Exceeded (429):**
```json
{
  "error": "Rate limit exceeded",
  "detail": "Maximum 100 requests per minute"
}
```

### Error Handling Best Practices

```javascript
async function safeAPICall(lat, lon) {
  try {
    const response = await fetch(
      `https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=${lat}&lon=${lon}`
    );
    
    if (!response.ok) {
      const error = await response.json();
      console.error('API Error:', error.error);
      
      // Handle specific errors
      if (response.status === 400) {
        // Show user-friendly message
        return { error: "Invalid location" };
      } else if (response.status === 429) {
        // Retry after delay
        await new Promise(resolve => setTimeout(resolve, 60000));
        return safeAPICall(lat, lon);
      }
    }
    
    return await response.json();
  } catch (error) {
    console.error('Network error:', error);
    return { error: "Unable to fetch air quality data" };
  }
}
```

---

## 🚦 Rate Limits & Performance

### Rate Limits
- **Default:** 100 requests per minute
- **Burst:** Up to 120 requests per minute briefly
- **Daily:** 10,000 requests per day

**Note:** Rate limits may vary. Check response headers for current limits.

### Response Headers
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1699286400
```

### Caching
- Responses are cached for **10 minutes** by default
- Use `no_cache=true` to bypass cache
- Consider implementing client-side caching

### Performance Tips

1. **Cache on Your Side:**
   ```javascript
   // Cache for 5 minutes
   const CACHE_TTL = 5 * 60 * 1000;
   const cache = new Map();
   
   function getCachedAirQuality(lat, lon) {
     const key = `${lat},${lon}`;
     const cached = cache.get(key);
     
     if (cached && Date.now() - cached.time < CACHE_TTL) {
       return cached.data;
     }
     
     const data = await fetchAirQuality(lat, lon);
     cache.set(key, { data, time: Date.now() });
     return data;
   }
   ```

2. **Batch Requests:**
   - Request forecast once instead of multiple current requests
   - Reuse data for nearby locations (within ~5 km)

3. **Use Webhooks (if available):**
   - Subscribe to air quality alerts instead of polling

---

## 📱 Integration Examples

### JavaScript (Browser)

```javascript
// Vanilla JavaScript
fetch('https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=34.05&lon=-118.24')
  .then(response => response.json())
  .then(data => {
    document.getElementById('aqi').textContent = data.current.aqi;
    document.getElementById('category').textContent = data.current.category;
  });
```

### React

```jsx
import { useState, useEffect } from 'react';

function AirQualityWidget({ lat, lon }) {
  const [airQuality, setAirQuality] = useState(null);
  
  useEffect(() => {
    fetch(`https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=${lat}&lon=${lon}`)
      .then(res => res.json())
      .then(data => setAirQuality(data));
  }, [lat, lon]);
  
  if (!airQuality) return <div>Loading...</div>;
  
  return (
    <div>
      <h2>{airQuality.location.city}</h2>
      <div className="aqi">{airQuality.current.aqi}</div>
      <div className="category">{airQuality.current.category}</div>
      <p>{airQuality.health_advice}</p>
    </div>
  );
}
```

### Python

```python
import requests

def get_air_quality(lat, lon):
    url = f"https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/"
    params = {"lat": lat, "lon": lon}
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    data = response.json()
    return {
        "aqi": data["current"]["aqi"],
        "category": data["current"]["category"],
        "city": data["location"]["city"]
    }

# Usage
air_quality = get_air_quality(34.05, -118.24)
print(f"AQI: {air_quality['aqi']} ({air_quality['category']})")
```

### cURL

```bash
# Basic request
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=34.05&lon=-118.24"

# With headers
curl -H "Accept: application/json" \
     "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=40.71&lon=-74.01"

# Pretty print
curl "https://air-quiality-api-60b89b17b734.herokuapp.com/api/v1/air-quality/?lat=37.77&lon=-122.42" | jq
```

---

## 🎨 Response Data Guide

### Understanding Pollutant Values

All pollutant concentrations are in **micrograms per cubic meter (μg/m³)**:

| Pollutant | Symbol | Health Impact | Common Sources |
|-----------|--------|---------------|----------------|
| PM2.5 | `pm25` | Tiny particles that penetrate lungs | Vehicles, fires, industry |
| PM10 | `pm10` | Larger particles | Dust, construction |
| Ozone | `o3` | Respiratory irritant | Sunlight + pollution |
| NO₂ | `no2` | Lung inflammation | Vehicles, power plants |
| SO₂ | `so2` | Breathing difficulties | Coal burning, industry |
| CO | `co` | Reduces oxygen delivery | Vehicles, heating |

### Data Freshness

- **Current data:** Updated every 10 minutes
- **Forecast data:** Updated every hour
- **Source updates:** Vary by provider (1-60 minutes)

Check the `last_updated` timestamp to see data age.

### Data Source Priority

The API blends multiple sources. Priority varies by region:

**United States:**
1. EPA AirNow (official)
2. PurpleAir (sensors)
3. OpenWeatherMap (model)
4. WAQI (aggregator)
5. AirVisual (model)

**Canada:**
1. ECCC AQHI (official)
2. PurpleAir (sensors)
3. OpenWeatherMap (model)
4. WAQI (aggregator)

**Other Countries:**
1. WAQI (aggregator)
2. AirVisual (model)
3. PurpleAir (sensors)
4. OpenWeatherMap (model)

---

## 🔧 Troubleshooting

### No Data Returned

**Problem:** API returns AQI as `null`

**Possible causes:**
1. Location too remote (no sensors nearby)
2. All data sources unavailable
3. Temporary outage

**Solution:**
- Increase `radius_km` parameter
- Check `/health/` endpoint
- Try again in a few minutes

### Inaccurate Location

**Problem:** City name doesn't match coordinates

**Cause:** Reverse geocoding approximation

**Solution:**
- Trust the coordinates (lat/lon)
- Location name is for display only

### Slow Response

**Problem:** API takes >3 seconds to respond

**Possible causes:**
1. First request (cache miss)
2. Forecast included (more data to fetch)
3. Large search radius

**Solution:**
- Reduce `radius_km`
- Cache responses client-side
- Skip forecast if not needed

### Unexpected AQI Values

**Problem:** AQI seems wrong

**Explanation:**
- AQI is blended from multiple sources
- Check `source_details` for individual readings
- Some sensors may report differently

**Validation:**
- Compare with `source_details` array
- Check official sources directly
- Report persistent issues

---

## 📊 Best Practices

### 1. Handle Null Values
Some fields may be `null`:

```javascript
const pm25 = data.current.pollutants.pm25 ?? 'N/A';
const city = data.location.city || 'Unknown Location';
```

### 2. Display Source Attribution
Always credit data sources:

```javascript
const sources = data.current.sources.join(', ');
console.log(`Data from: ${sources}`);
```

### 3. Use Appropriate Precision
Don't over-specify:

```javascript
// Good
const aqi = Math.round(data.current.aqi);

// Bad (false precision)
const aqi = data.current.aqi.toFixed(2);
```

### 4. Respect Rate Limits
Implement exponential backoff:

```javascript
async function fetchWithRetry(url, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(url);
      if (response.status === 429) {
        await new Promise(r => setTimeout(r, Math.pow(2, i) * 1000));
        continue;
      }
      return await response.json();
    } catch (error) {
      if (i === retries - 1) throw error;
    }
  }
}
```

### 5. Validate Coordinates
Before sending request:

```javascript
function isValidCoordinate(lat, lon) {
  return lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}
```

---

## 📞 Support & Resources

### Need Help?

- **API Status:** Check `/health/` endpoint
- **Data Sources:** Check `/sources/` endpoint
- **Issues:** Report bugs with example requests

### Useful Links

- **AQI Information:** https://www.airnow.gov/aqi/aqi-basics/
- **Health Guidelines:** https://www.epa.gov/outdoor-air-quality-data
- **Pollutant Info:** https://www.who.int/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health

---

## 📝 Changelog

### v1.0.0 (Current)
- Initial public release
- 5 data sources integrated
- 4 API endpoints available
- Global coverage
- Forecast support

---

## 📜 License & Terms

### Data Attribution
This API aggregates data from:
- EPA AirNow (U.S. Government)
- PurpleAir (Community sensors)
- OpenWeatherMap
- World Air Quality Index Project
- AirVisual (IQAir)

**Please attribute data sources in your application.**

### Usage Terms
- API provided "as is"
- No guaranteed uptime
- Rate limits enforced
- Commercial use allowed
- Attribution required

---

**Last Updated:** November 6, 2025  
**API Version:** 1.0.0  
**Documentation Version:** 1.0.0

---

## Quick Reference Card

```
🌍 Main Endpoint: /api/v1/air-quality/
   Parameters: lat, lon, include_forecast, radius_km
   Returns: Current AQI, pollutants, location, health advice

💊 Health Advice: /api/v1/health-advice/
   Parameters: aqi, scale
   Returns: Category, color, health message

📋 Data Sources: /api/v1/sources/
   Parameters: None
   Returns: List of all data sources and status

❤️ Health Check: /api/v1/health/
   Parameters: None
   Returns: System status and adapter health

Rate Limit: 100 req/min
Cache: 10 minutes
Coverage: Global
Data Sources: 5
```

---

**Happy Coding! 🚀**

If you have questions or need examples for specific use cases, please reach out!
