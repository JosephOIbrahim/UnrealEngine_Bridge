"""Tests for structured console output parsers."""
from __future__ import annotations

from ue_mcp.tools._console_parsers import (
    parse_stat_fps,
    parse_stat_memory,
    parse_stat_unit,
    try_parse_output,
)


class TestStatFpsParser:
    def test_parses_fps_and_ms(self):
        output = "60.5 fps, 16.5 ms"
        result = parse_stat_fps(output)
        assert result is not None
        assert result["fps"] == 60.5
        assert result["frame_time_ms"] == 16.5

    def test_fps_only(self):
        result = parse_stat_fps("120 fps")
        assert result is not None
        assert result["fps"] == 120.0

    def test_no_match(self):
        result = parse_stat_fps("no data here")
        assert result is None


class TestStatUnitParser:
    def test_parses_frame_times(self):
        output = "Frame: 16.6 ms, Game: 2.1 ms, Draw: 5.3 ms, GPU: 8.2 ms"
        result = parse_stat_unit(output)
        assert result is not None
        assert result["frame_ms"] == 16.6
        assert result["game_ms"] == 2.1
        assert result["draw_ms"] == 5.3
        assert result["gpu_ms"] == 8.2

    def test_partial_data(self):
        result = parse_stat_unit("Frame: 33.3 ms")
        assert result is not None
        assert result["frame_ms"] == 33.3
        assert "game_ms" not in result

    def test_no_match(self):
        result = parse_stat_unit("nothing useful")
        assert result is None


class TestStatMemoryParser:
    def test_parses_mb(self):
        output = "Used Physical Memory: 4096.0 MB"
        result = parse_stat_memory(output)
        assert result is not None
        assert result["used_physical_mb"] == 4096.0

    def test_parses_gb(self):
        output = "Used Physical Memory: 4.0 GB"
        result = parse_stat_memory(output)
        assert result is not None
        assert result["used_physical_mb"] == 4096.0

    def test_no_match(self):
        result = parse_stat_memory("empty")
        assert result is None


class TestTryParseOutput:
    def test_known_command(self):
        result = try_parse_output("stat fps", "60 fps, 16.6 ms")
        assert result is not None
        assert result["fps"] == 60.0

    def test_unknown_command(self):
        result = try_parse_output("stat scenerendering", "some output")
        assert result is None

    def test_case_insensitive(self):
        result = try_parse_output("Stat FPS", "60 fps")
        assert result is not None
