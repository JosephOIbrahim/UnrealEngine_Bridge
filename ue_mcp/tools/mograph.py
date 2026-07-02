"""Motion graphics tools for UE5 MCP server.

Convenience wrappers for Avalanche, ClonerEffector, Niagara, and PCG plugins.
All route through ue_execute_python under the hood.
"""

from __future__ import annotations

import json
import logging

from ._types import MCPServer, UEBridge
from ._validation import escape_for_fstring, make_error, sanitize_content_path, sanitize_label

logger = logging.getLogger("ue5-mcp.tools.mograph")


def register(server: MCPServer, ue: UEBridge) -> None:
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

        label_str = escape_for_fstring(label or "ClaudeCloner")
        safe_mesh = escape_for_fstring(mesh_path)
        # ClonerEffector clones its ATTACHED child actors; layout/count/spacing
        # live on the cloner component and its active layout object. Property
        # names could not be verified against a live editor, so every write goes
        # through _safe_set and is reported applied/skipped (lighting.py pattern)
        # instead of silently pretending.
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

cloner_class = unreal.find_class("ClonerActor") or unreal.find_class("ACEClonerActor")
if cloner_class is None:
    cloner_class = unreal.load_class(None, "/Script/ClonerEffector.ClonerActor")

if cloner_class is None:
    print("RESULT:" + json.dumps({{"error": "CLASS_NOT_FOUND - ClonerEffector plugin may not be loaded"}}))
else:
    cloner = subsystem.spawn_actor_from_class(
        cloner_class,
        unreal.Vector({x}, {y}, {z}),
        unreal.Rotator(0, 0, 0)
    )
    if cloner is None:
        print("RESULT:" + json.dumps({{"error": "SPAWN_FAILED"}}))
    else:
        cloner.set_actor_label("{label_str}")
        applied, skipped = [], []

        def _safe_set(obj, name, value):
            try:
                obj.set_editor_property(name, value)
                applied.append(name)
            except Exception as e:
                skipped.append(name + ": " + str(e)[:80])

        comp = None
        comp_class = getattr(unreal, "CEClonerComponent", None)
        if comp_class:
            comp = cloner.get_component_by_class(comp_class)
        if comp is None:
            skipped.append("layout/count/spacing: CEClonerComponent not found on actor")
        else:
            _safe_set(comp, "layout_name", "{layout}")
            layout_obj = None
            try:
                layout_obj = comp.get_editor_property("active_layout")
            except Exception:
                pass
            target = layout_obj if layout_obj is not None else comp
            _safe_set(target, "count_x", {count_x})
            _safe_set(target, "count_y", {count_y})
            _safe_set(target, "count_z", {count_z})
            _safe_set(target, "spacing_x", {spacing})
            _safe_set(target, "spacing_y", {spacing})
            _safe_set(target, "spacing_z", {spacing})

        mesh_attached = False
        try:
            mesh = unreal.EditorAssetLibrary.load_asset("{safe_mesh}")
            if mesh:
                child = subsystem.spawn_actor_from_class(
                    unreal.StaticMeshActor, unreal.Vector({x}, {y}, {z}), unreal.Rotator(0, 0, 0))
                if child:
                    child.static_mesh_component.set_static_mesh(mesh)
                    child.attach_to_actor(cloner, "", unreal.AttachmentRule.KEEP_RELATIVE,
                                          unreal.AttachmentRule.KEEP_RELATIVE,
                                          unreal.AttachmentRule.KEEP_RELATIVE, False)
                    mesh_attached = True
            else:
                skipped.append("mesh: asset not found {safe_mesh}")
        except Exception as e:
            skipped.append("mesh: " + str(e)[:80])

        print("RESULT:" + json.dumps({{
            "created": cloner.get_path_name(),
            "layout": "{layout}",
            "applied": applied,
            "skipped": skipped,
            "mesh_attached": mesh_attached,
        }}))
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

        label_str = escape_for_fstring(label or "ClaudeNiagara")
        asset_line = ""
        if system_asset:
            safe_asset = escape_for_fstring(system_asset)
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

        label_str = escape_for_fstring(label or "ClaudePCG")
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
