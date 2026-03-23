"""
URL configuration for JASPR Weather endpoint.
"""
from django.urls import path
from .views import JasprWeatherView

app_name = 'jaspr'

urlpatterns = [
    path('', JasprWeatherView.as_view(), name='jaspr'),
]
