"""Level management tools for UE5 MCP server."""

from __future__ import annotations

import json
import logging

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
