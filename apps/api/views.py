"""
API views for air quality endpoints.
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.shortcuts import render
from django.views import View

from apps.core.utils import validate_coordinates
from .orchestrator import AirQualityOrchestrator
from .serializers import AirQualityResponseSerializer, ErrorSerializer

logger = logging.getLogger(__name__)


class AirQualityView(APIView):
    """
    Main endpoint for fetching air quality data.
    
    GET /api/v1/air-quality/?lat=34.05&lon=-118.24&include_forecast=true
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator = AirQualityOrchestrator()
    
    def get(self, request):
        """
        Get air quality data for coordinates.
        
        Query parameters:
        - lat (required): Latitude
        - lon (required): Longitude
        - include_forecast (optional): Include forecast data (true/false)
        - radius_km (optional): Search radius for sensors (default: 25)
        - no_cache (optional): Skip cache (true/false)
        """
        # Extract and validate parameters
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        
        if not lat or not lon:
            return Response(
                {'error': 'Missing required parameters: lat and lon'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate coordinates
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid coordinate format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_valid, error_message = validate_coordinates(lat, lon)
        if not is_valid:
            return Response(
                {'error': error_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Optional parameters
        include_forecast = request.query_params.get('include_forecast', 'false').lower() == 'true'
        no_cache = request.query_params.get('no_cache', 'false').lower() == 'true'
        
        try:
            radius_km = float(request.query_params.get('radius_km', 25))
            # Limit radius
            radius_km = min(radius_km, 100)
        except (TypeError, ValueError):
            radius_km = 25
        
        try:
            # Fetch air quality data
            result = self.orchestrator.get_air_quality(
                lat=lat,
                lon=lon,
                include_forecast=include_forecast,
                radius_km=radius_km,
                use_cache=not no_cache
            )
            
            # Serialize and return
            serializer = AirQualityResponseSerializer(data=result)
            if serializer.is_valid():
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                # Return raw result if serialization fails
                return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching air quality data: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'detail': str(e) if request.user.is_staff else 'Unable to fetch air quality data'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthAdviceView(APIView):
    """
    Get health advice for a given AQI value.
    
    GET /api/v1/health-advice/?aqi=72&scale=EPA
    """
    
    def get(self, request):
        """Get health advice for AQI value."""
        aqi = request.query_params.get('aqi')
        scale = request.query_params.get('scale', 'EPA').upper()
        
        if not aqi:
            return Response(
                {'error': 'Missing required parameter: aqi'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            aqi = int(aqi)
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid AQI value'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.core.utils import convert_aqi_to_category
        
        category_info = convert_aqi_to_category(aqi, scale=scale)
        
        if not category_info:
            return Response(
                {'error': 'Invalid AQI value or scale'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'aqi': aqi,
            'scale': scale,
            'category': category_info['category'],
            'color': category_info['color_hex'],
            'health_message': category_info['health_message'],
            'sensitive_groups': category_info.get('sensitive_groups', ''),
        })


class SourcesView(APIView):
    """
    List available data sources and their status.
    
    GET /api/v1/sources/
    """
    
    def get(self, request):
        """List all data sources and their health status."""
        from apps.adapters.models import AdapterStatus
        from apps.core.models import DataSource
        
        sources = []
        
        # Get all data sources
        for data_source in DataSource.objects.filter(is_active=True):
            # Get adapter status if available
            try:
                adapter_status = AdapterStatus.objects.get(source=data_source.code)
                health_status = {
                    'is_healthy': adapter_status.is_healthy,
                    'success_rate': round(adapter_status.success_rate, 2),
                    'last_success': adapter_status.last_success_at.isoformat() if adapter_status.last_success_at else None,
                    'consecutive_failures': adapter_status.consecutive_failures,
                }
            except AdapterStatus.DoesNotExist:
                health_status = {
                    'is_healthy': True,
                    'success_rate': None,
                    'last_success': None,
                    'consecutive_failures': 0,
                }
            
            sources.append({
                'code': data_source.code,
                'name': data_source.name,
                'type': data_source.source_type,
                'description': data_source.description,
                'countries': data_source.countries_covered,
                'trust_weight': data_source.default_trust_weight,
                'status': health_status,
            })
        
        return Response({'sources': sources})


class HealthCheckView(APIView):
    """
    Health check endpoint for monitoring.
    
    GET /api/v1/health/
    """
    
    def get(self, request):
        """Check system health."""
        from django.db import connection
        from apps.adapters.models import AdapterStatus
        
        health = {
            'status': 'healthy',
            'database': False,
            'cache': False,
            'adapters': {},
        }
        
        # Check database
        try:
            connection.ensure_connection()
            health['database'] = True
        except Exception as e:
            health['status'] = 'unhealthy'
            logger.error(f"Database health check failed: {e}")
        
        # Check cache
        try:
            cache.set('health_check', 'ok', 10)
            cache_value = cache.get('health_check')
            health['cache'] = (cache_value == 'ok')
            if not health['cache']:
                health['status'] = 'degraded'
        except Exception as e:
            health['status'] = 'degraded'
            logger.error(f"Cache health check failed: {e}")
        
        # Check adapters
        try:
            for adapter_status in AdapterStatus.objects.all():
                health['adapters'][adapter_status.source] = adapter_status.is_healthy
        except Exception as e:
            logger.error(f"Adapter health check failed: {e}")
        
        # Determine overall status
        if health['status'] == 'healthy' and not all(health['adapters'].values()):
            health['status'] = 'degraded'
        
        status_code = status.HTTP_200_OK if health['status'] != 'unhealthy' else status.HTTP_503_SERVICE_UNAVAILABLE
        
        return Response(health, status=status_code)


class DemoView(View):
    """
    Interactive demo page with world map.
    
    GET /demo/
    """
    
    def get(self, request):
        """Render the demo page."""
        return render(request, 'demo.html')
