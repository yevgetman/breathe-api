"""
Base adapter class for all air quality data sources.
"""
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional

import requests
from django.conf import settings
from django.utils import timezone
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .models import SourceData, RawAPIResponse, AdapterStatus

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Lightweight circuit breaker to fail fast when an external API is down.

    States:
      CLOSED  – requests flow normally
      OPEN    – requests are immediately rejected (fail fast)
      HALF_OPEN – a single probe request is allowed through to test recovery
    """

    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds before trying again
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._lock = threading.Lock()

    @property
    def state(self):
        with self._lock:
            if self._state == self.OPEN and self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
            return self._state

    def allow_request(self) -> bool:
        """Return True if the request should proceed."""
        return self.state != self.OPEN

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = self.CLOSED

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = self.OPEN


class BaseAdapter(ABC):
    """
    Abstract base class for all data source adapters.
    Provides common functionality for API calls, caching, error handling, and data normalization.
    """

    # Subclasses must define these
    SOURCE_NAME = None
    SOURCE_CODE = None
    API_BASE_URL = None
    REQUIRES_API_KEY = True
    QUALITY_LEVEL = 'verified'

    # Circuit breaker settings (overridable per adapter)
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60  # seconds

    def __init__(self):
        if not all([self.SOURCE_NAME, self.SOURCE_CODE, self.API_BASE_URL]):
            raise ValueError("Adapter must define SOURCE_NAME, SOURCE_CODE, and API_BASE_URL")

        self.settings = settings.AIR_QUALITY_SETTINGS
        self.api_key = self._get_api_key()
        self.session = self._create_session()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_timeout=self.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
        )
    
    # Map SOURCE_CODE to the key used in settings.API_KEYS.
    # Override in subclass if the mapping differs.
    API_KEY_SETTINGS_NAME = None

    def _get_api_key(self) -> Optional[str]:
        """Get API key from settings."""
        if not self.REQUIRES_API_KEY:
            return None

        key_name = self.API_KEY_SETTINGS_NAME or self.SOURCE_CODE
        api_key = settings.API_KEYS.get(key_name)
        if not api_key:
            logger.warning(f"No API key found for {self.SOURCE_NAME} (looked up '{key_name}')")

        return api_key
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.settings.get('MAX_RETRIES', 3),
            backoff_factor=self.settings.get('RETRY_BACKOFF_FACTOR', 2),
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]  # Updated from method_whitelist
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _make_request(
        self,
        endpoint: str,
        params: Dict = None,
        headers: Dict = None,
        method: str = 'GET'
    ) -> Optional[Dict]:
        """
        Make HTTP request with circuit breaker, error handling, and logging.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            headers: HTTP headers
            method: HTTP method

        Returns:
            Response data as dict or None on error
        """
        # Circuit breaker check – fail fast if API is known to be down
        if not self.circuit_breaker.allow_request():
            logger.warning(
                f"{self.SOURCE_NAME} circuit breaker OPEN – skipping request to {endpoint}"
            )
            return None

        url = f"{self.API_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        params = params or {}
        headers = headers or {}

        start_time = time.time()

        try:
            # Add API key to request
            self._add_api_key(params, headers)

            # Make request
            timeout = self.settings.get('REQUEST_TIMEOUT', 10)
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                timeout=timeout
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            # Log raw response (with sensitive params redacted)
            self._log_response(
                endpoint=endpoint,
                params=self._redact_params(params),
                response=response,
                response_time_ms=response_time_ms
            )

            # Check response
            response.raise_for_status()

            # Parse JSON safely
            try:
                data = response.json()
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"{self.SOURCE_NAME} returned invalid JSON from {endpoint}: {e}")
                self.circuit_breaker.record_failure()
                self._update_status(success=False, error_message=f"Invalid JSON: {e}")
                return None

            # Success – record in circuit breaker and adapter status
            self.circuit_breaker.record_success()
            self._update_status(success=True)

            return data

        except requests.exceptions.RequestException as e:
            # Sanitize error message to avoid leaking API keys from URLs
            safe_error = self._sanitize_error(str(e))
            logger.error(f"{self.SOURCE_NAME} API error: {safe_error}")

            response_time_ms = int((time.time() - start_time) * 1000)

            # Log error response
            self._log_response(
                endpoint=endpoint,
                params=self._redact_params(params),
                response=getattr(e, 'response', None),
                response_time_ms=response_time_ms,
                error=safe_error
            )

            # Record failure in circuit breaker and adapter status
            self.circuit_breaker.record_failure()
            self._update_status(success=False, error_message=safe_error)

            return None

    # Keys that should be redacted from logged params
    _SENSITIVE_PARAM_KEYS = frozenset({
        'api_key', 'API_KEY', 'key', 'token', 'appid', 'apikey',
    })

    def _redact_params(self, params: Dict) -> Dict:
        """Return a copy of params with sensitive values replaced by '***'."""
        if not params:
            return params
        redacted = {}
        for k, v in params.items():
            if k in self._SENSITIVE_PARAM_KEYS:
                redacted[k] = '***REDACTED***'
            else:
                redacted[k] = v
        return redacted

    def _sanitize_error(self, error_msg: str) -> str:
        """Remove API key values from error messages (e.g. URLs in exceptions)."""
        sanitized = error_msg
        if self.api_key and self.api_key in sanitized:
            sanitized = sanitized.replace(self.api_key, '***REDACTED***')
        return sanitized

    def _add_api_key(self, params: Dict, headers: Dict):
        """
        Add API key to request. Override in subclass if needed.
        Default: adds to query params as 'api_key'.
        """
        if self.REQUIRES_API_KEY and self.api_key:
            params['api_key'] = self.api_key
    
    def _log_response(
        self, 
        endpoint: str, 
        params: Dict, 
        response: Optional[requests.Response],
        response_time_ms: int,
        error: str = None
    ):
        """Log API response to database."""
        try:
            status_code = response.status_code if response else 0
            is_error = bool(error) or (status_code >= 400)
            
            response_data = {}
            if response:
                try:
                    response_data = response.json()
                except Exception:
                    response_data = {'raw': response.text[:1000]}
            
            RawAPIResponse.objects.create(
                source=self.SOURCE_CODE,
                endpoint=endpoint,
                params=params,
                response_data=response_data,
                status_code=status_code,
                response_time_ms=response_time_ms,
                is_error=is_error,
                error_message=error or ''
            )
        except Exception as e:
            logger.error(f"Failed to log API response: {e}")
    
    def _update_status(self, success: bool, error_message: str = ''):
        """Update adapter status metrics using atomic increments."""
        from django.db.models import F

        try:
            # Ensure the row exists
            AdapterStatus.objects.get_or_create(
                source=self.SOURCE_CODE,
                defaults={'is_active': True}
            )

            now = timezone.now()

            if success:
                AdapterStatus.objects.filter(source=self.SOURCE_CODE).update(
                    total_requests=F('total_requests') + 1,
                    last_success_at=now,
                    consecutive_failures=0,
                )
            else:
                AdapterStatus.objects.filter(source=self.SOURCE_CODE).update(
                    total_requests=F('total_requests') + 1,
                    total_failures=F('total_failures') + 1,
                    consecutive_failures=F('consecutive_failures') + 1,
                    last_failure_at=now,
                    status_message=error_message,
                )

            # Auto-disable after too many consecutive failures
            disabled_count = AdapterStatus.objects.filter(
                source=self.SOURCE_CODE,
                consecutive_failures__gte=10,
                is_active=True,
            ).update(is_active=False)
            if disabled_count:
                logger.error(f"{self.SOURCE_NAME} auto-disabled after 10+ consecutive failures")

        except Exception as e:
            logger.error(f"Failed to update adapter status: {e}")
    
    def normalize_data(self, raw_data: Dict, query_lat: float, query_lon: float) -> List[SourceData]:
        """
        Normalize raw API response to SourceData objects.
        Must be implemented by subclasses.
        
        Args:
            raw_data: Raw API response
            query_lat: Query latitude
            query_lon: Query longitude
            
        Returns:
            List of SourceData objects (not saved to DB)
        """
        raise NotImplementedError("Subclasses must implement normalize_data()")
    
    @abstractmethod
    def fetch_current(self, lat: float, lon: float, **kwargs) -> List[SourceData]:
        """
        Fetch current air quality data for coordinates.
        Must be implemented by subclasses.
        
        Args:
            lat: Latitude
            lon: Longitude
            **kwargs: Additional adapter-specific parameters
            
        Returns:
            List of SourceData objects
        """
        pass
    
    def fetch_forecast(self, lat: float, lon: float, **kwargs) -> List[Dict]:
        """
        Fetch forecast data (optional, override if supported).
        
        Args:
            lat: Latitude
            lon: Longitude
            **kwargs: Additional adapter-specific parameters
            
        Returns:
            List of forecast data dictionaries
        """
        return []
    
    def is_available(self) -> bool:
        """Check if adapter is available and healthy."""
        # Fail fast if circuit breaker is open
        if not self.circuit_breaker.allow_request():
            return False

        if not self.REQUIRES_API_KEY:
            return True

        if not self.api_key:
            return False

        try:
            status = AdapterStatus.objects.get(source=self.SOURCE_CODE)
            return status.is_healthy
        except AdapterStatus.DoesNotExist:
            return True
