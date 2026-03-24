"""
Admin configuration for core models.
"""
from django.contrib import admin
from .models import AQICategory, APIKey, DataSource


@admin.register(AQICategory)
class AQICategoryAdmin(admin.ModelAdmin):
    list_display = ['scale', 'category', 'min_value', 'max_value', 'color_hex']
    list_filter = ['scale']
    search_fields = ['category', 'health_message']
    ordering = ['scale', 'min_value']


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'key_prefix', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'key']
    readonly_fields = ['key', 'created_at', 'updated_at']

    def key_prefix(self, obj):
        return f"{obj.key[:8]}..."
    key_prefix.short_description = 'Key'


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'source_type', 'is_active', 'default_trust_weight']
    list_filter = ['source_type', 'is_active']
    search_fields = ['code', 'name', 'description']
    ordering = ['name']
