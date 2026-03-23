"""Circuit breaker for UE5 connection resilience."""

import time

from .constants import (
    CB_FAILURE_THRESHOLD,
    CB_HALF_OPEN_MAX,
    CB_RECOVERY_TIMEOUT,
    logger,
)


class CircuitBreaker:
    """Simple circuit breaker for UE5 connection resilience.

    States:
    - CLOSED: normal operation, requests pass through
    - OPEN: failures exceeded threshold, requests fail-fast
    - HALF_OPEN: recovery timeout elapsed, allow one probe request
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = CB_FAILURE_THRESHOLD,
                 recovery_timeout: float = CB_RECOVERY_TIMEOUT):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_in_flight = 0

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = self.HALF_OPEN
                logger.info("Circuit breaker -> HALF_OPEN (attempting recovery)")
        return self._state

    def allow_request(self) -> bool:
        s = self.state
        if s == self.CLOSED:
            return True
        if s == self.HALF_OPEN:
            if self._half_open_in_flight < CB_HALF_OPEN_MAX:
                self._half_open_in_flight += 1
                return True
            return False  # probe already in flight
        return False  # OPEN

    def record_success(self):
        if self._state in (self.HALF_OPEN, self.OPEN):
            logger.info("Circuit breaker -> CLOSED (connection recovered)")
        self._state = self.CLOSED
        self._failure_count = 0
        self._half_open_in_flight = 0

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        self._half_open_in_flight = 0
        if self._failure_count >= self.failure_threshold:
            if self._state != self.OPEN:
                logger.warning(
                    "Circuit breaker -> OPEN after %d failures (cooldown %.0fs)",
                    self._failure_count, self.recovery_timeout,
                )
            self._state = self.OPEN

    def fail_fast_error(self) -> dict:
        wait = max(0, self.recovery_timeout - (time.time() - self._last_failure_time))
        return {
            "result": None,
            "output": "",
            "error": f"Circuit breaker OPEN — UE5 editor unreachable after {self._failure_count} "
                     f"consecutive failures. Retry in {wait:.0f}s, or restart the editor.",
        }
