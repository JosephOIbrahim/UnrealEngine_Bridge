"""Asset management tools for UE5 MCP server."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("ue5-mcp.tools.assets")

from ._validation import (
    sanitize_label, sanitize_class_name, sanitize_content_path,
    escape_for_fstring, make_error,
)


def register(server, ue):
    @server.tool(
        name="ue_find_assets",
        description="Search the Content Browser for assets by name pattern. Returns up to 50 matches.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def find_assets(search_pattern: str, class_filter: str | None = None) -> str:
        """Search for assets. search_pattern matches against asset names (case-insensitive)."""
        if not search_pattern or len(search_pattern) > 256:
            return make_error("search_pattern must be 1-256 characters")
        if class_filter is not None:
            if err := sanitize_class_name(class_filter, "class_filter"):
                return make_error(err)

        result = await ue.find_assets(search_pattern, class_filter=class_filter)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_create_material",
        description="Create a basic material with base color, roughness, and metallic parameters.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def create_material(
        name: str,
        base_color_r: float = 0.8,
        base_color_g: float = 0.8,
        base_color_b: float = 0.8,
        roughness: float = 0.5,
        metallic: float = 0.0,
    ) -> str:
        """Create a material instance at /Game/Materials/{name}."""
        if err := sanitize_label(name, "name"):
            return make_error(err)

        safe_name = escape_for_fstring(name)
        code = f"""
import unreal, json

# Create material asset
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
factory = unreal.MaterialFactoryNew()
material = asset_tools.create_asset("{safe_name}", "/Game/Materials", unreal.Material, factory)

if material:
    mel = unreal.MaterialEditingLibrary

    # BaseColor constant expression
    base_color_node = mel.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -300, 0)
    if base_color_node:
        base_color_node.set_editor_property("Constant", unreal.LinearColor({base_color_r}, {base_color_g}, {base_color_b}, 1.0))
        mel.connect_material_property(base_color_node, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # Roughness constant expression
    roughness_node = mel.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 200)
    if roughness_node:
        roughness_node.set_editor_property("R", {roughness})
        mel.connect_material_property(roughness_node, "", unreal.MaterialProperty.MP_ROUGHNESS)

    # Metallic constant expression
    metallic_node = mel.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 400)
    if metallic_node:
        metallic_node.set_editor_property("R", {metallic})
        mel.connect_material_property(metallic_node, "", unreal.MaterialProperty.MP_METALLIC)

    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset("/Game/Materials/{safe_name}")
    print("RESULT:" + json.dumps({{"created": "/Game/Materials/{safe_name}", "base_color": [{base_color_r}, {base_color_g}, {base_color_b}], "roughness": {roughness}, "metallic": {metallic}}}))
else:
    print("RESULT:" + json.dumps({{"error": "Failed to create material"}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_delete_asset",
        description="Delete an asset from the Content Browser by its content path. This is destructive and cannot be undone.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
        },
    )
    async def delete_asset(asset_path: str) -> str:
        """Delete an asset. asset_path is a content path like /Game/Materials/MyMaterial."""
        if err := sanitize_content_path(asset_path, "asset_path"):
            return make_error(err)

        safe_path = escape_for_fstring(asset_path)
        code = f"""
import unreal, json

if not unreal.EditorAssetLibrary.does_asset_exist("{safe_path}"):
    print("RESULT:" + json.dumps({{"error": "Asset not found: {safe_path}"}}))
else:
    success = unreal.EditorAssetLibrary.delete_asset("{safe_path}")
    print("RESULT:" + json.dumps({{"deleted": success, "asset": "{safe_path}"}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
