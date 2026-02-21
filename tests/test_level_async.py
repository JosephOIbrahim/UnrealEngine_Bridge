"""Async integration tests for ue_mcp/tools/level.py.

Exercises the full tool registration -> call -> mock response path
using FastMCP server instances and the mock_ue fixture.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.level import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestSaveLevelAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_save_level")
        result = await fn()
        data = json.loads(result)
        assert data.get("success") is True
        mock_ue.save_level.assert_awaited_once()


class TestGetLevelInfoAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_get_level_info")
        result = await fn()
        data = json.loads(result)
        assert data["name"] == "TestLevel"
        assert data["actor_count"] == 0
        mock_ue.get_level_info.assert_awaited_once()


class TestLoadLevelAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_load_level")
        result = await fn(level_path="/Game/Maps/TestLevel")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_level_path(self, server, mock_ue):
        fn = _call(server, "ue_load_level")
        await fn(level_path="/Game/Maps/MyLevel")
        code = mock_ue.execute_python.call_args[0][0]
        assert "/Game/Maps/MyLevel" in code
        assert "load_level" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_load_level")
        result = await fn(level_path="../etc/passwd")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestGetWorldInfoAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_get_world_info")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_world_query(self, server, mock_ue):
        fn = _call(server, "ue_get_world_info")
        await fn()
        code = mock_ue.execute_python.call_args[0][0]
        assert "get_editor_world" in code
        assert "streaming_levels" in code
