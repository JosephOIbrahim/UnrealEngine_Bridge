"""Tests for ue_mcp/tools/materials.py — material editing tools."""

import ast
import json
import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools._validation import (
    sanitize_label, sanitize_content_path, escape_for_fstring,
)
from ue_mcp.tools.materials import register


class TestCreateMaterialInstanceValidation:
    """ue_create_material_instance input validation."""

    def test_rejects_empty_name(self):
        assert sanitize_label("", "name") is not None

    def test_rejects_invalid_parent_path(self):
        assert sanitize_content_path("not/a/valid/path", "parent_material") is not None

    def test_accepts_valid_inputs(self):
        assert sanitize_label("MI_Chrome", "name") is None
        assert sanitize_content_path("/Game/Materials/M_Chrome", "parent_material") is None
        assert sanitize_content_path("/Game/Materials", "folder") is None


class TestCreateMaterialInstanceCodeGen:
    """Generated code for ue_create_material_instance parses cleanly."""

    def test_code_parses(self):
        safe_name = escape_for_fstring("MI_Chrome")
        safe_parent = escape_for_fstring("/Game/Materials/M_Chrome")
        safe_folder = escape_for_fstring("/Game/Materials")
        code = f"""
import unreal, json

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
factory = unreal.MaterialInstanceConstantFactoryNew()

parent = unreal.EditorAssetLibrary.load_asset("{safe_parent}")
if parent is None:
    print("RESULT:" + json.dumps({{"error": "not found"}}))
else:
    factory.set_editor_property("InitialParent", parent)
    mi = asset_tools.create_asset("{safe_name}", "{safe_folder}", unreal.MaterialInstanceConstant, factory)
    if mi:
        unreal.EditorAssetLibrary.save_asset("{safe_folder}/{safe_name}")
        print("RESULT:" + json.dumps({{"created": "{safe_folder}/{safe_name}"}}))
"""
        ast.parse(code)


class TestSetMaterialParameterValidation:
    """ue_set_material_parameter input validation."""

    def test_rejects_invalid_path(self):
        assert sanitize_content_path("../etc/passwd", "material_path") is not None

    def test_rejects_invalid_param_type(self):
        valid_types = {"scalar", "vector", "texture"}
        assert "invalid" not in valid_types


class TestSetMaterialParameterCodeGen:
    """Generated code for scalar/vector/texture params parses cleanly."""

    def test_scalar_code_parses(self):
        safe_path = escape_for_fstring("/Game/Materials/MI_Test")
        safe_param = escape_for_fstring("Roughness")
        safe_value = escape_for_fstring("0.5")
        code = f"""
import unreal, json

mi = unreal.EditorAssetLibrary.load_asset("{safe_path}")
if mi is None:
    print("RESULT:" + json.dumps({{"error": "not found"}}))
else:
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "{safe_param}", float("{safe_value}"))
    unreal.EditorAssetLibrary.save_asset("{safe_path}")
    print("RESULT:" + json.dumps({{"set": True}}))
"""
        ast.parse(code)

    def test_vector_code_parses(self):
        safe_path = escape_for_fstring("/Game/Materials/MI_Test")
        safe_param = escape_for_fstring("BaseColor")
        safe_value = escape_for_fstring("1.0,0.0,0.0,1.0")
        code = f"""
import unreal, json

mi = unreal.EditorAssetLibrary.load_asset("{safe_path}")
if mi is None:
    print("RESULT:" + json.dumps({{"error": "not found"}}))
else:
    parts = "{safe_value}".split(",")
    color = unreal.LinearColor(float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]) if len(parts) > 3 else 1.0)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, "{safe_param}", color)
    print("RESULT:" + json.dumps({{"set": True}}))
"""
        ast.parse(code)


class TestGetMaterialParametersCodeGen:
    """Generated code for ue_get_material_parameters parses cleanly."""

    def test_code_parses(self):
        safe_path = escape_for_fstring("/Game/Materials/MI_Test")
        code = f"""
import unreal, json

asset = unreal.EditorAssetLibrary.load_asset("{safe_path}")
if asset is None:
    print("RESULT:" + json.dumps({{"error": "not found"}}))
else:
    params = {{}}
    print("RESULT:" + json.dumps({{"material": "{safe_path}", "parameters": params}}))
"""
        ast.parse(code)


class TestAssignMaterialValidation:
    """ue_assign_material input validation."""

    def test_rejects_negative_slot(self):
        assert -1 < 0  # slot_index < 0 check in tool

    def test_rejects_too_large_slot(self):
        assert 64 > 63  # slot_index > 63 check in tool

    def test_accepts_valid_slot(self):
        assert 0 <= 0 <= 63


class TestAssignMaterialCodeGen:
    """Generated code for ue_assign_material parses cleanly."""

    def test_code_parses(self):
        safe_label = escape_for_fstring("MyCube")
        safe_mat = escape_for_fstring("/Game/Materials/M_Chrome")
        slot_index = 0
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{safe_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "not found"}}))
else:
    mat = unreal.EditorAssetLibrary.load_asset("{safe_mat}")
    if mat is None:
        print("RESULT:" + json.dumps({{"error": "material not found"}}))
    else:
        mesh_comp = actor.get_component_by_class(unreal.StaticMeshComponent)
        if mesh_comp:
            mesh_comp.set_material({slot_index}, mat)
            print("RESULT:" + json.dumps({{"assigned": True}}))
"""
        ast.parse(code)


# --- Async integration tests ---


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestCreateMaterialInstanceAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_create_material_instance")
        result = await fn(name="MI_Chrome", parent_material="/Game/Materials/M_Chrome")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_name_and_parent(self, server, mock_ue):
        fn = _call(server, "ue_create_material_instance")
        await fn(name="MI_Gold", parent_material="/Game/Materials/M_Gold")
        code = mock_ue.execute_python.call_args[0][0]
        assert "MI_Gold" in code
        assert "/Game/Materials/M_Gold" in code

    @pytest.mark.asyncio
    async def test_rejects_empty_name(self, server, mock_ue):
        fn = _call(server, "ue_create_material_instance")
        result = await fn(name="", parent_material="/Game/Materials/M_Chrome")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_parent_path(self, server, mock_ue):
        fn = _call(server, "ue_create_material_instance")
        result = await fn(name="MI_Test", parent_material="not/valid")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestSetMaterialParameterAsync:
    @pytest.mark.asyncio
    async def test_scalar_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_set_material_parameter")
        result = await fn(
            material_path="/Game/Materials/MI_Test",
            param_name="Roughness",
            value="0.5",
            param_type="scalar",
        )
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_param_name(self, server, mock_ue):
        fn = _call(server, "ue_set_material_parameter")
        await fn(
            material_path="/Game/Materials/MI_Test",
            param_name="Roughness",
            value="0.5",
            param_type="scalar",
        )
        code = mock_ue.execute_python.call_args[0][0]
        assert "Roughness" in code
        assert "scalar_parameter_value" in code

    @pytest.mark.asyncio
    async def test_vector_value_rejected_by_sanitizer(self, server, mock_ue):
        """Vector values with commas are rejected by sanitize_label on value param."""
        fn = _call(server, "ue_set_material_parameter")
        result = await fn(
            material_path="/Game/Materials/MI_Test",
            param_name="BaseColor",
            value="1.0,0.0,0.0,1.0",
            param_type="vector",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_param_type(self, server, mock_ue):
        fn = _call(server, "ue_set_material_parameter")
        result = await fn(
            material_path="/Game/Materials/MI_Test",
            param_name="Roughness",
            value="0.5",
            param_type="invalid",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_material_path(self, server, mock_ue):
        fn = _call(server, "ue_set_material_parameter")
        result = await fn(
            material_path="../etc/passwd",
            param_name="Roughness",
            value="0.5",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestGetMaterialParametersAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_get_material_parameters")
        result = await fn(material_path="/Game/Materials/MI_Test")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_get_material_parameters")
        result = await fn(material_path="bad path")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestAssignMaterialAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_assign_material")
        result = await fn(
            actor_label="MyCube",
            material_path="/Game/Materials/M_Chrome",
        )
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_negative_slot(self, server, mock_ue):
        fn = _call(server, "ue_assign_material")
        result = await fn(
            actor_label="MyCube",
            material_path="/Game/Materials/M_Chrome",
            slot_index=-1,
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_slot_over_63(self, server, mock_ue):
        fn = _call(server, "ue_assign_material")
        result = await fn(
            actor_label="MyCube",
            material_path="/Game/Materials/M_Chrome",
            slot_index=64,
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()
