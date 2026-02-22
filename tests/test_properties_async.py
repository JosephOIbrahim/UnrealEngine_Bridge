"""Async integration tests for ue_mcp/tools/properties.py.

Exercises the full tool registration -> call -> mock response path
using FastMCP server instances and the mock_ue fixture.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.properties import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestGetPropertyAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_get_property")
        result = await fn(
            object_path="/Game/Maps/Main.Main:PersistentLevel.Cube_1",
            property_name="RelativeLocation",
        )
        data = json.loads(result)
        assert "error" not in data
        mock_ue.get_property.assert_awaited_once_with(
            "/Game/Maps/Main.Main:PersistentLevel.Cube_1",
            "RelativeLocation",
        )

    @pytest.mark.asyncio
    async def test_rejects_invalid_object_path(self, server, mock_ue):
        fn = _call(server, "ue_get_property")
        result = await fn(object_path="bad path!!!", property_name="RelativeLocation")
        data = json.loads(result)
        assert "error" in data
        mock_ue.get_property.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_property_name(self, server, mock_ue):
        fn = _call(server, "ue_get_property")
        result = await fn(
            object_path="/Game/Maps/Main.Main:PersistentLevel.Cube_1",
            property_name="bad;prop",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.get_property.assert_not_awaited()


class TestSetPropertyAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_set_property")
        result = await fn(
            object_path="/Game/Maps/Main.Main:PersistentLevel.Cube_1",
            property_name="RelativeLocation",
            value='{"X": 100, "Y": 0, "Z": 50}',
        )
        data = json.loads(result)
        assert data.get("success") is True
        mock_ue.set_property.assert_awaited_once_with(
            "/Game/Maps/Main.Main:PersistentLevel.Cube_1",
            "RelativeLocation",
            {"X": 100, "Y": 0, "Z": 50},
        )

    @pytest.mark.asyncio
    async def test_rejects_invalid_json_value(self, server, mock_ue):
        fn = _call(server, "ue_set_property")
        result = await fn(
            object_path="/Game/Maps/Main.Main:PersistentLevel.Cube_1",
            property_name="RelativeLocation",
            value="not valid json {",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.set_property.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_object_path(self, server, mock_ue):
        fn = _call(server, "ue_set_property")
        result = await fn(object_path="bad!", property_name="Prop", value="100")
        data = json.loads(result)
        assert "error" in data
        mock_ue.set_property.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_empty_property_name(self, server, mock_ue):
        fn = _call(server, "ue_set_property")
        result = await fn(
            object_path="/Game/Maps/Main.Main:PersistentLevel.Cube_1",
            property_name="",
            value="100",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.set_property.assert_not_awaited()
