"""Async integration tests for ue_mcp/tools/mograph.py.

Exercises the full tool registration -> call -> mock response path
using FastMCP server instances and the mock_ue fixture.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.mograph import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestCreateClonerAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_create_cloner")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_layout(self, server, mock_ue):
        fn = _call(server, "ue_create_cloner")
        await fn(layout="Circle", label="MyCloner")
        code = mock_ue.execute_python.call_args[0][0]
        assert "MyCloner" in code
        assert "ClonerActor" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_layout(self, server, mock_ue):
        fn = _call(server, "ue_create_cloner")
        result = await fn(layout="InvalidLayout")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_mesh_path(self, server, mock_ue):
        fn = _call(server, "ue_create_cloner")
        result = await fn(mesh_path="bad path")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_label(self, server, mock_ue):
        fn = _call(server, "ue_create_cloner")
        result = await fn(label='bad"; import os')
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestCreateNiagaraSystemAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_create_niagara_system")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_system_asset(self, server, mock_ue):
        fn = _call(server, "ue_create_niagara_system")
        await fn(system_asset="/Game/FX/NS_Sparks", label="Sparks01")
        code = mock_ue.execute_python.call_args[0][0]
        assert "/Game/FX/NS_Sparks" in code
        assert "Sparks01" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_system_asset(self, server, mock_ue):
        fn = _call(server, "ue_create_niagara_system")
        result = await fn(system_asset="bad path")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestCreatePcgGraphAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_create_pcg_graph")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_label(self, server, mock_ue):
        fn = _call(server, "ue_create_pcg_graph")
        await fn(label="MyPCG", extent_x=2000.0)
        code = mock_ue.execute_python.call_args[0][0]
        assert "MyPCG" in code
        assert "PCGVolume" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_label(self, server, mock_ue):
        fn = _call(server, "ue_create_pcg_graph")
        result = await fn(label='bad"; drop')
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()
