"""
URL routing for API endpoints.
"""
from django.urls import path, include
from .views import AirQualityView, HealthAdviceView, SourcesView, HealthCheckView

app_name = 'api'

urlpatterns = [
    path('air-quality/', AirQualityView.as_view(), name='air-quality'),
    path('health-advice/', HealthAdviceView.as_view(), name='health-advice'),
    path('sources/', SourcesView.as_view(), name='sources'),
    path('health/', HealthCheckView.as_view(), name='health'),
    path('public/', include('apps.api.public_urls')),
]
