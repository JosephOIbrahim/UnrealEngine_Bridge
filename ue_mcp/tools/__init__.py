"""Tool registry for UE5 MCP server.

Tools are classified into tiers per docs/EPIC_MCP_MATRIX.md (the retirement
contract-of-record, live-probed against Epic's official Unreal MCP on UE 5.8):

- CORE             differentiated capability Epic does not ship; always mounted
- LEGACY_COMMODITY covered by Epic's MCP surface (matrix verdict RETIRE);
                   mounted only under the "full" profile
- EXPERIMENTAL     known-incomplete (honest not-implemented stubs); "all" only

The active profile comes from the UE_MCP_PROFILE env var (default: "core" —
the M4 flip). Run with UE_MCP_PROFILE=full to remount the commodity tools,
e.g. when Epic's MCP is not enabled in the editor.
"""

import os
from enum import StrEnum

from ._types import MCPServer, UEBridge
from .actors import register as register_actors
from .assets import register as register_assets
from .blueprints import register as register_blueprints
from .editor import register as register_editor
from .level import register as register_level
from .lighting import register as register_lighting
from .materials import register as register_materials
from .mograph import register as register_mograph
from .perception import register as register_perception
from .properties import register as register_properties
from .python_exec import register as register_python_exec
from .scene import register as register_scene
from .sequencer import register as register_sequencer
from .spatial import register as register_spatial
from .x3d import register as register_x3d


class Tier(StrEnum):
    CORE = "core"
    LEGACY_COMMODITY = "legacy_commodity"
    EXPERIMENTAL = "experimental"


_CORE = Tier.CORE
_LEGACY = Tier.LEGACY_COMMODITY
_EXP = Tier.EXPERIMENTAL

# One entry per registered tool. Every LEGACY_COMMODITY verdict cites its row
# in docs/EPIC_MCP_MATRIX.md §2; keep the two in sync (tests pin the counts).
TIERS: dict[str, Tier] = {
    # actors.py — Epic ActorTools/SceneTools cover all but duplication
    "ue_spawn_actor": _LEGACY,        # SceneTools.add_to_scene_from_class
    "ue_delete_actor": _LEGACY,       # SceneTools.remove_from_scene
    "ue_list_actors": _LEGACY,        # SceneTools.find_actors
    "ue_set_transform": _LEGACY,      # ActorTools.set_actor_transform
    "ue_duplicate_actor": _CORE,      # no level-actor duplication in the probe
    "ue_get_actor_bounds": _LEGACY,   # ActorTools.get_actor_bounds
    # properties.py — Epic ObjectTools is exactly this
    "ue_get_property": _LEGACY,       # ObjectTools.get_properties
    "ue_set_property": _LEGACY,       # ObjectTools.set_properties
    # python_exec.py — Epic's execute_tool_script is sandboxed (no unreal import)
    "ue_execute_python": _CORE,
    # assets.py
    "ue_find_assets": _LEGACY,        # AssetTools.find_assets (+ semantic search)
    "ue_create_material": _LEGACY,    # MaterialTools.create_material + graph tools
    "ue_delete_asset": _LEGACY,       # AssetTools.delete
    # level.py
    "ue_save_level": _LEGACY,         # AssetTools.save_assets + SceneTools.save_actor
    "ue_get_level_info": _LEGACY,     # SceneTools.get_current_level + find_actors
    "ue_load_level": _LEGACY,         # SceneTools.load_level
    "ue_get_world_info": _CORE,       # no streaming-levels enumeration in the probe
    # mograph.py
    "ue_create_cloner": _CORE,        # no ClonerEffector toolset in the probe
    "ue_create_niagara_system": _LEGACY,  # NiagaraToolset_System.CreateNiagaraSystem
    "ue_create_pcg_graph": _LEGACY,   # PCG.CreateGraph + SpawnGraphInstance
    # blueprints.py — Epic BlueprintTools (53) + ActorTools/ObjectTools
    "ue_create_blueprint": _LEGACY,
    "ue_add_component": _LEGACY,
    "ue_set_component_property": _LEGACY,
    "ue_set_blueprint_defaults": _LEGACY,
    "ue_compile_blueprint": _LEGACY,
    "ue_get_actor_components": _LEGACY,
    "ue_spawn_blueprint": _LEGACY,
    # perception.py — continuous watch / diff / correlation have no Epic counterpart
    "ue_viewport_percept": _CORE,     # KEEP-PARTIAL: correlation + fallback stay ours
    "ue_viewport_watch": _CORE,
    "ue_viewport_config": _CORE,
    "ue_viewport_diff": _CORE,
    # scene.py
    "ue_get_actor_details": _LEGACY,  # find_actors + get_actor_transform + ...
    "ue_query_scene": _LEGACY,        # SceneTools.find_actors
    "ue_get_component_details": _LEGACY,  # get_components + get_properties
    "ue_get_actor_hierarchy": _CORE,  # no one-shot recursive attachment tree
    # spatial.py — normal-aware reasoning; trace_world returns distance only
    "ue_ground_trace": _CORE,
    "ue_snap_to_ground": _CORE,
    "ue_spatial_query": _CORE,
    "ue_measure": _LEGACY,            # arithmetic over two probe-verified reads
    # lighting.py — no sky/atmosphere/mood tooling anywhere in the probe
    "ue_setup_sky_atmosphere": _CORE,
    "ue_set_time_of_day": _CORE,
    "ue_list_mood_presets": _CORE,
    "ue_apply_mood_preset": _CORE,
    "ue_blend_mood_presets": _CORE,
    # materials.py — Epic MaterialInstanceTools + mesh set_material
    "ue_create_material_instance": _LEGACY,
    "ue_set_material_parameter": _LEGACY,
    "ue_get_material_parameters": _LEGACY,
    "ue_assign_material": _LEGACY,
    # editor.py
    "ue_console_command": _CORE,      # no console exec anywhere in the probe
    "ue_undo": _EXP,                  # honest not-implemented; capability slot kept
    "ue_redo": _EXP,
    "ue_focus_actor": _LEGACY,        # EditorApp.FocusOnActors
    "ue_select_actors": _LEGACY,      # EditorApp.SelectActors
    # sequencer.py — Epic ships 140 SequencerTools + 22 KeyframingTools
    "ue_create_level_sequence": _LEGACY,
    "ue_play_sequence": _LEGACY,
    "ue_add_actor_to_sequence": _LEGACY,
    "ue_add_keyframe": _LEGACY,
    # x3d.py — UE<->X3D thin-slice harness (no Epic counterpart)
    "ue_x3d_export": _CORE,
    "ue_x3d_validate": _CORE,
    "ue_x3d_apply": _CORE,
    "ue_x3d_preview": _CORE,
}

PROFILES: dict[str, set[Tier]] = {
    "core": {Tier.CORE},
    "full": {Tier.CORE, Tier.LEGACY_COMMODITY},
    "all": {Tier.CORE, Tier.LEGACY_COMMODITY, Tier.EXPERIMENTAL},
}

DEFAULT_PROFILE = "core"


class ToolRegistry:
    """Wraps the MCP server; drops registrations whose tier is outside the
    active profile. Returned by register_all_tools as the mount report."""

    def __init__(self, inner: MCPServer, profile: str):
        self._inner = inner
        self.profile = profile
        self.profile_warning: str | None = None
        if profile not in PROFILES:
            self.profile_warning = (
                f"unknown UE_MCP_PROFILE {profile!r}; falling back to {DEFAULT_PROFILE!r}"
            )
            self.profile = DEFAULT_PROFILE
        self._active = PROFILES[self.profile]
        self.registered: list[str] = []
        self.skipped: list[str] = []
        self.unclassified: list[str] = []  # fail-open; CI pins TIERS completeness

    def tool(self, *, name: str, description: str, annotations: dict | None = None):
        tier = TIERS.get(name)
        if tier is None:
            self.unclassified.append(name)
            tier = Tier.CORE
        if tier not in self._active:
            self.skipped.append(name)
            return lambda fn: fn  # no-op decorator: code stays, tool unmounted
        self.registered.append(name)
        return self._inner.tool(name=name, description=description, annotations=annotations)


_ALL_REGISTER_FNS = (
    register_actors,
    register_properties,
    register_python_exec,
    register_assets,
    register_level,
    register_mograph,
    register_blueprints,
    register_perception,
    register_scene,
    register_spatial,
    register_lighting,
    register_materials,
    register_editor,
    register_sequencer,
    register_x3d,
)


def register_all_tools(server: MCPServer, ue: UEBridge, profile: str | None = None) -> ToolRegistry:
    """Register tool modules with the MCP server, filtered by profile.

    Profile resolution: explicit arg > UE_MCP_PROFILE env > "core" (the default
    since the Epic-MCP retirement flip; see docs/EPIC_MCP_MATRIX.md).
    """
    resolved = profile or os.environ.get("UE_MCP_PROFILE") or DEFAULT_PROFILE
    registry = ToolRegistry(server, resolved)
    for register in _ALL_REGISTER_FNS:
        register(registry, ue)
    return registry
