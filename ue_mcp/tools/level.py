"""Level management tools for UE5 MCP server."""

from __future__ import annotations

import json
import logging

from ._validation import sanitize_content_path, escape_for_fstring, make_error

logger = logging.getLogger("ue5-mcp.tools.level")


def register(server, ue):
    @server.tool(
        name="ue_save_level",
        description="Save the current level in the UE5 editor.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def save_level() -> str:
        """Save the current level."""
        result = await ue.save_level()
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_level_info",
        description="Get information about the current level (name, actor count).",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_level_info() -> str:
        """Get level name and actor count."""
        result = await ue.get_level_info()
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_load_level",
        description="Load a level by its content path. This will unload the current level.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
        },
    )
    async def load_level(level_path: str) -> str:
        """Load a level. level_path is a content path like /Game/Maps/MyLevel."""
        if err := sanitize_content_path(level_path, "level_path"):
            return make_error(err)

        safe_path = escape_for_fstring(level_path)
        code = f"""
import unreal, json

try:
    success = unreal.EditorLevelLibrary.load_level("{safe_path}")
    print("RESULT:" + json.dumps({{"loaded": True, "level": "{safe_path}"}}))
except Exception as e:
    print("RESULT:" + json.dumps({{"error": str(e)}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_world_info",
        description="Get detailed world information: streaming levels, world settings, game mode.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_world_info() -> str:
        """Get comprehensive world/level information."""
        code = """
import unreal, json

world = unreal.EditorLevelLibrary.get_editor_world()
info = {}

if world:
    info["world_name"] = world.get_name()
    info["world_path"] = world.get_path_name()

    # Streaming levels
    try:
        streaming = world.get_streaming_levels() if hasattr(world, 'get_streaming_levels') else []
        info["streaming_levels"] = [sl.get_world_asset_package_name() for sl in streaming] if streaming else []
    except Exception:
        info["streaming_levels"] = []

    # World settings
    try:
        ws = world.get_world_settings() if hasattr(world, 'get_world_settings') else None
        if ws:
            info["world_settings"] = {
                "class": ws.get_class().get_name(),
            }
            try:
                gm = ws.get_editor_property("DefaultGameMode")
                info["world_settings"]["game_mode"] = gm.get_name() if gm else None
            except Exception:
                pass
    except Exception:
        pass

    # Actor count
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    info["actor_count"] = len(actors)

    print("RESULT:" + json.dumps(info))
else:
    print("RESULT:" + json.dumps({"error": "No editor world available"}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
