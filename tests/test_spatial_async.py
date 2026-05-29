"""Tests for ue_mcp/tools/spatial.py — spatial reasoning / world-building tools."""

import ast
import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools._validation import sanitize_label
from ue_mcp.tools.spatial import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


def _gen_code(mock_ue):
    """The UE5 Python the tool generated on its last execute_python call."""
    return mock_ue.execute_python.call_args[0][0]


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


class TestValidation:
    def test_label_rejects_injection(self):
        assert sanitize_label('x"; import os', "actor_label") is not None

    def test_label_rejects_newline(self):
        # The hardened label regex must reject embedded line terminators.
        assert sanitize_label("Rock\nimport os", "actor_label") is not None

    def test_label_accepts_valid(self):
        assert sanitize_label("Rock_01", "actor_label") is None


# --------------------------------------------------------------------------- #
# ue_ground_trace
# --------------------------------------------------------------------------- #


class TestGroundTrace:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_ground_trace")
        result = await fn(x=100.0, y=200.0)
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_parses_and_traces(self, server, mock_ue):
        fn = _call(server, "ue_ground_trace")
        await fn(x=100.0, y=200.0, start_z=5000.0)
        code = _gen_code(mock_ue)
        ast.parse(code)  # generated Python must be syntactically valid
        assert "line_trace_single" in code
        assert "_ground_hit" in code
        assert "100.0" in code and "200.0" in code


# --------------------------------------------------------------------------- #
# ue_snap_to_ground
# --------------------------------------------------------------------------- #


class TestSnapToGround:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_snap_to_ground")
        result = await fn(actor_label="Rock_01")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert "Rock_01" in code
        assert "set_actor_location" in code
        # No-align path should not align rotation.
        assert "aligned = False" in code

    @pytest.mark.asyncio
    async def test_align_to_normal_emits_rotation(self, server, mock_ue):
        fn = _call(server, "ue_snap_to_ground")
        await fn(actor_label="Statue", align_to_normal=True)
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert "make_rot_from_z" in code
        assert "aligned = True" in code

    @pytest.mark.asyncio
    async def test_ignores_self_in_trace(self, server, mock_ue):
        fn = _call(server, "ue_snap_to_ground")
        await fn(actor_label="Crate")
        code = _gen_code(mock_ue)
        assert "[actor]" in code  # actor passed as ignore-list

    @pytest.mark.asyncio
    async def test_rejects_empty_label(self, server, mock_ue):
        fn = _call(server, "ue_snap_to_ground")
        result = await fn(actor_label="")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_injection_label(self, server, mock_ue):
        fn = _call(server, "ue_snap_to_ground")
        result = await fn(actor_label='Rock"; import os')
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


# --------------------------------------------------------------------------- #
# ue_spatial_query
# --------------------------------------------------------------------------- #


class TestSpatialQuery:
    @pytest.mark.asyncio
    async def test_nearest_code_parses(self, server, mock_ue):
        fn = _call(server, "ue_spatial_query")
        result = await fn(mode="nearest", x=0.0, y=0.0, z=0.0, count=3)
        data = json.loads(result)
        assert "error" not in data
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert 'mode = "nearest"' in code

    @pytest.mark.asyncio
    async def test_overlap_requires_both_actors(self, server, mock_ue):
        fn = _call(server, "ue_spatial_query")
        result = await fn(mode="overlap", actor_a="A")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_overlap_happy(self, server, mock_ue):
        fn = _call(server, "ue_spatial_query")
        result = await fn(mode="overlap", actor_a="Wall_A", actor_b="Wall_B")
        data = json.loads(result)
        assert "error" not in data
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert "Wall_A" in code and "Wall_B" in code

    @pytest.mark.asyncio
    async def test_combined_bounds_with_class_filter(self, server, mock_ue):
        fn = _call(server, "ue_spatial_query")
        result = await fn(mode="combined_bounds", class_filter="StaticMeshActor")
        data = json.loads(result)
        assert "error" not in data
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert "StaticMeshActor" in code

    @pytest.mark.asyncio
    async def test_box_contents_code_parses(self, server, mock_ue):
        fn = _call(server, "ue_spatial_query")
        await fn(mode="box_contents", x=0.0, y=0.0, z=0.0, extent_x=500.0, extent_y=500.0, extent_z=500.0)
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert 'mode = "box_contents"' in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_mode(self, server, mock_ue):
        fn = _call(server, "ue_spatial_query")
        result = await fn(mode="teleport")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_bad_class_filter(self, server, mock_ue):
        fn = _call(server, "ue_spatial_query")
        result = await fn(mode="combined_bounds", class_filter="1Bad;Class")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


# --------------------------------------------------------------------------- #
# ue_measure
# --------------------------------------------------------------------------- #


class TestMeasure:
    @pytest.mark.asyncio
    async def test_distance_happy(self, server, mock_ue):
        fn = _call(server, "ue_measure")
        result = await fn(mode="distance", actor_a="A", actor_b="B")
        data = json.loads(result)
        assert "error" not in data
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert "length()" in code

    @pytest.mark.asyncio
    async def test_distance_requires_actor_b(self, server, mock_ue):
        fn = _call(server, "ue_measure")
        result = await fn(mode="distance", actor_a="A")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extent_happy(self, server, mock_ue):
        fn = _call(server, "ue_measure")
        result = await fn(mode="extent", actor_a="Cabin")
        data = json.loads(result)
        assert "error" not in data
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert "get_actor_bounds" in code
        assert "footprint_area" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_mode(self, server, mock_ue):
        fn = _call(server, "ue_measure")
        result = await fn(mode="volume", actor_a="A")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()
