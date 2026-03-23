from django.contrib import admin
from .models import WeatherObservation, DailyForecast


@admin.register(WeatherObservation)
class WeatherObservationAdmin(admin.ModelAdmin):
    list_display = ('lat', 'lon', 'source', 'temperature', 'weather_description', 'observation_time')
    list_filter = ('source',)
    search_fields = ('weather_description',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DailyForecast)
class DailyForecastAdmin(admin.ModelAdmin):
    list_display = ('lat', 'lon', 'source', 'forecast_date', 'temp_high', 'temp_low', 'weather_description')
    list_filter = ('source', 'forecast_date')
    readonly_fields = ('created_at', 'updated_at')
