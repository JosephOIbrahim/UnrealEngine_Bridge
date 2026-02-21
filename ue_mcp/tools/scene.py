"""Scene understanding tools for UE5 MCP server.

Read-only tools for querying actor details, scene contents, component
inspection, and actor hierarchy traversal. All route through
ue_execute_python to run inside the editor.
"""

from __future__ import annotations

import json
import logging

from ._validation import (
    sanitize_label, sanitize_class_name, sanitize_object_path,
    escape_for_fstring, make_error,
)

logger = logging.getLogger("ue5-mcp.tools.scene")


def register(server, ue):
    @server.tool(
        name="ue_get_actor_details",
        description=(
            "Get full details about an actor: class, transform, components, "
            "visibility, tags, and parent actor. Lookup by label."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_actor_details(actor_label: str) -> str:
        """Get comprehensive info about an actor by its label."""
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
    loc = actor.get_actor_location()
    rot = actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()

    comps = actor.get_components_by_class(unreal.ActorComponent)
    comp_list = [c.get_class().get_name() for c in comps]

    tags = [str(t) for t in actor.tags] if hasattr(actor, 'tags') else []

    parent = actor.get_attach_parent_actor()
    parent_label = parent.get_actor_label() if parent else None

    print("RESULT:" + json.dumps({{
        "label": actor.get_actor_label(),
        "class": actor.get_class().get_name(),
        "path": actor.get_path_name(),
        "location": {{"x": loc.x, "y": loc.y, "z": loc.z}},
        "rotation": {{"pitch": rot.pitch, "yaw": rot.yaw, "roll": rot.roll}},
        "scale": {{"x": scale.x, "y": scale.y, "z": scale.z}},
        "visible": actor.is_hidden() is False,
        "components": comp_list,
        "tags": tags,
        "parent": parent_label,
    }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_query_scene",
        description=(
            "Query actors in the scene with optional filters: class name, tag, "
            "name pattern (substring match), and spatial proximity search. "
            "Returns up to max_results matches (default 100)."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def query_scene(
        class_filter: str | None = None,
        tag_filter: str | None = None,
        name_pattern: str | None = None,
        near_x: float | None = None,
        near_y: float | None = None,
        near_z: float | None = None,
        radius: float = 1000.0,
        max_results: int = 100,
    ) -> str:
        """Query actors with filters. All filters are AND-combined."""
        if class_filter is not None:
            if err := sanitize_class_name(class_filter, "class_filter"):
                return make_error(err)
        if tag_filter is not None:
            if err := sanitize_label(tag_filter, "tag_filter"):
                return make_error(err)
        if name_pattern is not None:
            if err := sanitize_label(name_pattern, "name_pattern"):
                return make_error(err)
        max_results = max(1, min(max_results, 500))

        spatial = (near_x is not None and near_y is not None and near_z is not None)

        safe_class = escape_for_fstring(class_filter) if class_filter else ""
        safe_tag = escape_for_fstring(tag_filter) if tag_filter else ""
        safe_pattern = escape_for_fstring(name_pattern) if name_pattern else ""

        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
results = []
max_results = {max_results}

class_filter = "{safe_class}" if "{safe_class}" else None
tag_filter = "{safe_tag}" if "{safe_tag}" else None
name_pattern = "{safe_pattern}".lower() if "{safe_pattern}" else None
spatial = {spatial}
near = unreal.Vector({near_x or 0}, {near_y or 0}, {near_z or 0})
radius = {radius}

for actor in actors:
    if len(results) >= max_results:
        break

    # Class filter
    if class_filter and actor.get_class().get_name() != class_filter:
        continue

    # Tag filter
    if tag_filter:
        tags = [str(t) for t in actor.tags] if hasattr(actor, 'tags') else []
        if tag_filter not in tags:
            continue

    # Name pattern (substring, case-insensitive)
    if name_pattern and name_pattern not in actor.get_actor_label().lower():
        continue

    # Spatial filter
    if spatial:
        loc = actor.get_actor_location()
        dist = (loc - near).length()
        if dist > radius:
            continue

    loc = actor.get_actor_location()
    results.append({{
        "label": actor.get_actor_label(),
        "class": actor.get_class().get_name(),
        "path": actor.get_path_name(),
        "location": {{"x": loc.x, "y": loc.y, "z": loc.z}},
    }})

print("RESULT:" + json.dumps({{"count": len(results), "actors": results}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_component_details",
        description=(
            "Get detailed info about a specific component on an actor: "
            "mesh asset, material slots, light parameters, etc."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_component_details(actor_label: str, component_name: str) -> str:
        """Inspect a specific component on an actor."""
        if err := sanitize_label(actor_label, "actor_label"):
            return make_error(err)
        if err := sanitize_label(component_name, "component_name"):
            return make_error(err)

        safe_label = escape_for_fstring(actor_label)
        safe_comp = escape_for_fstring(component_name)
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
    comps = actor.get_components_by_class(unreal.ActorComponent)
    target = None
    for c in comps:
        if c.get_name() == "{safe_comp}" or c.get_class().get_name() == "{safe_comp}":
            target = c
            break

    if target is None:
        available = [c.get_name() + " (" + c.get_class().get_name() + ")" for c in comps]
        print("RESULT:" + json.dumps({{"error": "Component not found: {safe_comp}", "available": available}}))
    else:
        info = {{
            "name": target.get_name(),
            "class": target.get_class().get_name(),
        }}

        # Mesh component details
        if hasattr(target, 'static_mesh') or hasattr(target, 'get_static_mesh'):
            try:
                mesh = target.static_mesh if hasattr(target, 'static_mesh') else target.get_static_mesh()
                info["mesh"] = mesh.get_path_name() if mesh else None
            except Exception:
                pass
        if hasattr(target, 'get_num_materials'):
            try:
                n = target.get_num_materials()
                mats = []
                for i in range(n):
                    m = target.get_material(i)
                    mats.append(m.get_path_name() if m else None)
                info["materials"] = mats
            except Exception:
                pass

        # Light component details
        if hasattr(target, 'intensity'):
            try:
                info["intensity"] = target.get_editor_property("intensity")
            except Exception:
                pass
        if hasattr(target, 'light_color'):
            try:
                col = target.get_editor_property("light_color")
                info["light_color"] = {{"r": col.r, "g": col.g, "b": col.b, "a": col.a}}
            except Exception:
                pass

        print("RESULT:" + json.dumps(info))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_actor_hierarchy",
        description=(
            "Get the parent-child attachment tree for an actor. "
            "Shows all attached children recursively (max depth 10)."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_actor_hierarchy(actor_label: str) -> str:
        """Get attachment hierarchy starting from an actor."""
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
    def build_tree(a, depth=0):
        if depth > 10:
            return {{"label": a.get_actor_label(), "class": a.get_class().get_name(), "truncated": True}}
        children = a.get_attached_actors()
        child_list = [build_tree(c, depth + 1) for c in children] if children else []
        return {{
            "label": a.get_actor_label(),
            "class": a.get_class().get_name(),
            "children": child_list,
        }}

    # Walk up to root
    root = actor
    parent = root.get_attach_parent_actor()
    while parent:
        root = parent
        parent = root.get_attach_parent_actor()

    tree = build_tree(root)
    print("RESULT:" + json.dumps(tree))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
