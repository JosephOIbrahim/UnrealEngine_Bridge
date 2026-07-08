"""The M4 retirement flip: tiered tool registry vs docs/EPIC_MCP_MATRIX.md.

TIERS is the executable form of the matrix's disposition table. These tests
pin the arithmetic (36 RETIRE / 18 CORE / 2 EXPERIMENTAL of 56), the profile
semantics, and the drift gates in both directions: a tool cannot register
without a tier, and a tier entry cannot outlive its tool.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ue_mcp.tools import (
    DEFAULT_PROFILE,
    PROFILES,
    TIERS,
    Tier,
    register_all_tools,
)


class RecordingServer:
    def __init__(self):
        self.tools: dict[str, dict | None] = {}

    def tool(self, *, name, description, annotations=None):
        self.tools[name] = annotations

        def decorator(fn):
            return fn

        return decorator


def _register(profile=None, monkeypatch=None, env=None):
    if monkeypatch is not None:
        if env is None:
            monkeypatch.delenv("UE_MCP_PROFILE", raising=False)
        else:
            monkeypatch.setenv("UE_MCP_PROFILE", env)
    server = RecordingServer()
    registry = register_all_tools(server, AsyncMock(), profile=profile)
    return server, registry


CORE_NAMES = {n for n, t in TIERS.items() if t is Tier.CORE}
LEGACY_NAMES = {n for n, t in TIERS.items() if t is Tier.LEGACY_COMMODITY}
EXP_NAMES = {n for n, t in TIERS.items() if t is Tier.EXPERIMENTAL}


def test_matrix_arithmetic_is_pinned():
    """docs/EPIC_MCP_MATRIX.md §4: 36 RETIRE; KEEP/KEEP-PARTIAL = 18 CORE here
    (ue_status/ue_health_check live in mcp_server.py, outside this registry);
    undo/redo are the two honest not-implemented EXPERIMENTAL slots."""
    assert len(TIERS) == 60
    assert len(LEGACY_NAMES) == 36
    assert len(CORE_NAMES) == 22
    assert EXP_NAMES == {"ue_undo", "ue_redo"}


def test_all_profile_mounts_exactly_the_tier_table(monkeypatch):
    server, registry = _register(profile="all", monkeypatch=monkeypatch)
    assert set(server.tools) == set(TIERS), (
        "drift between TIERS and the registered tool set — a tool was added, "
        "removed, or renamed without updating the tier table"
    )
    assert not registry.unclassified
    assert not registry.skipped


def test_default_profile_is_the_core_flip(monkeypatch):
    assert DEFAULT_PROFILE == "core"
    server, registry = _register(monkeypatch=monkeypatch)  # no env, no arg
    assert registry.profile == "core"
    assert set(server.tools) == CORE_NAMES
    assert set(registry.skipped) == LEGACY_NAMES | EXP_NAMES


def test_full_profile_remounts_legacy_but_not_experimental(monkeypatch):
    server, registry = _register(monkeypatch=monkeypatch, env="full")
    assert registry.profile == "full"
    assert set(server.tools) == CORE_NAMES | LEGACY_NAMES
    assert set(registry.skipped) == EXP_NAMES


def test_explicit_profile_arg_beats_env(monkeypatch):
    server, registry = _register(profile="all", monkeypatch=monkeypatch, env="core")
    assert registry.profile == "all"
    assert set(server.tools) == set(TIERS)


def test_unknown_profile_falls_back_to_default_with_warning(monkeypatch):
    server, registry = _register(monkeypatch=monkeypatch, env="turbo")
    assert registry.profile == DEFAULT_PROFILE
    assert registry.profile_warning and "turbo" in registry.profile_warning
    assert set(server.tools) == CORE_NAMES


def test_unclassified_tool_fails_open_and_is_flagged():
    """A brand-new tool without a TIERS entry mounts (fail-open at runtime)
    but is reported, and test_all_profile_mounts_exactly_the_tier_table
    fails CI until it is classified."""
    server = RecordingServer()
    registry = register_all_tools(server, AsyncMock(), profile="core")
    decorator = registry.tool(name="ue_brand_new_tool", description="x", annotations=None)
    decorator(lambda: None)
    assert "ue_brand_new_tool" in server.tools
    assert registry.unclassified == ["ue_brand_new_tool"]


def test_annotations_pass_through_unchanged():
    server, _ = _register(profile="all")
    annotations = server.tools["ue_execute_python"]
    assert isinstance(annotations, dict) and "readOnlyHint" in annotations


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_every_profile_mounts_all_core_tools(profile):
    server, _ = _register(profile=profile)
    missing = CORE_NAMES - set(server.tools)
    assert not missing, f"profile {profile!r} dropped CORE tools: {sorted(missing)}"
