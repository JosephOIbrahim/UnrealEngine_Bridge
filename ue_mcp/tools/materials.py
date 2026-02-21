"""Material editing tools for UE5 MCP server.

Create material instances, set parameters, and assign materials to actors.
All route through ue_execute_python using MaterialEditingLibrary and
MaterialInstanceConstantFactoryNew.
"""

from __future__ import annotations

import json
import logging

from ._validation import (
    sanitize_label, sanitize_content_path, sanitize_property_name,
    escape_for_fstring, make_error,
)

logger = logging.getLogger("ue5-mcp.tools.materials")


def register(server, ue):
    @server.tool(
        name="ue_create_material_instance",
        description=(
            "Create a MaterialInstanceConstant from a parent material. "
            "The instance inherits all parameters from the parent and can override them."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def create_material_instance(
        name: str,
        parent_material: str,
        folder: str = "/Game/Materials",
    ) -> str:
        """Create a material instance. parent_material is the content path to the parent material."""
        if err := sanitize_label(name, "name"):
            return make_error(err)
        if err := sanitize_content_path(parent_material, "parent_material"):
            return make_error(err)
        if err := sanitize_content_path(folder, "folder"):
            return make_error(err)

        safe_name = escape_for_fstring(name)
        safe_parent = escape_for_fstring(parent_material)
        safe_folder = escape_for_fstring(folder)
        code = f"""
import unreal, json

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
factory = unreal.MaterialInstanceConstantFactoryNew()

parent = unreal.EditorAssetLibrary.load_asset("{safe_parent}")
if parent is None:
    print("RESULT:" + json.dumps({{"error": "Parent material not found: {safe_parent}"}}))
else:
    factory.set_editor_property("InitialParent", parent)
    mi = asset_tools.create_asset("{safe_name}", "{safe_folder}", unreal.MaterialInstanceConstant, factory)
    if mi:
        unreal.EditorAssetLibrary.save_asset("{safe_folder}/{safe_name}")
        print("RESULT:" + json.dumps({{
            "created": "{safe_folder}/{safe_name}",
            "parent": "{safe_parent}",
        }}))
    else:
        print("RESULT:" + json.dumps({{"error": "Failed to create material instance"}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_material_parameter",
        description=(
            "Set a parameter on a MaterialInstanceConstant. "
            "param_type can be 'scalar', 'vector', or 'texture'. "
            "For scalar: value is a number. "
            "For vector: value is 'r,g,b,a' (0-1 range). "
            "For texture: value is a content path to a texture asset."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_material_parameter(
        material_path: str,
        param_name: str,
        value: str,
        param_type: str = "scalar",
    ) -> str:
        """Set a parameter on a material instance."""
        if err := sanitize_content_path(material_path, "material_path"):
            return make_error(err)
        if err := sanitize_label(param_name, "param_name"):
            return make_error(err)
        valid_types = {"scalar", "vector", "texture"}
        if param_type not in valid_types:
            return make_error(f"param_type must be one of: {', '.join(sorted(valid_types))}")
        if err := sanitize_label(value, "value"):
            return make_error(err)

        safe_path = escape_for_fstring(material_path)
        safe_param = escape_for_fstring(param_name)
        safe_value = escape_for_fstring(value)

        if param_type == "scalar":
            set_line = f'unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "{safe_param}", float("{safe_value}"))'
        elif param_type == "vector":
            set_line = f"""
parts = "{safe_value}".split(",")
color = unreal.LinearColor(float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]) if len(parts) > 3 else 1.0)
unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, "{safe_param}", color)
""".strip()
        else:  # texture
            set_line = f"""
tex = unreal.EditorAssetLibrary.load_asset("{safe_value}")
if tex:
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "{safe_param}", tex)
else:
    print("RESULT:" + json.dumps({{"error": "Texture not found: {safe_value}"}}))
    raise SystemExit
""".strip()

        code = f"""
import unreal, json

mi = unreal.EditorAssetLibrary.load_asset("{safe_path}")
if mi is None:
    print("RESULT:" + json.dumps({{"error": "Material not found: {safe_path}"}}))
else:
    {set_line}
    unreal.EditorAssetLibrary.save_asset("{safe_path}")
    print("RESULT:" + json.dumps({{"set": True, "material": "{safe_path}", "parameter": "{safe_param}", "type": "{param_type}"}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_material_parameters",
        description="List all exposed parameters on a material or material instance with their current values.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_material_parameters(material_path: str) -> str:
        """Get all parameters from a material or material instance."""
        if err := sanitize_content_path(material_path, "material_path"):
            return make_error(err)

        safe_path = escape_for_fstring(material_path)
        code = f"""
import unreal, json

asset = unreal.EditorAssetLibrary.load_asset("{safe_path}")
if asset is None:
    print("RESULT:" + json.dumps({{"error": "Material not found: {safe_path}"}}))
else:
    params = {{}}

    # Scalar parameters
    if hasattr(unreal, 'MaterialEditingLibrary'):
        lib = unreal.MaterialEditingLibrary

        try:
            scalar_infos = lib.get_scalar_parameter_names(asset) if hasattr(lib, 'get_scalar_parameter_names') else []
            for name in scalar_infos:
                try:
                    val = lib.get_material_instance_scalar_parameter_value(asset, name)
                    params[name] = {{"type": "scalar", "value": val}}
                except Exception:
                    params[name] = {{"type": "scalar", "value": None}}
        except Exception:
            pass

        try:
            vector_infos = lib.get_vector_parameter_names(asset) if hasattr(lib, 'get_vector_parameter_names') else []
            for name in vector_infos:
                try:
                    val = lib.get_material_instance_vector_parameter_value(asset, name)
                    params[name] = {{"type": "vector", "value": {{"r": val.r, "g": val.g, "b": val.b, "a": val.a}}}}
                except Exception:
                    params[name] = {{"type": "vector", "value": None}}
        except Exception:
            pass

        try:
            texture_infos = lib.get_texture_parameter_names(asset) if hasattr(lib, 'get_texture_parameter_names') else []
            for name in texture_infos:
                try:
                    val = lib.get_material_instance_texture_parameter_value(asset, name)
                    params[name] = {{"type": "texture", "value": val.get_path_name() if val else None}}
                except Exception:
                    params[name] = {{"type": "texture", "value": None}}
        except Exception:
            pass

    print("RESULT:" + json.dumps({{"material": "{safe_path}", "parameters": params}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_assign_material",
        description="Assign a material to a mesh component on an actor at a given slot index.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def assign_material(
        actor_label: str,
        material_path: str,
        slot_index: int = 0,
    ) -> str:
        """Apply a material to an actor's mesh component at the specified slot."""
        if err := sanitize_label(actor_label, "actor_label"):
            return make_error(err)
        if err := sanitize_content_path(material_path, "material_path"):
            return make_error(err)
        if slot_index < 0 or slot_index > 63:
            return make_error("slot_index must be between 0 and 63")

        safe_label = escape_for_fstring(actor_label)
        safe_mat = escape_for_fstring(material_path)
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
    print("RESULT:" + json.dumps({{"error": "Actor not found: {safe_label}"}}))
else:
    mat = unreal.EditorAssetLibrary.load_asset("{safe_mat}")
    if mat is None:
        print("RESULT:" + json.dumps({{"error": "Material not found: {safe_mat}"}}))
    else:
        mesh_comp = actor.get_component_by_class(unreal.StaticMeshComponent)
        if mesh_comp is None:
            mesh_comp = actor.get_component_by_class(unreal.SkeletalMeshComponent)
        if mesh_comp is None:
            print("RESULT:" + json.dumps({{"error": "No mesh component found on actor"}}))
        else:
            mesh_comp.set_material({slot_index}, mat)
            print("RESULT:" + json.dumps({{
                "assigned": True,
                "actor": "{safe_label}",
                "material": "{safe_mat}",
                "slot": {slot_index},
            }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
