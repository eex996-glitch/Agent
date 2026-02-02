#!/usr/bin/env python3
"""
Error Handling and Retry Utilities
Provides robust error handling with exponential backoff and circuit breakers
"""

import time
import functools
from typing import Callable, Type, Tuple, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import threading


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout: float = 30.0  # Seconds before trying half-open
    excluded_exceptions: Tuple[Type[Exception], ...] = ()


class CircuitBreaker:
    """
    Circuit breaker pattern implementation

    Prevents cascading failures by failing fast when a service is down.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout:
                        self._state = CircuitState.HALF_OPEN
                        self._success_count = 0
                        logger.info(f"Circuit {self.name} transitioning to HALF_OPEN")
            return self._state

    def record_success(self) -> None:
        """Record a successful call"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(f"Circuit {self.name} CLOSED after recovery")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self, exception: Exception) -> None:
        """Record a failed call"""
        # Don't count excluded exceptions
        if isinstance(exception, self.config.excluded_exceptions):
            return

        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} OPEN again after failure in half-open")
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(f"Circuit {self.name} OPEN after {self._failure_count} failures")

    def can_execute(self) -> bool:
        """Check if request can be executed"""
        return self.state != CircuitState.OPEN

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self.can_execute():
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure(e)
                raise

        return wrapper


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class RetryExhaustedError(Exception):
    """Raised when all retries have been exhausted"""
    pass


def calculate_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """Calculate delay for retry attempt with exponential backoff"""
    import random

    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add random jitter (±25%)
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


def retry(
    config: RetryConfig = None,
    on_retry: Callable[[int, Exception, float], None] = None
) -> Callable:
    """
    Decorator for retrying failed operations with exponential backoff

    Args:
        config: Retry configuration
        on_retry: Callback called before each retry (attempt, exception, delay)

    Example:
        @retry(RetryConfig(max_retries=3, base_delay=1.0))
        def api_call():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except config.non_retryable_exceptions as e:
                    # Don't retry these
                    logger.error(f"{func.__name__} failed with non-retryable error: {e}")
                    raise

                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)

                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{config.max_retries + 1}): {e}. "
                            f"Retrying in {delay:.2f}s"
                        )

                        if on_retry:
                            on_retry(attempt, e, delay)

                        time.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {config.max_retries + 1} attempts: {e}"
                        )

            raise RetryExhaustedError(
                f"All {config.max_retries + 1} attempts failed for {func.__name__}"
            ) from last_exception

        return wrapper
    return decorator


def retry_async(config: RetryConfig = None) -> Callable:
    """Async version of retry decorator"""
    import asyncio

    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except config.non_retryable_exceptions as e:
                    raise

                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}): {e}. "
                            f"Retrying in {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)

            raise RetryExhaustedError(
                f"All attempts failed for {func.__name__}"
            ) from last_exception

        return wrapper
    return decorator


class GracefulDegradation:
    """
    Provides fallback values when primary operations fail

    Example:
        degradation = GracefulDegradation()

        @degradation.with_fallback(default_value=0.0)
        def get_price():
            return api.get_price()
    """

    def __init__(self):
        self._fallback_cache: dict = {}

    def with_fallback(
        self,
        default_value: Any = None,
        cache_successful: bool = True,
        cache_key: str = None
    ) -> Callable:
        """
        Decorator that returns fallback value on failure

        Args:
            default_value: Value to return on failure
            cache_successful: Cache successful results as fallback
            cache_key: Key for caching (default: function name)
        """
        def decorator(func: Callable) -> Callable:
            key = cache_key or func.__name__

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    result = func(*args, **kwargs)

                    if cache_successful:
                        self._fallback_cache[key] = result

                    return result

                except Exception as e:
                    logger.warning(f"{func.__name__} failed, using fallback: {e}")

                    # Try cached value first
                    if key in self._fallback_cache:
                        logger.info(f"Using cached value for {func.__name__}")
                        return self._fallback_cache[key]

                    # Use default
                    return default_value

            return wrapper
        return decorator


# Pre-configured retry configs for common scenarios
API_RETRY_CONFIG = RetryConfig(
    max_retries=4,
    base_delay=2.0,
    max_delay=16.0,
    exponential_base=2.0,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        OSError,
    )
)

NETWORK_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)


def validate_credentials(
    username: str,
    password: str,
    cid: str,
    sec: str
) -> Tuple[bool, List[str]]:
    """
    Validate trading credentials before use

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not username or not username.strip():
        errors.append("Username is required")

    if not password:
        errors.append("Password is required")

    if not cid or not cid.strip():
        errors.append("Client ID (CID) is required")

    if not sec or not sec.strip():
        errors.append("Secret Key (SEC) is required")

    # Basic format validation
    if cid and len(cid) < 5:
        errors.append("Client ID appears too short")

    if sec and len(sec) < 10:
        errors.append("Secret Key appears too short")

    return len(errors) == 0, errors
