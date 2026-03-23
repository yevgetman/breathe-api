"""
URL Configuration for Air Quality API project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from apps.api.views import HomeView, DemoView, StatusView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.api.urls')),
    path('api/v1/weather/', include('apps.weather.urls')),
    path('api/v1/jaspr/', include('apps.jaspr.urls')),
    path('demo/', DemoView.as_view(), name='demo'),
    path('status/', StatusView.as_view(), name='status'),
]

# Add debug toolbar URLs in development
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
