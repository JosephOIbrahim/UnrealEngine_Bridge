"""Actor manipulation tools for UE5 MCP server."""

from __future__ import annotations

import json
import logging

from ._validation import (
    sanitize_class_name, sanitize_label, sanitize_object_path,
    escape_for_fstring, make_error,
)

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

    @server.tool(
        name="ue_duplicate_actor",
        description="Duplicate an actor with an optional position offset.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def duplicate_actor(
        actor_label: str,
        offset_x: float = 200.0,
        offset_y: float = 0.0,
        offset_z: float = 0.0,
    ) -> str:
        """Duplicate an actor by label and offset the copy."""
        if err := sanitize_label(actor_label, "actor_label"):
            return make_error(err)

        safe_label = escape_for_fstring(actor_label)
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
    # Select and duplicate
    subsystem.set_selected_level_actors([actor])
    duplicated = subsystem.duplicate_selected_actors()
    if duplicated:
        new_actor = duplicated[0]
        loc = new_actor.get_actor_location()
        new_actor.set_actor_location(
            unreal.Vector(loc.x + {offset_x}, loc.y + {offset_y}, loc.z + {offset_z}),
            False, False
        )
        print("RESULT:" + json.dumps({{
            "duplicated": new_actor.get_actor_label(),
            "path": new_actor.get_path_name(),
            "class": new_actor.get_class().get_name(),
            "location": {{
                "x": loc.x + {offset_x},
                "y": loc.y + {offset_y},
                "z": loc.z + {offset_z},
            }},
        }}))
    else:
        print("RESULT:" + json.dumps({{"error": "Duplication failed"}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_actor_bounds",
        description="Get the axis-aligned bounding box of an actor.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_actor_bounds(actor_label: str) -> str:
        """Get bounding box origin and extent for an actor."""
        if err := sanitize_label(actor_label, "actor_label"):
            return make_error(err)

        safe_label = escape_for_fstring(actor_label)
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
    origin, extent = actor.get_actor_bounds(False)
    print("RESULT:" + json.dumps({{
        "label": actor.get_actor_label(),
        "origin": {{"x": origin.x, "y": origin.y, "z": origin.z}},
        "extent": {{"x": extent.x, "y": extent.y, "z": extent.z}},
    }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
