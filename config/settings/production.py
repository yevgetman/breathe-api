"""
Production settings for Air Quality API project.
"""
from .base import *

DEBUG = False

# Security settings for production
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Only allow specific hosts in production
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Use specific CORS origins in production
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

# Production logging - use console for Heroku
# Heroku aggregates logs from stdout/stderr
LOGGING['handlers'].pop('file', None)  # Remove file handler for Heroku
LOGGING['root']['handlers'] = ['console']
LOGGING['root']['level'] = 'INFO'
LOGGING['loggers']['django']['handlers'] = ['console']
LOGGING['loggers']['apps']['handlers'] = ['console']
LOGGING['loggers']['apps']['level'] = 'INFO'

# Static files handling with WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Email configuration for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='localhost')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

# Sentry integration (optional)
if env('SENTRY_DSN', default=''):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    
    sentry_sdk.init(
        dsn=env('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
