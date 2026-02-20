"""Motion graphics tools for UE5 MCP server.

Convenience wrappers for Avalanche, ClonerEffector, Niagara, and PCG plugins.
All route through ue_execute_python under the hood.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("ue5-mcp.tools.mograph")

from ._validation import sanitize_label, sanitize_content_path, make_error


def _escape_for_fstring(s: str) -> str:
    """Escape a string for safe embedding in an f-string Python code template."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")


def register(server, ue):
    @server.tool(
        name="ue_create_cloner",
        description=(
            "Create a ClonerEffector actor that instances a mesh in a layout pattern. "
            "Requires the ClonerEffector plugin to be enabled."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def create_cloner(
        layout: str = "Grid",
        mesh_path: str = "/Engine/BasicShapes/Cube",
        count_x: int = 5,
        count_y: int = 5,
        count_z: int = 1,
        spacing: float = 200.0,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        label: str | None = None,
    ) -> str:
        """Create a ClonerEffector. layout can be: Grid, Circle, Line, Sphere, Honeycomb, Cylinder."""
        valid_layouts = {"Grid", "Circle", "Line", "Sphere", "Honeycomb", "Cylinder"}
        if layout not in valid_layouts:
            return make_error(f"Invalid layout '{layout}'. Must be one of: {', '.join(sorted(valid_layouts))}")
        if err := sanitize_content_path(mesh_path, "mesh_path"):
            return make_error(err)
        if label is not None:
            if err := sanitize_label(label):
                return make_error(err)

        label_str = _escape_for_fstring(label or "ClaudeCloner")
        code = f"""
import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# Spawn the Cloner actor
cloner_class = unreal.find_class("ClonerActor") or unreal.find_class("ACEClonerActor")
if cloner_class is None:
    # Try loading from the plugin module
    cloner_class = unreal.load_class(None, "/Script/ClonerEffector.ClonerActor")

if cloner_class:
    cloner = subsystem.spawn_actor_from_class(
        cloner_class,
        unreal.Vector({x}, {y}, {z}),
        unreal.Rotator(0, 0, 0)
    )
    if cloner:
        cloner.set_actor_label("{label_str}")
        print("RESULT:CREATED " + cloner.get_path_name())
    else:
        print("RESULT:SPAWN_FAILED")
else:
    print("RESULT:CLASS_NOT_FOUND - ClonerEffector plugin may not be loaded")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_create_niagara_system",
        description=(
            "Spawn a Niagara particle system actor in the level. "
            "Can use a template system asset or create a default one."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def create_niagara_system(
        system_asset: str | None = None,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        label: str | None = None,
    ) -> str:
        """Spawn a Niagara system. system_asset is an optional content path to a NiagaraSystem asset."""
        if system_asset is not None:
            if err := sanitize_content_path(system_asset, "system_asset"):
                return make_error(err)
        if label is not None:
            if err := sanitize_label(label):
                return make_error(err)

        label_str = _escape_for_fstring(label or "ClaudeNiagara")
        asset_line = ""
        if system_asset:
            safe_asset = _escape_for_fstring(system_asset)
            asset_line = f"""
    system = unreal.EditorAssetLibrary.load_asset("{safe_asset}")
    if system:
        comp = actor.get_component_by_class(unreal.NiagaraComponent)
        if comp:
            comp.set_asset(system)
"""
        code = f"""
import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = subsystem.spawn_actor_from_class(
    unreal.NiagaraActor if hasattr(unreal, 'NiagaraActor') else unreal.load_class(None, "/Script/Niagara.NiagaraActor"),
    unreal.Vector({x}, {y}, {z}),
    unreal.Rotator(0, 0, 0)
)
if actor:
    actor.set_actor_label("{label_str}")
{asset_line}
    print("RESULT:CREATED " + actor.get_path_name())
else:
    print("RESULT:SPAWN_FAILED")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_create_pcg_graph",
        description=(
            "Create a PCG (Procedural Content Generation) volume actor in the level. "
            "Requires the PCG plugin to be enabled."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def create_pcg_graph(
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        extent_x: float = 1000.0,
        extent_y: float = 1000.0,
        extent_z: float = 500.0,
        label: str | None = None,
    ) -> str:
        """Create a PCG volume. extent controls the bounds of the procedural generation area."""
        if label is not None:
            if err := sanitize_label(label):
                return make_error(err)

        label_str = _escape_for_fstring(label or "ClaudePCG")
        code = f"""
import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# Try to find the PCG volume class
pcg_class = None
for class_name in ["PCGVolume", "APCGVolume", "PCGComponent"]:
    pcg_class = unreal.find_class(class_name)
    if pcg_class:
        break

if pcg_class is None:
    pcg_class = unreal.load_class(None, "/Script/PCG.PCGVolume")

if pcg_class:
    actor = subsystem.spawn_actor_from_class(
        pcg_class,
        unreal.Vector({x}, {y}, {z}),
        unreal.Rotator(0, 0, 0)
    )
    if actor:
        actor.set_actor_label("{label_str}")
        actor.set_actor_scale3d(unreal.Vector({extent_x / 100}, {extent_y / 100}, {extent_z / 100}))
        print("RESULT:CREATED " + actor.get_path_name())
    else:
        print("RESULT:SPAWN_FAILED")
else:
    print("RESULT:CLASS_NOT_FOUND - PCG plugin may not be loaded")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
