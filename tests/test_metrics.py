"""Tests for ue_mcp/metrics.py — in-process metrics collector."""

import time

import pytest

from ue_mcp.metrics import Metrics


class TestMetrics:
    def test_counter_increment(self):
        m = Metrics()
        m.inc("test.count")
        m.inc("test.count")
        m.inc("test.count", 3)
        snap = m.snapshot()
        assert snap["counters"]["test.count"] == 5

    def test_latency_recording(self):
        m = Metrics()
        m.record_latency("op", 0.1)
        m.record_latency("op", 0.2)
        m.record_latency("op", 0.3)
        snap = m.snapshot()
        stats = snap["latencies"]["op"]
        assert stats["count"] == 3
        assert stats["min_ms"] == pytest.approx(100.0, abs=1)
        assert stats["max_ms"] == pytest.approx(300.0, abs=1)
        assert stats["avg_ms"] == pytest.approx(200.0, abs=1)

    def test_uptime(self):
        m = Metrics()
        time.sleep(0.05)
        snap = m.snapshot()
        assert snap["uptime_s"] >= 0.04

    def test_reset(self):
        m = Metrics()
        m.inc("x")
        m.record_latency("y", 1.0)
        m.reset()
        snap = m.snapshot()
        assert snap["counters"] == {}
        assert snap["latencies"] == {}

    def test_rolling_window(self):
        m = Metrics()
        m._max_latency_samples = 5
        for i in range(10):
            m.record_latency("op", float(i))
        snap = m.snapshot()
        assert snap["latencies"]["op"]["count"] == 5

    def test_empty_snapshot(self):
        m = Metrics()
        snap = m.snapshot()
        assert snap["counters"] == {}
        assert snap["latencies"] == {}
        assert snap["uptime_s"] >= 0
