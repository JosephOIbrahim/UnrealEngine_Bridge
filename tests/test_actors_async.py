"""Async integration tests for ue_mcp/tools/actors.py.

Exercises the full tool registration -> call -> mock response path
using FastMCP server instances and the mock_ue fixture.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.actors import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestSpawnActorAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_spawn_actor")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        mock_ue.spawn_actor.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_label_and_position(self, server, mock_ue):
        fn = _call(server, "ue_spawn_actor")
        result = await fn(class_name="PointLight", x=100.0, y=200.0, z=300.0, label="MyLight")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.spawn_actor.assert_awaited_once_with(
            "PointLight",
            location=(100.0, 200.0, 300.0),
            rotation=(0.0, 0.0, 0.0),
            label="MyLight",
        )

    @pytest.mark.asyncio
    async def test_rejects_invalid_class(self, server, mock_ue):
        fn = _call(server, "ue_spawn_actor")
        result = await fn(class_name="1Bad;Class")
        data = json.loads(result)
        assert "error" in data
        mock_ue.spawn_actor.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_label(self, server, mock_ue):
        fn = _call(server, "ue_spawn_actor")
        result = await fn(label='test"; import os')
        data = json.loads(result)
        assert "error" in data
        mock_ue.spawn_actor.assert_not_awaited()


class TestDeleteActorAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_delete_actor")
        result = await fn(actor_path="/Game/Maps/Level.Level:PersistentLevel.Cube_1")
        data = json.loads(result)
        assert data.get("success") is True
        mock_ue.delete_actor.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_delete_actor")
        result = await fn(actor_path="../etc/passwd")
        data = json.loads(result)
        assert "error" in data
        mock_ue.delete_actor.assert_not_awaited()


class TestListActorsAsync:
    @pytest.mark.asyncio
    async def test_happy_path_no_filter(self, server, mock_ue):
        fn = _call(server, "ue_list_actors")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        mock_ue.list_actors.assert_awaited_once_with(class_filter=None)

    @pytest.mark.asyncio
    async def test_with_class_filter(self, server, mock_ue):
        fn = _call(server, "ue_list_actors")
        result = await fn(class_filter="PointLight")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.list_actors.assert_awaited_once_with(class_filter="PointLight")

    @pytest.mark.asyncio
    async def test_rejects_invalid_class_filter(self, server, mock_ue):
        fn = _call(server, "ue_list_actors")
        result = await fn(class_filter="1Bad;Class")
        data = json.loads(result)
        assert "error" in data
        mock_ue.list_actors.assert_not_awaited()


class TestSetTransformAsync:
    @pytest.mark.asyncio
    async def test_happy_path_location(self, server, mock_ue):
        fn = _call(server, "ue_set_transform")
        result = await fn(actor_path="/Game/Level.Level:PersistentLevel.Cube", x=1.0, y=2.0, z=3.0)
        data = json.loads(result)
        assert data.get("success") is True
        mock_ue.set_actor_transform.assert_awaited_once_with(
            "/Game/Level.Level:PersistentLevel.Cube",
            location=(1.0, 2.0, 3.0),
            rotation=None,
            scale=None,
        )

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_set_transform")
        result = await fn(actor_path="bad path!!!")
        data = json.loads(result)
        assert "error" in data
        mock_ue.set_actor_transform.assert_not_awaited()


class TestDuplicateActorAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_duplicate_actor")
        result = await fn(actor_label="MyCube")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_label(self, server, mock_ue):
        fn = _call(server, "ue_duplicate_actor")
        await fn(actor_label="TestActor")
        code = mock_ue.execute_python.call_args[0][0]
        assert "TestActor" in code
        assert "duplicate_selected_actors" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_label(self, server, mock_ue):
        fn = _call(server, "ue_duplicate_actor")
        result = await fn(actor_label='bad"; import os')
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestGetActorBoundsAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_get_actor_bounds")
        result = await fn(actor_label="MyCube")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_label(self, server, mock_ue):
        fn = _call(server, "ue_get_actor_bounds")
        await fn(actor_label="TestCube")
        code = mock_ue.execute_python.call_args[0][0]
        assert "TestCube" in code
        assert "get_actor_bounds" in code

    @pytest.mark.asyncio
    async def test_rejects_empty_label(self, server, mock_ue):
        fn = _call(server, "ue_get_actor_bounds")
        result = await fn(actor_label="")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()
