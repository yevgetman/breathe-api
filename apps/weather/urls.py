"""
URL routing for weather endpoints.
"""
from django.urls import path
from .views import WeatherView

app_name = 'weather'

urlpatterns = [
    path('', WeatherView.as_view(), name='weather'),
]
