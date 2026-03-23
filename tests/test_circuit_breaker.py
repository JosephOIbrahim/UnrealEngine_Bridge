"""Tests for CircuitBreaker in remote_control_bridge.py."""

import time

import pytest

from remote_control_bridge import CircuitBreaker


class TestCircuitBreakerStates:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request()

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert not cb.allow_request()

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request()

    def test_success_resets_counter(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitBreaker.CLOSED

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        time.sleep(0.15)
        assert cb.allow_request()
        assert cb.state == CircuitBreaker.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # Transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # Transitions to HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN

    def test_fail_fast_error(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        error = cb.fail_fast_error()
        assert "error" in error
        assert "circuit breaker" in error["error"].lower()


class TestHalfOpenConcurrencyLimit:
    """Test that HALF_OPEN state only allows one probe request."""

    def test_half_open_allows_first_request(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        # Trip the breaker
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        # Wait for recovery
        time.sleep(0.15)
        assert cb.state == CircuitBreaker.HALF_OPEN
        # First request should be allowed
        assert cb.allow_request() is True

    def test_half_open_blocks_second_concurrent_request(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitBreaker.HALF_OPEN
        # First probe allowed
        assert cb.allow_request() is True
        # Second should be blocked (probe already in flight)
        assert cb.allow_request() is False

    def test_half_open_resets_after_success(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # first probe
        cb.record_success()  # probe succeeded
        # Should be CLOSED now, requests allowed
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    def test_half_open_resets_after_failure(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # first probe
        cb.record_failure()  # probe failed
        # Should be OPEN again
        assert cb.state == CircuitBreaker.OPEN
