"""
Core models and base classes for Air Quality API.
"""
import secrets

from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides created_at and updated_at timestamps.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AQICategory(models.Model):
    """
    Lookup table for AQI categories and health advice.
    Supports both EPA (US) and AQHI (Canada) scales.
    """
    SCALE_CHOICES = [
        ('EPA', 'EPA AQI (US)'),
        ('AQHI', 'AQHI (Canada)'),
    ]

    scale = models.CharField(max_length=10, choices=SCALE_CHOICES, default='EPA')
    min_value = models.IntegerField()
    max_value = models.IntegerField()
    category = models.CharField(max_length=50)
    color_hex = models.CharField(max_length=7)  # e.g., #00E400
    health_message = models.TextField()
    sensitive_groups = models.TextField(blank=True)

    class Meta:
        verbose_name = 'AQI Category'
        verbose_name_plural = 'AQI Categories'
        ordering = ['scale', 'min_value']
        indexes = [
            models.Index(fields=['scale', 'min_value', 'max_value']),
        ]

    def __str__(self):
        return f"{self.scale}: {self.category} ({self.min_value}-{self.max_value})"

    @classmethod
    def get_category_for_aqi(cls, aqi_value, scale='EPA'):
        """Get category information for a given AQI value."""
        try:
            return cls.objects.get(
                scale=scale,
                min_value__lte=aqi_value,
                max_value__gte=aqi_value
            )
        except cls.DoesNotExist:
            return None


class APIKey(TimeStampedModel):
    """
    API key for authenticating client requests.
    Keys are 40-character hex tokens.
    """
    key = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=100, help_text="Label for this key, e.g. 'JASPR iOS App'")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-created_at']

    def __str__(self):
        prefix = self.key[:8]
        return f"{self.name} ({prefix}...)"

    @classmethod
    def generate(cls, name: str) -> 'APIKey':
        """Create a new API key with a random token."""
        return cls.objects.create(
            key=secrets.token_hex(20),
            name=name,
        )


class DataSource(models.Model):
    """
    Registry of air quality data sources.
    """
    SOURCE_TYPES = [
        ('OFFICIAL', 'Official Government'),
        ('SENSOR', 'Community Sensors'),
        ('MODEL', 'Atmospheric Model'),
        ('AGGREGATOR', 'Data Aggregator'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    description = models.TextField(blank=True)
    api_endpoint = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    requires_api_key = models.BooleanField(default=True)
    
    # Coverage
    countries_covered = models.JSONField(default=list)  # List of country codes
    
    # Rate limiting
    rate_limit_per_minute = models.IntegerField(default=60)
    
    # Default weight in fusion
    default_trust_weight = models.FloatField(default=1.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Data Source'
        verbose_name_plural = 'Data Sources'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"
