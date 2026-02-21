"""Blueprint and component tools for UE5 MCP server.

Note on UE5.7 Python limitations:
- Blueprint SCS (SimpleConstructionScript) is NOT exposed to Python in UE5.7.
- Components can be added to LIVE ACTORS at runtime via new_object + k2_attach_to.
- Blueprint assets can be created, compiled, and spawned.
- Blueprint CDO default values can be read/set.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("ue5-mcp.tools.blueprints")

from ._validation import (
    sanitize_class_name, sanitize_label, sanitize_content_path,
    sanitize_property_name, escape_for_fstring, make_error,
)


def register(server, ue):
    @server.tool(
        name="ue_create_blueprint",
        description=(
            "Create a new Blueprint asset. Returns the asset path. "
            "parent_class can be 'Actor', 'Pawn', 'Character', 'PlayerController', etc."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def create_blueprint(
        name: str,
        folder: str = "/Game/Blueprints",
        parent_class: str = "Actor",
    ) -> str:
        """Create a new Blueprint class asset."""
        if err := sanitize_label(name, "name"):
            return make_error(err)
        if err := sanitize_content_path(folder, "folder"):
            return make_error(err)
        if err := sanitize_class_name(parent_class, "parent_class"):
            return make_error(err)

        safe_name = escape_for_fstring(name)
        safe_folder = escape_for_fstring(folder)
        safe_class = escape_for_fstring(parent_class)
        code = f"""
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
factory = unreal.BlueprintFactory()
factory.set_editor_property("ParentClass", getattr(unreal, "{safe_class}", unreal.Actor))

blueprint = asset_tools.create_asset("{safe_name}", "{safe_folder}", None, factory)
if blueprint:
    unreal.EditorAssetLibrary.save_asset("{safe_folder}/{safe_name}")
    print("RESULT:" + blueprint.get_path_name())
else:
    print("RESULT:CREATE_FAILED")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_add_component",
        description=(
            "Add a component to a LIVE ACTOR in the level (not a Blueprint asset). "
            "Provide the actor's object path. component_class can be "
            "'StaticMeshComponent', 'PointLightComponent', 'SpotLightComponent', "
            "'AudioComponent', 'BoxComponent', 'SphereComponent', "
            "'SkeletalMeshComponent', 'NiagaraComponent', 'DecalComponent', etc. "
            "Returns the list of all components on the actor after adding."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def add_component(
        actor_label: str,
        component_class: str,
        component_name: str | None = None,
    ) -> str:
        """Add a component to a live actor by label. Uses new_object + k2_attach_to."""
        if err := sanitize_label(actor_label, "actor_label"):
            return make_error(err)
        if err := sanitize_class_name(component_class, "component_class"):
            return make_error(err)
        if component_name is not None:
            if err := sanitize_label(component_name, "component_name"):
                return make_error(err)

        comp_name = component_name or component_class.replace("Component", "")
        safe_label = escape_for_fstring(actor_label)
        safe_cc = escape_for_fstring(component_class)
        safe_cn = escape_for_fstring(comp_name)
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
    comp_class = getattr(unreal, "{safe_cc}", None)
    if comp_class is None:
        print("RESULT:" + json.dumps({{"error": "Component class not found: {safe_cc}"}}))
    else:
        comp = unreal.new_object(comp_class, actor, "{safe_cn}")
        if comp and actor.root_component:
            comp.k2_attach_to(actor.root_component)

        comps = actor.get_components_by_class(unreal.ActorComponent)
        comp_list = [c.get_class().get_name() for c in comps]
        print("RESULT:" + json.dumps({{
            "actor": actor.get_actor_label(),
            "added": "{safe_cn}",
            "class": "{safe_cc}",
            "all_components": comp_list
        }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_component_property",
        description=(
            "Set a property on a component of a live actor. "
            "Find the component by class name (e.g. 'StaticMeshComponent'). "
            "For asset references (meshes, materials), pass the content path as a string."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_component_property(
        actor_label: str,
        component_class: str,
        property_name: str,
        value: str,
    ) -> str:
        """Set a property on an actor's component. value is JSON (string, number, object, etc.)."""
        if err := sanitize_label(actor_label, "actor_label"):
            return make_error(err)
        if err := sanitize_class_name(component_class, "component_class"):
            return make_error(err)
        if err := sanitize_property_name(property_name):
            return make_error(err)
        # Validate value is parseable JSON
        try:
            json.loads(value)
        except json.JSONDecodeError as e:
            return make_error(f"Invalid JSON value: {e}")

        safe_label = escape_for_fstring(actor_label)
        safe_cc = escape_for_fstring(component_class)
        safe_prop = escape_for_fstring(property_name)
        safe_val = escape_for_fstring(value)
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
    comp_class = getattr(unreal, "{safe_cc}", None)
    comp = actor.get_component_by_class(comp_class) if comp_class else None

    if comp is None:
        comps = actor.get_components_by_class(unreal.ActorComponent)
        available = [c.get_class().get_name() for c in comps]
        print("RESULT:" + json.dumps({{"error": "Component not found: {safe_cc}", "available": available}}))
    else:
        val = json.loads('''{safe_val}''')
        # Handle asset path strings
        if isinstance(val, str) and val.startswith("/"):
            asset = unreal.EditorAssetLibrary.load_asset(val)
            if asset:
                val = asset
        try:
            comp.set_editor_property("{safe_prop}", val)
            print("RESULT:" + json.dumps({{"set": true, "component": "{safe_cc}", "property": "{safe_prop}"}}))
        except Exception as e:
            print("RESULT:" + json.dumps({{"error": str(e)}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_blueprint_defaults",
        description=(
            "Set default property values on a Blueprint's Class Default Object (CDO). "
            "Properties are passed as a JSON object string, e.g. "
            "'{\"MaxHealth\": 100, \"Speed\": 600.0}'"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_blueprint_defaults(
        blueprint_path: str,
        properties: str,
    ) -> str:
        """Set default values on a Blueprint's CDO. properties is a JSON string of key-value pairs."""
        if err := sanitize_content_path(blueprint_path, "blueprint_path"):
            return make_error(err)
        # Validate properties is valid JSON object
        try:
            props = json.loads(properties)
            if not isinstance(props, dict):
                return make_error("properties must be a JSON object")
            for key in props:
                if err := sanitize_property_name(key, f"property '{key}'"):
                    return make_error(err)
        except json.JSONDecodeError as e:
            return make_error(f"Invalid JSON in properties: {e}")

        safe_bp = escape_for_fstring(blueprint_path)
        safe_props = escape_for_fstring(properties)
        code = f"""
import unreal, json

bp = unreal.EditorAssetLibrary.load_asset("{safe_bp}")
if bp is None:
    print("RESULT:" + json.dumps({{"error": "Blueprint not found: {safe_bp}"}}))
else:
    cdo = unreal.get_default_object(bp.generated_class())
    props = json.loads('''{safe_props}''')
    results = {{}}
    for key, value in props.items():
        try:
            cdo.set_editor_property(key, value)
            results[key] = "set"
        except Exception as e:
            results[key] = str(e)

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset("{safe_bp}")
    print("RESULT:" + json.dumps({{"blueprint": "{safe_bp}", "properties": results}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_compile_blueprint",
        description="Compile a Blueprint asset. Run this after making changes to ensure they take effect.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def compile_blueprint(blueprint_path: str) -> str:
        """Compile and save a Blueprint."""
        if err := sanitize_content_path(blueprint_path, "blueprint_path"):
            return make_error(err)

        safe_bp = escape_for_fstring(blueprint_path)
        code = f"""
import unreal, json

bp = unreal.EditorAssetLibrary.load_asset("{safe_bp}")
if bp is None:
    print("RESULT:" + json.dumps({{"error": "Blueprint not found: {safe_bp}"}}))
else:
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset("{safe_bp}")
    print("RESULT:" + json.dumps({{"blueprint": "{safe_bp}", "compiled": True}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_actor_components",
        description="List all components on a live actor in the level, with their classes.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_actor_components(actor_label: str) -> str:
        """Inspect an actor's component hierarchy by actor label."""
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
    comps = actor.get_components_by_class(unreal.ActorComponent)
    comp_list = []
    for c in comps:
        comp_list.append({{
            "class": c.get_class().get_name(),
            "name": c.get_name(),
        }})
    print("RESULT:" + json.dumps({{
        "actor": actor.get_actor_label(),
        "actor_class": actor.get_class().get_name(),
        "components": comp_list,
    }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_spawn_blueprint",
        description="Spawn an instance of a Blueprint actor in the level.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def spawn_blueprint(
        blueprint_path: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rx: float = 0.0,
        ry: float = 0.0,
        rz: float = 0.0,
        label: str | None = None,
    ) -> str:
        """Spawn a Blueprint actor instance in the level."""
        if err := sanitize_content_path(blueprint_path, "blueprint_path"):
            return make_error(err)
        if label is not None:
            if err := sanitize_label(label):
                return make_error(err)

        safe_bp = escape_for_fstring(blueprint_path)
        label_line = ""
        if label:
            safe_lbl = escape_for_fstring(label)
            label_line = f'\n    actor.set_actor_label("{safe_lbl}")'
        code = f"""
import unreal, json

bp_class = unreal.EditorAssetLibrary.load_blueprint_class("{safe_bp}")
if bp_class is None:
    print("RESULT:" + json.dumps({{"error": "Blueprint not found: {safe_bp}"}}))
else:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(
        bp_class,
        unreal.Vector({x}, {y}, {z}),
        unreal.Rotator({rx}, {ry}, {rz})
    )
    if actor:{label_line}
        print("RESULT:" + actor.get_path_name())
    else:
        print("RESULT:" + json.dumps({{"error": "Spawn failed"}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
