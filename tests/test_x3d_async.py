"""Async tests for ue_mcp/tools/x3d.py -- the ue_x3d_* MCP tools.

Mocked bridge; the exec-sim harness proves the generated read/apply scripts run
against the strict fake `unreal`. Live round-trip is proven by ue_preflight +
smoke_live against a real editor.
"""

import ast
import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.x3d import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _fn(server, name):
    return server._tool_manager._tools[name].fn


_ACTOR_ROW = {
    "guid": "/Game/Maps/M.M:PersistentLevel.Rock_1",
    "mesh": "/Game/Meshes/SM_Rock",
    "material": "/Game/Mat/M_Granite",
    "t": [420.0, 0.0, 155.0],
    "r": [0.0, 0.0, 0.0, 1.0],
    "s": [1.0, 1.0, 1.0],
    "parent": None,
}

_APPLY_X3D = (
    '<X3D profile="Interchange" version="4.0"><Scene>'
    '<Transform DEF="/Game/Maps/M.M:PersistentLevel.A_1" translation="1.0 2.0 3.0" '
    'rotation="0.0 0.0 1.0 0.0" scale="1.0 1.0 1.0"/></Scene></X3D>'
)


class TestExport:
    @pytest.mark.asyncio
    async def test_serializes_scene(self, server, mock_ue):
        mock_ue.execute_python.return_value = {"result": [_ACTOR_ROW], "output": "", "error": None}
        data = json.loads(await _fn(server, "ue_x3d_export")(mesh_only=True))
        assert "error" not in data
        assert data["actor_count"] == 1
        assert 'DEF="/Game/Maps/M.M:PersistentLevel.Rock_1"' in data["x3d"]
        assert "/Game/Meshes/SM_Rock" in data["x3d"]
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_read_script_is_valid_python(self, server, mock_ue):
        mock_ue.execute_python.return_value = {"result": [], "output": "", "error": None}
        await _fn(server, "ue_x3d_export")()
        code = mock_ue.execute_python.call_args[0][0]
        ast.parse(code)  # generated UE Python must compile
        assert "get_all_level_actors" in code
        assert "get_actor_transform" in code

    @pytest.mark.asyncio
    async def test_mesh_only_filters_meshless(self, server, mock_ue):
        rows = [_ACTOR_ROW, {**_ACTOR_ROW, "guid": "Light_1", "mesh": ""}]
        mock_ue.execute_python.return_value = {"result": rows, "output": "", "error": None}
        data = json.loads(await _fn(server, "ue_x3d_export")(mesh_only=True))
        assert data["actor_count"] == 1

    @pytest.mark.asyncio
    async def test_reports_read_failure(self, server, mock_ue):
        mock_ue.execute_python.return_value = {"result": None, "output": "", "error": "boom"}
        data = json.loads(await _fn(server, "ue_x3d_export")())
        assert "error" in data


class TestValidate:
    @pytest.mark.asyncio
    async def test_accepts_good(self, server, mock_ue):
        x3d = '<X3D><Scene><Material DEF="m"/><Material USE="m"/></Scene></X3D>'
        data = json.loads(await _fn(server, "ue_x3d_validate")(x3d=x3d))
        assert data["ok"] is True
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_out_of_grammar(self, server, mock_ue):
        data = json.loads(await _fn(server, "ue_x3d_validate")(x3d="<X3D><Scene><Frobnicate/></Scene></X3D>"))
        assert data["ok"] is False
        assert data["errors"]


class TestApply:
    @pytest.mark.asyncio
    async def test_emits_set_transform(self, server, mock_ue):
        mock_ue.execute_python.return_value = {"result": {"applied": 1}, "output": "", "error": None}
        await _fn(server, "ue_x3d_apply")(x3d=_APPLY_X3D)
        mock_ue.execute_python.assert_awaited_once()
        code = mock_ue.execute_python.call_args[0][0]
        ast.parse(code)
        assert "set_actor_location" in code
        assert "RESULT:" in code  # the emitted ops are wrapped with a result line

    @pytest.mark.asyncio
    async def test_rejects_invalid_x3d_before_editor(self, server, mock_ue):
        data = json.loads(await _fn(server, "ue_x3d_apply")(x3d="<X3D><Scene><Frobnicate/></Scene></X3D>"))
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dangerous_guid_never_reaches_codegen(self, server, mock_ue):
        # a DEF carrying an injection attempt must be rejected, or at minimum not
        # appear verbatim in the generated Python.
        x3d = (
            '<X3D profile="Interchange" version="4.0"><Scene>'
            '<Transform DEF="a&quot;)&#10;import os#" translation="1.0 2.0 3.0" '
            'rotation="0.0 0.0 1.0 0.0" scale="1.0 1.0 1.0"/></Scene></X3D>'
        )
        result = await _fn(server, "ue_x3d_apply")(x3d=x3d)
        data = json.loads(result)
        if "error" not in data:
            code = mock_ue.execute_python.call_args[0][0]
            assert "import os" not in code


class TestPreview:
    @pytest.mark.asyncio
    async def test_embeds_x3d_no_editor(self, server, mock_ue):
        x3d = '<X3D><Scene><Transform DEF="A"/></Scene></X3D>'
        data = json.loads(await _fn(server, "ue_x3d_preview")(x3d=x3d))
        assert data["chars"] > 0
        assert "<x3d-canvas>" in data["html"]
        assert 'DEF="A"' in data["html"]
        mock_ue.execute_python.assert_not_awaited()
