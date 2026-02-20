"""Lightweight in-process metrics for ue-bridge observability.

No external dependencies — tracks counters, latencies, and circuit breaker state
in memory. Exposed via the ue_health_check MCP tool.
"""

from __future__ import annotations

import time
import threading
from collections import defaultdict
from typing import Any


class Metrics:
    """Thread-safe in-process metrics collector."""

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._max_latency_samples = 100  # rolling window per key

    def inc(self, name: str, delta: int = 1) -> None:
        """Increment a counter."""
        with self._lock:
            self._counters[name] += delta

    def record_latency(self, name: str, duration_s: float) -> None:
        """Record a latency sample (seconds)."""
        with self._lock:
            samples = self._latencies[name]
            samples.append(duration_s)
            if len(samples) > self._max_latency_samples:
                self._latencies[name] = samples[-self._max_latency_samples:]

    def snapshot(self) -> dict[str, Any]:
        """Return a point-in-time snapshot of all metrics."""
        with self._lock:
            uptime = time.monotonic() - self._start_time
            latency_stats = {}
            for key, samples in self._latencies.items():
                if samples:
                    sorted_s = sorted(samples)
                    latency_stats[key] = {
                        "count": len(sorted_s),
                        "min_ms": round(sorted_s[0] * 1000, 1),
                        "max_ms": round(sorted_s[-1] * 1000, 1),
                        "avg_ms": round(sum(sorted_s) / len(sorted_s) * 1000, 1),
                        "p95_ms": round(sorted_s[int(len(sorted_s) * 0.95)] * 1000, 1),
                    }
            return {
                "uptime_s": round(uptime, 1),
                "counters": dict(self._counters),
                "latencies": latency_stats,
            }

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._counters.clear()
            self._latencies.clear()
            self._start_time = time.monotonic()


# Singleton instance
metrics = Metrics()
