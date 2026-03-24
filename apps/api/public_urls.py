"""
URL routing for public (no-auth) API endpoints used by the demo page.
"""
from django.urls import path
from .public_views import PublicAirQualityView, PublicWeatherView, PublicJasprView

app_name = 'public'

urlpatterns = [
    path('air-quality/', PublicAirQualityView.as_view(), name='air-quality'),
    path('weather/', PublicWeatherView.as_view(), name='weather'),
    path('jaspr/', PublicJasprView.as_view(), name='jaspr'),
]
