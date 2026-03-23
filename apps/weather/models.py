"""
Models for weather data caching.
"""
from django.db import models
from apps.core.models import TimeStampedModel


class WeatherObservation(TimeStampedModel):
    """
    Cached current weather observation for a location.
    """
    # Location (rounded to 3 decimal places for cache key)
    lat = models.DecimalField(max_digits=9, decimal_places=6, db_index=True)
    lon = models.DecimalField(max_digits=9, decimal_places=6, db_index=True)

    # Source adapter
    source = models.CharField(max_length=50, db_index=True)

    # Observation timestamp
    observation_time = models.DateTimeField(db_index=True)

    # Temperature (Celsius)
    temperature = models.FloatField(null=True)
    feels_like = models.FloatField(null=True)
    dew_point = models.FloatField(null=True)

    # Atmosphere
    humidity = models.IntegerField(null=True)       # percentage 0-100
    pressure = models.FloatField(null=True)         # hPa
    visibility = models.FloatField(null=True)       # meters
    cloud_cover = models.IntegerField(null=True)    # percentage 0-100
    uv_index = models.FloatField(null=True)

    # Wind
    wind_speed = models.FloatField(null=True)       # m/s
    wind_direction = models.IntegerField(null=True) # degrees 0-360
    wind_gusts = models.FloatField(null=True)       # m/s

    # Conditions
    weather_code = models.IntegerField(null=True)
    weather_description = models.CharField(max_length=100, blank=True)
    weather_icon = models.CharField(max_length=50, blank=True)

    # Sun
    sunrise = models.DateTimeField(null=True)
    sunset = models.DateTimeField(null=True)

    # Cache control
    cached_until = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = 'Weather Observation'
        verbose_name_plural = 'Weather Observations'
        ordering = ['-observation_time']
        indexes = [
            models.Index(fields=['lat', 'lon', '-observation_time']),
            models.Index(fields=['cached_until']),
        ]

    def __str__(self):
        return f"{self.temperature}°C at ({self.lat}, {self.lon}) - {self.weather_description}"


class DailyForecast(TimeStampedModel):
    """
    Cached daily weather forecast entry.
    """
    lat = models.DecimalField(max_digits=9, decimal_places=6, db_index=True)
    lon = models.DecimalField(max_digits=9, decimal_places=6, db_index=True)
    source = models.CharField(max_length=50, db_index=True)

    forecast_date = models.DateField(db_index=True)

    # Temperature range (Celsius)
    temp_high = models.FloatField(null=True)
    temp_low = models.FloatField(null=True)
    feels_like_high = models.FloatField(null=True)
    feels_like_low = models.FloatField(null=True)

    # Conditions
    weather_code = models.IntegerField(null=True)
    weather_description = models.CharField(max_length=100, blank=True)
    weather_icon = models.CharField(max_length=50, blank=True)

    # Precipitation
    precipitation_sum = models.FloatField(null=True)            # mm
    precipitation_probability = models.IntegerField(null=True)  # %

    # Wind
    wind_speed_max = models.FloatField(null=True)               # m/s
    wind_gusts_max = models.FloatField(null=True)               # m/s
    wind_direction_dominant = models.IntegerField(null=True)     # degrees

    # UV
    uv_index_max = models.FloatField(null=True)

    # Sun
    sunrise = models.DateTimeField(null=True)
    sunset = models.DateTimeField(null=True)

    # Cache control
    cached_until = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = 'Daily Forecast'
        verbose_name_plural = 'Daily Forecasts'
        ordering = ['forecast_date']
        unique_together = [['lat', 'lon', 'source', 'forecast_date']]
        indexes = [
            models.Index(fields=['lat', 'lon', 'forecast_date']),
            models.Index(fields=['cached_until']),
        ]

    def __str__(self):
        return f"{self.forecast_date}: {self.temp_high}°/{self.temp_low}° at ({self.lat}, {self.lon})"
