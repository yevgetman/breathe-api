"""
DRF serializers for the JASPR combined endpoint response.
"""
from rest_framework import serializers
from apps.api.serializers import LocationSerializer, PollutantSerializer


class PollenLevelSerializer(serializers.Serializer):
    level = serializers.CharField()
    value = serializers.FloatField(allow_null=True)


class PollenSerializer(serializers.Serializer):
    tree = PollenLevelSerializer(required=False)
    grass = PollenLevelSerializer(required=False)
    weed = PollenLevelSerializer(required=False)
    dominant_allergen = serializers.CharField(allow_null=True, required=False)


class JasprCurrentSerializer(serializers.Serializer):
    # Weather
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
    weather_code = serializers.IntegerField(allow_null=True, required=False)
    weather_description = serializers.CharField(default='')
    weather_icon = serializers.CharField(default='')
    sunrise = serializers.CharField(allow_null=True)
    sunset = serializers.CharField(allow_null=True)
    observation_time = serializers.CharField(default='')
    # Air quality
    aqi = serializers.IntegerField(allow_null=True)
    aqi_category = serializers.CharField(default='')
    dominant_pollutant = serializers.CharField(allow_null=True)
    pollutants = PollutantSerializer(required=False)
    pollen = PollenSerializer(required=False)
    health_advice = serializers.CharField(default='', allow_blank=True)


class JasprHourlySerializer(serializers.Serializer):
    # Weather
    time = serializers.CharField()
    temperature = serializers.FloatField(allow_null=True)
    feels_like = serializers.FloatField(allow_null=True)
    dew_point = serializers.FloatField(allow_null=True)
    humidity = serializers.IntegerField(allow_null=True)
    precipitation = serializers.FloatField(allow_null=True)
    precipitation_probability = serializers.IntegerField(allow_null=True)
    weather_code = serializers.IntegerField(allow_null=True)
    weather_description = serializers.CharField(default='')
    weather_icon = serializers.CharField(default='')
    cloud_cover = serializers.IntegerField(allow_null=True)
    visibility = serializers.FloatField(allow_null=True)
    wind_speed = serializers.FloatField(allow_null=True)
    wind_direction = serializers.IntegerField(allow_null=True)
    wind_gusts = serializers.FloatField(allow_null=True)
    is_day = serializers.IntegerField(allow_null=True)
    uv_index = serializers.FloatField(allow_null=True)
    # Air quality
    aqi = serializers.IntegerField(allow_null=True, required=False)
    aqi_category = serializers.CharField(default='', required=False)


class TodayVsAvgSerializer(serializers.Serializer):
    aqi_delta = serializers.IntegerField()
    trend = serializers.CharField()


class HistoricalSerializer(serializers.Serializer):
    aqi_avg_30d = serializers.FloatField(allow_null=True)
    aqi_min_30d = serializers.IntegerField(allow_null=True)
    aqi_max_30d = serializers.IntegerField(allow_null=True)
    today_vs_avg = TodayVsAvgSerializer(allow_null=True, required=False)


class HiddenGemSerializer(serializers.Serializer):
    text = serializers.CharField()
    type = serializers.CharField()


class JasprDailySerializer(serializers.Serializer):
    date = serializers.CharField()
    temp_high = serializers.FloatField(allow_null=True)
    temp_low = serializers.FloatField(allow_null=True)
    feels_like_high = serializers.FloatField(allow_null=True)
    feels_like_low = serializers.FloatField(allow_null=True)
    weather_code = serializers.IntegerField(allow_null=True, required=False)
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
    moon_phase = serializers.DictField(allow_null=True, required=False)
    golden_hour = serializers.DictField(allow_null=True, required=False)


class JasprResponseSerializer(serializers.Serializer):
    location = LocationSerializer()
    current = JasprCurrentSerializer()
    hourly_forecast = JasprHourlySerializer(many=True)
    daily_forecast = JasprDailySerializer(many=True)
    historical = HistoricalSerializer(allow_null=True, required=False)
    hidden_gems = HiddenGemSerializer(many=True, required=False)
    source = serializers.CharField(allow_blank=True)
    units = serializers.CharField()
    generated_at = serializers.CharField()
