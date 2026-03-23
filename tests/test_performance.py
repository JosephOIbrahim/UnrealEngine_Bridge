"""Performance tests for critical-path operations.

These tests verify that hot-path operations stay within latency budgets.
They are NOT integration tests — they exercise pure-Python logic only.
"""
from __future__ import annotations

import time

from remote_control_bridge import CircuitBreaker
from ue_mcp.metrics import metrics
from ue_mcp.tools._validation import validate_python_code


class TestCircuitBreakerPerformance:
    """Circuit breaker state transitions must be sub-millisecond."""

    def test_allow_request_latency(self):
        cb = CircuitBreaker()
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            cb.allow_request()
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 100, f"allow_request() took {avg_us:.1f}µs avg (budget: 100µs)"

    def test_state_transition_latency(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.001)
        start = time.perf_counter()
        for _ in range(1000):
            cb.record_failure()
            cb.record_failure()
            cb.record_success()
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / 1000) * 1_000_000
        assert avg_us < 1000, f"Full state cycle took {avg_us:.1f}µs avg (budget: 1000µs)"


class TestMetricsPerformance:
    """Metrics operations must be fast under load."""

    def setup_method(self):
        metrics.reset()

    def test_increment_throughput(self):
        start = time.perf_counter()
        for _ in range(10_000):
            metrics.inc("perf_test_counter")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"10K increments took {elapsed:.3f}s (budget: 0.1s)"

    def test_latency_recording_throughput(self):
        start = time.perf_counter()
        for i in range(1000):
            metrics.record_latency("perf_test", 0.001 * i)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.05, f"1K latency records took {elapsed:.3f}s (budget: 0.05s)"

    def test_snapshot_under_load(self):
        for i in range(100):
            metrics.inc(f"counter_{i}")
            metrics.record_latency(f"latency_{i}", 0.001 * i)
        start = time.perf_counter()
        for _ in range(100):
            metrics.snapshot()
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"100 snapshots took {elapsed:.3f}s (budget: 0.5s)"


class TestValidationPerformance:
    """Code validation must be fast for interactive use."""

    def test_simple_code_validation(self):
        code = """
import unreal, json
actors = unreal.EditorLevelLibrary.get_all_level_actors()
result = [a.get_actor_label() for a in actors]
print("RESULT:" + json.dumps({"actors": result}))
"""
        start = time.perf_counter()
        for _ in range(1000):
            validate_python_code(code)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"1K validations took {elapsed:.3f}s (budget: 0.5s)"

    def test_complex_code_validation(self):
        code = """
import unreal, json, math

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
result = []
for a in actors:
    loc = a.get_actor_location()
    rot = a.get_actor_rotation()
    result.append({
        "label": a.get_actor_label(),
        "class": a.get_class().get_name(),
        "location": [loc.x, loc.y, loc.z],
        "rotation": [rot.pitch, rot.yaw, rot.roll],
        "distance": math.sqrt(loc.x**2 + loc.y**2 + loc.z**2),
    })
print("RESULT:" + json.dumps({"actors": result, "count": len(result)}))
"""
        start = time.perf_counter()
        for _ in range(100):
            validate_python_code(code)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"100 complex validations took {elapsed:.3f}s (budget: 0.2s)"

    def test_blocked_code_detection_speed(self):
        """Blocked code should be detected quickly (fail-fast)."""
        blocked_codes = [
            "import subprocess",
            "import os; os.system('rm -rf /')",
            "eval('dangerous')",
            "getattr(os, 'system')",
            "import importlib",
        ]
        start = time.perf_counter()
        for _ in range(1000):
            for code in blocked_codes:
                validate_python_code(code)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"5K blocked validations took {elapsed:.3f}s (budget: 0.5s)"
