"""
DRF serializers for weather API responses.
"""
from rest_framework import serializers
from apps.api.serializers import LocationSerializer


class CurrentWeatherSerializer(serializers.Serializer):
    temperature = serializers.FloatField(allow_null=True)
    feels_like = serializers.FloatField(allow_null=True)
    dew_point = serializers.FloatField(allow_null=True)
    humidity = serializers.IntegerField(allow_null=True)
    pressure = serializers.FloatField(allow_null=True)
    visibility = serializers.FloatField(allow_null=True)
    cloud_cover = serializers.IntegerField(allow_null=True)
    uv_index = serializers.FloatField(allow_null=True)
    wind_speed = serializers.FloatField(allow_null=True)
    wind_direction = serializers.IntegerField(allow_null=True)
    wind_gusts = serializers.FloatField(allow_null=True)
    weather_description = serializers.CharField()
    weather_icon = serializers.CharField()
    sunrise = serializers.CharField(allow_null=True)
    sunset = serializers.CharField(allow_null=True)
    observation_time = serializers.CharField()


class DailyForecastSerializer(serializers.Serializer):
    date = serializers.CharField()
    temp_high = serializers.FloatField(allow_null=True)
    temp_low = serializers.FloatField(allow_null=True)
    feels_like_high = serializers.FloatField(allow_null=True)
    feels_like_low = serializers.FloatField(allow_null=True)
    weather_description = serializers.CharField()
    weather_icon = serializers.CharField()
    precipitation_sum = serializers.FloatField(allow_null=True)
    precipitation_probability = serializers.IntegerField(allow_null=True)
    wind_speed_max = serializers.FloatField(allow_null=True)
    wind_gusts_max = serializers.FloatField(allow_null=True)
    wind_direction_dominant = serializers.IntegerField(allow_null=True)
    uv_index_max = serializers.FloatField(allow_null=True)
    sunrise = serializers.CharField(allow_null=True)
    sunset = serializers.CharField(allow_null=True)


class WeatherResponseSerializer(serializers.Serializer):
    location = LocationSerializer()
    current = CurrentWeatherSerializer(allow_null=True)
    daily_forecast = DailyForecastSerializer(many=True)
    source = serializers.CharField(allow_null=True)
    units = serializers.CharField()
