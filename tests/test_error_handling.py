"""
Tests for Error Handling and Retry Utilities
"""

import pytest
import time
from unittest.mock import Mock, patch, call

from utils.errors import (
    retry,
    RetryConfig,
    RetryExhaustedError,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState,
    GracefulDegradation,
    validate_credentials,
    calculate_delay
)


class TestRetryDecorator:
    """Tests for retry decorator"""

    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry"""
        call_count = 0

        @retry(RetryConfig(max_retries=3))
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self):
        """Test retry on transient failure"""
        call_count = 0

        @retry(RetryConfig(max_retries=3, base_delay=0.01))
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = failing_then_success()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self):
        """Test RetryExhaustedError after all retries fail"""
        @retry(RetryConfig(max_retries=2, base_delay=0.01))
        def always_fails():
            raise ConnectionError("Persistent failure")

        with pytest.raises(RetryExhaustedError):
            always_fails()

    def test_non_retryable_exception(self):
        """Test non-retryable exceptions aren't retried"""
        call_count = 0

        @retry(RetryConfig(
            max_retries=3,
            non_retryable_exceptions=(ValueError,)
        ))
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            raises_value_error()

        assert call_count == 1  # No retries

    def test_on_retry_callback(self):
        """Test on_retry callback is called"""
        callback = Mock()

        @retry(
            RetryConfig(max_retries=2, base_delay=0.01),
            on_retry=callback
        )
        def failing_func():
            raise ConnectionError("Failure")

        with pytest.raises(RetryExhaustedError):
            failing_func()

        assert callback.call_count == 2  # Called for each retry

    def test_exponential_backoff(self):
        """Test delay increases exponentially"""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=100.0,
            jitter=False
        )

        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0
        assert calculate_delay(3, config) == 8.0

    def test_max_delay_cap(self):
        """Test delay is capped at max_delay"""
        config = RetryConfig(
            base_delay=10.0,
            exponential_base=2.0,
            max_delay=50.0,
            jitter=False
        )

        # 10 * 2^5 = 320, but capped at 50
        assert calculate_delay(5, config) == 50.0


class TestCircuitBreaker:
    """Tests for circuit breaker pattern"""

    def test_initial_state_closed(self):
        """Test circuit starts in CLOSED state"""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_failures(self):
        """Test circuit opens after threshold failures"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))

        for _ in range(3):
            cb.record_failure(Exception("test"))

        assert cb.state == CircuitState.OPEN

    def test_rejects_when_open(self):
        """Test requests rejected when circuit is open"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure(Exception("test"))

        assert cb.can_execute() is False

    def test_transitions_to_half_open(self):
        """Test circuit transitions to half-open after timeout"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            timeout=0.01  # Very short timeout for testing
        ))

        cb.record_failure(Exception("test"))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.02)  # Wait for timeout

        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_successes(self):
        """Test circuit closes after success threshold in half-open"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            timeout=0.01
        ))

        # Open the circuit
        cb.record_failure(Exception("test"))
        time.sleep(0.02)

        # Record successes
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_decorator_usage(self):
        """Test circuit breaker as decorator"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))

        call_count = 0

        @cb
        def protected_func():
            nonlocal call_count
            call_count += 1
            return "success"

        # Should work initially
        assert protected_func() == "success"
        assert call_count == 1

        # Manually open circuit
        cb.record_failure(Exception("test"))
        cb.record_failure(Exception("test"))

        # Should raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            protected_func()

        assert call_count == 1  # Didn't execute


class TestGracefulDegradation:
    """Tests for graceful degradation"""

    def test_returns_value_on_success(self):
        """Test returns actual value when successful"""
        degradation = GracefulDegradation()

        @degradation.with_fallback(default_value="fallback")
        def successful_func():
            return "actual"

        assert successful_func() == "actual"

    def test_returns_fallback_on_failure(self):
        """Test returns fallback when function fails"""
        degradation = GracefulDegradation()

        @degradation.with_fallback(default_value="fallback")
        def failing_func():
            raise Exception("Failed")

        assert failing_func() == "fallback"

    def test_caches_successful_value(self):
        """Test caches successful value for later fallback"""
        degradation = GracefulDegradation()
        call_count = 0

        @degradation.with_fallback(default_value="default", cache_key="test")
        def sometimes_fails():
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise Exception("Failed")
            return "cached_value"

        # First call succeeds, value is cached
        assert sometimes_fails() == "cached_value"

        # Second call fails, returns cached value
        assert sometimes_fails() == "cached_value"


class TestCredentialValidation:
    """Tests for credential validation"""

    def test_valid_credentials(self):
        """Test valid credentials pass validation"""
        is_valid, errors = validate_credentials(
            username="testuser",
            password="testpass",
            cid="client123456",
            sec="secret1234567890"
        )

        assert is_valid is True
        assert len(errors) == 0

    def test_missing_username(self):
        """Test missing username fails validation"""
        is_valid, errors = validate_credentials(
            username="",
            password="testpass",
            cid="client123456",
            sec="secret1234567890"
        )

        assert is_valid is False
        assert "Username is required" in errors

    def test_missing_all_credentials(self):
        """Test all missing credentials reported"""
        is_valid, errors = validate_credentials(
            username="",
            password="",
            cid="",
            sec=""
        )

        assert is_valid is False
        assert len(errors) >= 4

    def test_short_cid_warning(self):
        """Test short CID produces error"""
        is_valid, errors = validate_credentials(
            username="testuser",
            password="testpass",
            cid="abc",  # Too short
            sec="secret1234567890"
        )

        assert is_valid is False
        assert any("Client ID" in e for e in errors)

    def test_short_secret_warning(self):
        """Test short secret produces error"""
        is_valid, errors = validate_credentials(
            username="testuser",
            password="testpass",
            cid="client123456",
            sec="short"  # Too short
        )

        assert is_valid is False
        assert any("Secret Key" in e for e in errors)
