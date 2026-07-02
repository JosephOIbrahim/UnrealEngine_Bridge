"""Motion graphics tools for UE5 MCP server.

Convenience wrappers for Avalanche, ClonerEffector, Niagara, and PCG plugins.
All route through ue_execute_python under the hood.
"""

from __future__ import annotations

import asyncio
import json
import logging

from ._types import MCPServer, UEBridge
from ._validation import escape_for_fstring, make_error, sanitize_content_path, sanitize_label

logger = logging.getLogger("ue5-mcp.tools.mograph")

# UCEClonerComponent.SetClonerActiveLayout loads the layout instance
# asynchronously — a second editor pass configures it after this delay.
CLONER_LAYOUT_POLL_DELAY_S = 0.5


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
        """Create a ClonerEffector. layout: Grid, Line, Circle, SphereUniform,
        SphereRandom, Honeycomb, Cylinder (5.7 registered layout names).
        count_x/y/z and spacing map fully onto the Grid layout; other layouts
        apply what their property set supports and report the rest skipped."""
        valid_layouts = {"Grid", "Line", "Circle", "SphereUniform", "SphereRandom", "Honeycomb", "Cylinder"}
        if layout not in valid_layouts:
            return make_error(f"Invalid layout '{layout}'. Must be one of: {', '.join(sorted(valid_layouts))}")
        if err := sanitize_content_path(mesh_path, "mesh_path"):
            return make_error(err)
        if label is not None:
            if err := sanitize_label(label):
                return make_error(err)

        label_str = escape_for_fstring(label or "ClaudeCloner")
        safe_mesh = escape_for_fstring(mesh_path)
        # Verified against the installed 5.7 ClonerEffector plugin source:
        # - the actor reflects as CEClonerActor (/Script/ClonerEffector.CEClonerActor)
        # - SetLayoutName silently ignores unknown names, so every write is
        #   verified by read-back before it may be reported "applied"
        # - the active layout loads asynchronously after layout_name is set,
        #   so count/spacing usually need the second pass below
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

cloner_class = unreal.find_class("CEClonerActor")
if cloner_class is None:
    cloner_class = unreal.load_class(None, "/Script/ClonerEffector.CEClonerActor")

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

        def _verified_set(obj, name, value):
            try:
                obj.set_editor_property(name, value)
                back = obj.get_editor_property(name)
                if str(back) == str(value):
                    applied.append(name)
                else:
                    skipped.append(name + ": write ignored (read-back " + str(back)[:40] + ")")
            except Exception as e:
                skipped.append(name + ": " + str(e)[:80])

        layout_pending = False
        comp_class = getattr(unreal, "CEClonerComponent", None)
        comp = cloner.get_component_by_class(comp_class) if comp_class else None
        if comp is None:
            skipped.append("layout/count/spacing: CEClonerComponent not found on actor")
        else:
            _verified_set(comp, "layout_name", "{layout}")
            layout_obj = None
            try:
                layout_obj = comp.get_editor_property("active_layout")
            except Exception:
                pass
            if layout_obj is not None and "{layout}".lower() in type(layout_obj).__name__.lower():
                for prop, value in [("count_x", {count_x}), ("count_y", {count_y}), ("count_z", {count_z}),
                                    ("spacing_x", {spacing}), ("spacing_y", {spacing}), ("spacing_z", {spacing})]:
                    _verified_set(layout_obj, prop, value)
            else:
                layout_pending = True

        mesh_attached = False
        try:
            mesh = unreal.EditorAssetLibrary.load_asset("{safe_mesh}")
            if mesh:
                child = subsystem.spawn_actor_from_class(
                    unreal.StaticMeshActor, cloner.get_actor_location(), unreal.Rotator(0, 0, 0))
                if child:
                    child.static_mesh_component.set_static_mesh(mesh)
                    child.attach_to_actor(cloner, "", unreal.AttachmentRule.KEEP_WORLD,
                                          unreal.AttachmentRule.KEEP_WORLD,
                                          unreal.AttachmentRule.KEEP_WORLD, False)
                    mesh_attached = True
            else:
                skipped.append("mesh: asset not found {safe_mesh}")
        except Exception as e:
            skipped.append("mesh: " + str(e)[:80])

        print("RESULT:" + json.dumps({{
            "created": cloner.get_path_name(),
            "layout": "{layout}",
            "layout_pending": layout_pending,
            "applied": applied,
            "skipped": skipped,
            "mesh_attached": mesh_attached,
        }}))
"""
        result = await ue.execute_python(code)
        first = result.get("result") if isinstance(result, dict) else None
        if not isinstance(first, dict) or not first.get("layout_pending"):
            return json.dumps(result, indent=2)

        # Layout instance was still loading — configure it in a second pass.
        await asyncio.sleep(CLONER_LAYOUT_POLL_DELAY_S)
        cloner_path = escape_for_fstring(str(first.get("created", "")))
        code2 = f"""
import unreal, json

applied, skipped = [], []
layout_pending = True
layout_class = None

def _verified_set(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        back = obj.get_editor_property(name)
        if str(back) == str(value):
            applied.append(name)
        else:
            skipped.append(name + ": write ignored (read-back " + str(back)[:40] + ")")
    except Exception as e:
        skipped.append(name + ": " + str(e)[:80])

cloner = unreal.load_object(None, "{cloner_path}")
comp_class = getattr(unreal, "CEClonerComponent", None)
comp = cloner.get_component_by_class(comp_class) if (cloner and comp_class) else None
if comp is None:
    skipped.append("configure: cloner or CEClonerComponent not found")
else:
    layout_obj = None
    try:
        layout_obj = comp.get_editor_property("active_layout")
    except Exception:
        pass
    if layout_obj is not None:
        layout_class = type(layout_obj).__name__
    if layout_obj is not None and "{layout}".lower() in type(layout_obj).__name__.lower():
        layout_pending = False
        for prop, value in [("count_x", {count_x}), ("count_y", {count_y}), ("count_z", {count_z}),
                            ("spacing_x", {spacing}), ("spacing_y", {spacing}), ("spacing_z", {spacing})]:
            _verified_set(layout_obj, prop, value)
    else:
        skipped.append("layout not active after wait (" + str(layout_class) + ") - counts/spacing not applied")

print("RESULT:" + json.dumps({{"applied": applied, "skipped": skipped,
                               "layout_pending": layout_pending, "layout_class": layout_class}}))
"""
        result2 = await ue.execute_python(code2)
        second = result2.get("result") if isinstance(result2, dict) else None
        if isinstance(second, dict):
            first["applied"] = list(first.get("applied", [])) + list(second.get("applied", []))
            first["skipped"] = list(first.get("skipped", [])) + list(second.get("skipped", []))
            first["layout_pending"] = bool(second.get("layout_pending"))
            first["layout_class"] = second.get("layout_class")
        else:
            first["skipped"] = list(first.get("skipped", [])) + [
                "configure pass failed: " + str((result2 or {}).get("error"))[:80]]
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
