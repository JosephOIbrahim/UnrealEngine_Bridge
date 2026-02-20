"""Tests for usd_bridge.py — USDA file operations, path validation, checksums."""

import pytest

from usd_bridge import (
    _validate_bridge_path,
    _atomic_write,
    _safe_read,
    write_question_usda,
    read_answer_usda,
    set_variant,
    write_ready_usda,
    validate_bridge_state,
    compute_checksum,
    generate_exec_anchor,
    parse_exec_anchor,
    get_expert_from_signals,
    DEFAULT_BRIDGE_PATH,
)
from pathlib import Path
import re


# ── Path validation ──────────────────────────────────────────────────────────

class TestValidateBridgePath:
    def test_default_path_accepted(self):
        result = _validate_bridge_path(None)
        assert result == DEFAULT_BRIDGE_PATH.resolve()

    def test_traversal_rejected(self):
        evil_path = DEFAULT_BRIDGE_PATH / ".." / ".." / "etc"
        with pytest.raises(ValueError, match="outside the allowed"):
            _validate_bridge_path(evil_path)


# ── Atomic write / safe read ─────────────────────────────────────────────────

class TestAtomicIO:
    def test_write_and_read(self, tmp_path):
        f = tmp_path / "test.usda"
        _atomic_write(f, "#usda 1.0\nhello")
        content = _safe_read(f)
        assert content == "#usda 1.0\nhello"

    def test_safe_read_missing_file(self, tmp_path):
        assert _safe_read(tmp_path / "nonexistent.usda", retries=1) is None


# ── Question writing ─────────────────────────────────────────────────────────

class TestWriteQuestion:
    def test_creates_file(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        path = write_question_usda(
            question_id="test_q1",
            text="Test question?",
            options=[
                {"label": "Option A", "direction": "low"},
                {"label": "Option B", "direction": "high"},
                {"label": "Option C", "direction": "mid"},
            ],
            index=0,
            total=8,
            bridge_path=tmp_bridge_dir,
        )
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "#usda 1.0" in content
        assert "question_pending" in content
        assert "test_q1" in content
        assert "Option A" in content

    def test_incremental_update(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        # First write
        write_question_usda(
            question_id="q1", text="First?",
            options=[{"label": "A", "direction": "low"}],
            index=0, total=2, bridge_path=tmp_bridge_dir,
        )
        # Second write should do incremental update
        write_question_usda(
            question_id="q2", text="Second?",
            options=[{"label": "B", "direction": "high"}],
            index=1, total=2, bridge_path=tmp_bridge_dir,
        )
        content = (tmp_bridge_dir / "bridge_state.usda").read_text(encoding="utf-8")
        assert "q2" in content
        assert "Second?" in content


# ── Answer reading ───────────────────────────────────────────────────────────

class TestReadAnswer:
    def test_no_answer_when_pending(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        write_question_usda(
            question_id="q1", text="Test?",
            options=[{"label": "A", "direction": "low"}],
            index=0, total=1, bridge_path=tmp_bridge_dir,
        )
        result = read_answer_usda(bridge_path=tmp_bridge_dir)
        assert result is None  # No answer yet

    def test_reads_answer_after_set(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        write_question_usda(
            question_id="q1", text="Test?",
            options=[{"label": "A", "direction": "low"}],
            index=0, total=1, bridge_path=tmp_bridge_dir,
        )
        # Simulate UE5 writing an answer by modifying the file
        f = tmp_bridge_dir / "bridge_state.usda"
        content = f.read_text(encoding="utf-8")
        content = content.replace('string sync_status = "question_pending"',
                                   'string sync_status = "answer_received"')
        content = re.sub(r'int option_index = -1', 'int option_index = 1', content)
        content = re.sub(r'string question_id = ""',
                          'string question_id = "q1"', content, count=1)
        f.write_text(content, encoding="utf-8")

        result = read_answer_usda(bridge_path=tmp_bridge_dir)
        assert result is not None
        assert result["question_id"] == "q1"
        assert result["option_index"] == 1


# ── Variant setting ──────────────────────────────────────────────────────────

class TestSetVariant:
    def test_set_sync_status(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        write_question_usda(
            question_id="q1", text="Test?",
            options=[{"label": "A", "direction": "low"}],
            index=0, total=1, bridge_path=tmp_bridge_dir,
        )
        assert set_variant("sync_status", "idle", bridge_path=tmp_bridge_dir)
        content = (tmp_bridge_dir / "bridge_state.usda").read_text(encoding="utf-8")
        assert 'string sync_status = "idle"' in content

    def test_set_nonexistent_file(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        assert not set_variant("sync_status", "idle", bridge_path=tmp_bridge_dir)


# ── Ready state ──────────────────────────────────────────────────────────────

class TestWriteReady:
    def test_creates_ready_state(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        path = write_ready_usda(total_questions=8, bridge_path=tmp_bridge_dir)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert 'message_type = "ready"' in content
        assert 'sync_status = "idle"' in content


# ── Validation ───────────────────────────────────────────────────────────────

class TestValidateBridgeState:
    def test_valid_file(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        write_ready_usda(bridge_path=tmp_bridge_dir)
        result = validate_bridge_state(bridge_path=tmp_bridge_dir)
        assert result["valid"]
        assert result["file_exists"]
        assert len(result["errors"]) == 0

    def test_missing_file(self, tmp_bridge_dir, monkeypatch):
        monkeypatch.setattr("usd_bridge.DEFAULT_BRIDGE_PATH", tmp_bridge_dir)
        result = validate_bridge_state(bridge_path=tmp_bridge_dir)
        assert not result["valid"]
        assert not result["file_exists"]


# ── Checksum determinism ─────────────────────────────────────────────────────

class TestChecksum:
    def test_deterministic(self):
        dims = {"cognitive_density": 0.7, "home_altitude": 0.3, "guidance_frequency": 0.5}
        c1 = compute_checksum(dims)
        c2 = compute_checksum(dims)
        assert c1 == c2

    def test_order_independent(self):
        from collections import OrderedDict
        dims_a = OrderedDict([("b", 0.5), ("a", 0.3)])
        dims_b = OrderedDict([("a", 0.3), ("b", 0.5)])
        assert compute_checksum(dims_a) == compute_checksum(dims_b)

    def test_different_values_different_checksum(self):
        d1 = {"a": 0.1}
        d2 = {"a": 0.9}
        assert compute_checksum(d1) != compute_checksum(d2)

    def test_8_char_hex(self):
        result = compute_checksum({"x": 1})
        assert len(result) == 8
        assert all(c in "0123456789abcdef" for c in result)


# ── EXEC anchors ─────────────────────────────────────────────────────────────

class TestExecAnchor:
    def test_generate_and_parse(self):
        anchor = generate_exec_anchor("abcdef01", "Direct", "Cortex", "Ground")
        parsed = parse_exec_anchor(anchor)
        assert parsed is not None
        assert parsed["checksum"] == "abcdef01"
        assert parsed["expert"] == "Direct"
        assert parsed["paradigm"] == "Cortex"
        assert parsed["altitude"] == "Ground"

    def test_parse_invalid(self):
        assert parse_exec_anchor("not an anchor") is None


# ── Expert routing ───────────────────────────────────────────────────────────

class TestExpertRouting:
    def test_default_is_direct(self):
        assert get_expert_from_signals({"detected_state": "focused"}) == "Direct"

    def test_frustrated_routes_validator(self):
        assert get_expert_from_signals({"detected_state": "frustrated"}) == "Validator"

    def test_red_burnout_routes_validator(self):
        assert get_expert_from_signals({"burnout_level": "RED"}) == "Validator"

    def test_stuck_routes_scaffolder(self):
        assert get_expert_from_signals({"detected_state": "stuck"}) == "Scaffolder"

    def test_depleted_routes_restorer(self):
        assert get_expert_from_signals({"detected_state": "depleted"}) == "Restorer"

    def test_exploring_routes_socratic(self):
        assert get_expert_from_signals({"detected_state": "exploring"}) == "Socratic"

    def test_rapid_clicks_routes_validator(self):
        signals = {"detected_state": "focused", "rapid_click_count": 5}
        assert get_expert_from_signals(signals) == "Validator"

    def test_priority_order_frustrated_over_stuck(self):
        signals = {"detected_state": "frustrated", "hesitation_count": 5}
        assert get_expert_from_signals(signals) == "Validator"
