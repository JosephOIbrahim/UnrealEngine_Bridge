"""Actor manipulation tools for UE5 MCP server."""

from __future__ import annotations

import json
import logging

from ._validation import sanitize_class_name, sanitize_label, sanitize_object_path, make_error

logger = logging.getLogger("ue5-mcp.tools.actors")


def register(server, ue):
    @server.tool(
        name="ue_spawn_actor",
        description="Spawn an actor in the UE5 editor by class name at a given location.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def spawn_actor(
        class_name: str = "StaticMeshActor",
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rx: float = 0.0,
        ry: float = 0.0,
        rz: float = 0.0,
        label: str | None = None,
    ) -> str:
        """Spawn an actor. class_name can be a UE class like StaticMeshActor, PointLight, CameraActor, etc."""
        if err := sanitize_class_name(class_name):
            return make_error(err)
        if label is not None:
            if err := sanitize_label(label):
                return make_error(err)

        result = await ue.spawn_actor(
            class_name,
            location=(x, y, z),
            rotation=(rx, ry, rz),
            label=label,
        )
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_delete_actor",
        description="Delete an actor from the level by its object path.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
        },
    )
    async def delete_actor(actor_path: str) -> str:
        """Delete an actor by its full object path (e.g. /Game/Maps/MainLevel.MainLevel:PersistentLevel.Cube_1)."""
        if err := sanitize_object_path(actor_path, "actor_path"):
            return make_error(err)

        result = await ue.delete_actor(actor_path)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_list_actors",
        description="List all actors in the current level, optionally filtered by class name.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def list_actors(class_filter: str | None = None) -> str:
        """List actors. Returns name, class, path, and location for each actor."""
        if class_filter is not None:
            if err := sanitize_class_name(class_filter, "class_filter"):
                return make_error(err)

        result = await ue.list_actors(class_filter=class_filter)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_transform",
        description="Set the transform (location/rotation/scale) of an actor.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_transform(
        actor_path: str,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        rx: float | None = None,
        ry: float | None = None,
        rz: float | None = None,
        sx: float | None = None,
        sy: float | None = None,
        sz: float | None = None,
    ) -> str:
        """Set location (x,y,z), rotation (rx,ry,rz), and/or scale (sx,sy,sz) on an actor."""
        if err := sanitize_object_path(actor_path, "actor_path"):
            return make_error(err)

        location = (x, y, z) if x is not None and y is not None and z is not None else None
        rotation = (rx, ry, rz) if rx is not None and ry is not None and rz is not None else None
        scale = (sx, sy, sz) if sx is not None and sy is not None and sz is not None else None
        result = await ue.set_actor_transform(
            actor_path, location=location, rotation=rotation, scale=scale
        )
        return json.dumps(result, indent=2)
