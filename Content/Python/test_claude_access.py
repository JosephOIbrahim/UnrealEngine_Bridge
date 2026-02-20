"""
test_claude_access.py - Verify Claude Code can script the UE5 editor.

Usage: In UE5 Python console, run:
    py test_claude_access.py

Expected: A cube spawns at origin with a green material, confirmation in Output Log.
"""

import unreal

# Spawn a static mesh actor at origin
actor_location = unreal.Vector(0.0, 0.0, 100.0)
actor_rotation = unreal.Rotator(0.0, 0.0, 0.0)

editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = editor_actor_subsystem.spawn_actor_from_class(
    unreal.StaticMeshActor,
    actor_location,
    actor_rotation
)

if actor is None:
    unreal.log_error("[ClaudeAccess] Failed to spawn StaticMeshActor")
else:
    actor.set_actor_label("ClaudeTestCube")

    # Assign cube mesh
    mesh_component = actor.get_component_by_class(unreal.StaticMeshComponent)
    cube_mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube")
    if cube_mesh:
        mesh_component.set_static_mesh(cube_mesh)

    # Create and assign a simple green material instance
    base_material = unreal.EditorAssetLibrary.load_asset(
        "/Engine/EngineMaterials/DefaultMaterial"
    )
    if base_material:
        mid = unreal.MaterialInstanceDynamic.create(base_material, actor)
        mid.set_vector_parameter_value(
            "BaseColor",
            unreal.LinearColor(0.1, 0.8, 0.2, 1.0)
        )
        mesh_component.set_material(0, mid)

    unreal.log("[ClaudeAccess] SUCCESS - Cube spawned at (0, 0, 100) with green material")
    unreal.log(f"[ClaudeAccess] Actor path: {actor.get_path_name()}")
