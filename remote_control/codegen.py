"""Code generation helpers for UE5 Python scripts.

All UE5 Python script strings are built here, once.
No I/O -- pure string construction.
"""



class _CodeGen:
    """Generates UE5 Python scripts. No I/O -- pure string construction."""

    @staticmethod
    def spawn_actor_code(
        class_path: str,
        location: tuple[float, float, float],
        rotation: tuple[float, float, float],
        label: str | None,
    ) -> str:
        loc_str = f"unreal.Vector({location[0]}, {location[1]}, {location[2]})"
        rot_str = f"unreal.Rotator({rotation[0]}, {rotation[1]}, {rotation[2]})"
        label_line = f'\n    actor.set_actor_label("{label}")' if label else ""
        return f"""
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = subsystem.spawn_actor_from_class(
    unreal.EditorAssetLibrary.load_blueprint_class("{class_path}") if "/" in "{class_path}" else getattr(unreal, "{class_path}"),
    {loc_str},
    {rot_str}
)
if actor:{label_line}
    result = actor.get_path_name()
else:
    result = "SPAWN_FAILED"
print("RESULT:" + result)
"""

    @staticmethod
    def delete_actor_code(actor_path: str) -> str:
        # Level actors are subobjects (…:PersistentLevel.Name) — the Content-Browser
        # asset API returns None for them; load_object resolves both forms.
        return f"""
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = unreal.load_object(None, "{actor_path}")
if actor:
    subsystem.destroy_actor(actor)
    print("RESULT:DELETED")
else:
    print("RESULT:NOT_FOUND")
"""

    @staticmethod
    def list_actors_code(class_filter: str | None = None) -> str:
        filter_line = ""
        if class_filter:
            filter_line = f"""
    if not actor.get_class().get_name() == "{class_filter}":
        continue"""
        return f"""
import unreal, json
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
results = []
for actor in actors:{filter_line}
    results.append({{
        "name": actor.get_actor_label(),
        "class": actor.get_class().get_name(),
        "path": actor.get_path_name(),
        "location": [actor.get_actor_location().x, actor.get_actor_location().y, actor.get_actor_location().z]
    }})
print("RESULT:" + json.dumps(results))
"""

    @staticmethod
    def set_actor_transform_code(
        actor_path: str,
        location: tuple[float, float, float] | None,
        rotation: tuple[float, float, float] | None,
        scale: tuple[float, float, float] | None,
    ) -> str:
        lines = ["import unreal"]
        lines.append(f'actor = unreal.load_object(None, "{actor_path}")')
        lines.append("if actor:")
        if location:
            lines.append(f"    actor.set_actor_location(unreal.Vector({location[0]}, {location[1]}, {location[2]}), False, False)")
        if rotation:
            lines.append(f"    actor.set_actor_rotation(unreal.Rotator({rotation[0]}, {rotation[1]}, {rotation[2]}), False)")
        if scale:
            lines.append(f"    actor.set_actor_scale3d(unreal.Vector({scale[0]}, {scale[1]}, {scale[2]}))")
        lines.append('    print("RESULT:OK")')
        lines.append('else:')
        lines.append('    print("RESULT:NOT_FOUND")')
        return "\n".join(lines)

    @staticmethod
    def find_assets_code(search_pattern: str, class_filter: str | None = None) -> str:
        return f"""
import unreal, json
registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = registry.get_assets_by_package_name("{search_pattern}") if "/" in "{search_pattern}" else []
if not assets:
    filt = unreal.ARFilter()
    assets = registry.get_all_assets(filt)
    assets = [a for a in assets if "{search_pattern}".lower() in str(a.asset_name).lower()]
results = []
for a in assets[:50]:
    results.append({{
        "name": str(a.asset_name),
        "path": str(a.package_name),
        "class": str(a.asset_class_path.asset_name) if hasattr(a.asset_class_path, 'asset_name') else str(a.asset_class_path)
    }})
print("RESULT:" + json.dumps(results))
"""

    @staticmethod
    def get_level_info_code() -> str:
        return """
import unreal, json
world = unreal.EditorLevelLibrary.get_editor_world()
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
level_name = world.get_name() if world else "Unknown"
print("RESULT:" + json.dumps({
    "level_name": level_name,
    "actor_count": len(actors)
}))
"""

    @staticmethod
    def save_level_code() -> str:
        return """
import unreal
unreal.EditorLevelLibrary.save_current_level()
print("RESULT:SAVED")
"""
