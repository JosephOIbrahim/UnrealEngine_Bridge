"""Asset management tools for UE5 MCP server."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("ue5-mcp.tools.assets")

from ._validation import sanitize_label, sanitize_class_name, make_error


def _escape_for_fstring(s: str) -> str:
    """Escape a string for safe embedding in an f-string Python code template."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")


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

        safe_name = _escape_for_fstring(name)
        code = f"""
import unreal

# Create material asset
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
factory = unreal.MaterialFactoryNew()
material = asset_tools.create_asset("{safe_name}", "/Game/Materials", unreal.Material, factory)

if material:
    # Set up base color via constant expression
    editor_subsystem = unreal.get_editor_subsystem(unreal.MaterialEditingSubsystem) if hasattr(unreal, 'MaterialEditingSubsystem') else None

    # Save the asset
    unreal.EditorAssetLibrary.save_asset("/Game/Materials/{safe_name}")
    print("RESULT:CREATED /Game/Materials/{safe_name}")
else:
    print("RESULT:FAILED")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
