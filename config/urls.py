"""
URL Configuration for Air Quality API project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from apps.api.views import DemoView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.api.urls')),
    path('demo/', DemoView.as_view(), name='demo'),
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
