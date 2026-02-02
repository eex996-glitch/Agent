"""
Utilities Package

Provides logging, error handling, and common utilities.
"""

from .logger import (
    setup_logging,
    get_trade_logger,
    log_trade,
    log_execution_time,
    LogContext,
    logger
)

from .errors import (
    retry,
    retry_async,
    RetryConfig,
    RetryExhaustedError,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState,
    GracefulDegradation,
    API_RETRY_CONFIG,
    NETWORK_RETRY_CONFIG,
    validate_credentials
)

__all__ = [
    # Logging
    'setup_logging',
    'get_trade_logger',
    'log_trade',
    'log_execution_time',
    'LogContext',
    'logger',

    # Error handling
    'retry',
    'retry_async',
    'RetryConfig',
    'RetryExhaustedError',
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitOpenError',
    'CircuitState',
    'GracefulDegradation',
    'API_RETRY_CONFIG',
    'NETWORK_RETRY_CONFIG',
    'validate_credentials'
]
