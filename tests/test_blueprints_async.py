"""Async integration tests for ue_mcp/tools/blueprints.py.

Exercises the full tool registration -> call -> mock response path
using FastMCP server instances and the mock_ue fixture.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.blueprints import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestCreateBlueprintAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_create_blueprint")
        result = await fn(name="BP_Test")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_name_and_class(self, server, mock_ue):
        fn = _call(server, "ue_create_blueprint")
        await fn(name="BP_Enemy", parent_class="Character")
        code = mock_ue.execute_python.call_args[0][0]
        assert "BP_Enemy" in code
        assert "Character" in code

    @pytest.mark.asyncio
    async def test_rejects_empty_name(self, server, mock_ue):
        fn = _call(server, "ue_create_blueprint")
        result = await fn(name="")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_folder(self, server, mock_ue):
        fn = _call(server, "ue_create_blueprint")
        result = await fn(name="BP_Test", folder="../etc")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_parent_class(self, server, mock_ue):
        fn = _call(server, "ue_create_blueprint")
        result = await fn(name="BP_Test", parent_class="1Bad;Class")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestAddComponentAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_add_component")
        result = await fn(actor_label="MyCube", component_class="PointLightComponent")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_class(self, server, mock_ue):
        fn = _call(server, "ue_add_component")
        await fn(actor_label="MyCube", component_class="SpotLightComponent", component_name="MySpot")
        code = mock_ue.execute_python.call_args[0][0]
        assert "SpotLightComponent" in code
        assert "MySpot" in code

    @pytest.mark.asyncio
    async def test_rejects_empty_label(self, server, mock_ue):
        fn = _call(server, "ue_add_component")
        result = await fn(actor_label="", component_class="PointLightComponent")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_component_class(self, server, mock_ue):
        fn = _call(server, "ue_add_component")
        result = await fn(actor_label="MyCube", component_class="1Bad;Class")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestSetComponentPropertyAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_set_component_property")
        result = await fn(
            actor_label="MyCube",
            component_class="StaticMeshComponent",
            property_name="CastShadow",
            value="true",
        )
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_invalid_property_name(self, server, mock_ue):
        fn = _call(server, "ue_set_component_property")
        result = await fn(
            actor_label="MyCube",
            component_class="StaticMeshComponent",
            property_name="bad;prop",
            value="true",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_json_value(self, server, mock_ue):
        fn = _call(server, "ue_set_component_property")
        result = await fn(
            actor_label="MyCube",
            component_class="StaticMeshComponent",
            property_name="CastShadow",
            value="not valid json {",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestSetBlueprintDefaultsAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_set_blueprint_defaults")
        result = await fn(
            blueprint_path="/Game/Blueprints/BP_Test",
            properties='{"MaxHealth": 100}',
        )
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_path_and_props(self, server, mock_ue):
        fn = _call(server, "ue_set_blueprint_defaults")
        await fn(
            blueprint_path="/Game/Blueprints/BP_Enemy",
            properties='{"Speed": 600.0}',
        )
        code = mock_ue.execute_python.call_args[0][0]
        assert "/Game/Blueprints/BP_Enemy" in code
        assert "Speed" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_set_blueprint_defaults")
        result = await fn(blueprint_path="../etc", properties='{"MaxHealth": 100}')
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_non_object_properties(self, server, mock_ue):
        fn = _call(server, "ue_set_blueprint_defaults")
        result = await fn(blueprint_path="/Game/Blueprints/BP_Test", properties="[1, 2, 3]")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_json(self, server, mock_ue):
        fn = _call(server, "ue_set_blueprint_defaults")
        result = await fn(blueprint_path="/Game/Blueprints/BP_Test", properties="not json")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_property_key(self, server, mock_ue):
        fn = _call(server, "ue_set_blueprint_defaults")
        result = await fn(
            blueprint_path="/Game/Blueprints/BP_Test",
            properties='{"bad;key": 100}',
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestCompileBlueprintAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_compile_blueprint")
        result = await fn(blueprint_path="/Game/Blueprints/BP_Test")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_path(self, server, mock_ue):
        fn = _call(server, "ue_compile_blueprint")
        await fn(blueprint_path="/Game/Blueprints/BP_Enemy")
        code = mock_ue.execute_python.call_args[0][0]
        assert "/Game/Blueprints/BP_Enemy" in code
        assert "compile_blueprint" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_compile_blueprint")
        result = await fn(blueprint_path="bad path")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestGetActorComponentsAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_get_actor_components")
        result = await fn(actor_label="MyCube")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_empty_label(self, server, mock_ue):
        fn = _call(server, "ue_get_actor_components")
        result = await fn(actor_label="")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestSpawnBlueprintAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_spawn_blueprint")
        result = await fn(blueprint_path="/Game/Blueprints/BP_Test")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_path_and_position(self, server, mock_ue):
        fn = _call(server, "ue_spawn_blueprint")
        await fn(blueprint_path="/Game/Blueprints/BP_Enemy", x=100.0, y=200.0, z=300.0, label="Enemy01")
        code = mock_ue.execute_python.call_args[0][0]
        assert "/Game/Blueprints/BP_Enemy" in code
        assert "100.0" in code
        assert "Enemy01" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_spawn_blueprint")
        result = await fn(blueprint_path="bad path")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_label(self, server, mock_ue):
        fn = _call(server, "ue_spawn_blueprint")
        result = await fn(blueprint_path="/Game/Blueprints/BP_Test", label='bad"; import os')
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()
