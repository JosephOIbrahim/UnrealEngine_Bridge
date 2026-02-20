"""Property access tools for UE5 MCP server."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("ue5-mcp.tools.properties")

from ._validation import sanitize_object_path, sanitize_property_name, make_error


def register(server, ue):
    @server.tool(
        name="ue_get_property",
        description="Read a property value from any UObject in the editor by object path and property name.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_property(object_path: str, property_name: str) -> str:
        """Get a property. object_path is the full path (e.g. /Game/Maps/MainLevel.MainLevel:PersistentLevel.Cube_1)."""
        if err := sanitize_object_path(object_path):
            return make_error(err)
        if err := sanitize_property_name(property_name):
            return make_error(err)

        result = await ue.get_property(object_path, property_name)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_property",
        description="Set a property value on any UObject in the editor.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_property(object_path: str, property_name: str, value: str) -> str:
        """Set a property. value is a JSON string that will be parsed (e.g. '{"X": 100, "Y": 0, "Z": 50}' for vectors)."""
        if err := sanitize_object_path(object_path):
            return make_error(err)
        if err := sanitize_property_name(property_name):
            return make_error(err)
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            return make_error(f"Invalid JSON value: {e}")

        result = await ue.set_property(object_path, property_name, parsed)
        return json.dumps(result, indent=2)
