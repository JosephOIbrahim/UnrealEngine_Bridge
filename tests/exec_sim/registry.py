"""Registry of every MCP tool registered by ``register_all_tools``.

Completeness is gate #1: test_codegen_exec asserts that the keys of REGISTRY
equal the registered tool names exactly, so a future tool cannot dodge the
harness -- it must be classified here as CODEGEN or DIRECT.

Modes:

- CODEGEN: the tool (or the client method it delegates to) builds a UE editor
  Python script and sends it through ``ue.execute_python``. Exec-simulated.
- DIRECT: no Python is generated (HTTP Remote Control object calls, HTTP to
  the perception plugin, pure server-side data, or verbatim pass-through).
  Skipped by the exec gates; the ``notes`` field carries the reason.

Sentinel values are distinctive so the sentinel gate can assert each
``sentinel_checkable`` kwarg appears *literally* in the generated source
(raw or f-string-escaped) -- catching validated-then-discarded arguments.
Floats are dyadic (x.25 / x.4375 ...) so ``str()``/``json.dumps`` round-trip
exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CODEGEN = "CODEGEN"
DIRECT = "DIRECT"

# Shared sentinels -- the stub's seeded world (unreal_stub._ACTOR_SPECS) matches
# these so tool success branches actually execute.
SENTINEL_LABEL = "SENTINEL_LBL_9Q"
SENTINEL_LABEL_B = "SENTINEL_LBL_B2"
SENTINEL_TAG = "SENTINEL_TAG_9Q"
SENTINEL_ACTOR_PATH = "/Game/Maps/TestMap.TestMap:PersistentLevel.SENTINEL_ACT_9Q"
SENTINEL_DIR = "/Game/SENTINEL_DIR_9Q"
SENTINEL_ASSET_PATH = SENTINEL_DIR + "/SENTINEL_ASSET_9Q"
SENTINEL_BP_PATH = SENTINEL_DIR + "/SENTINEL_BP_9Q"
SENTINEL_SEQ_PATH = SENTINEL_DIR + "/SENTINEL_SEQ_9Q"
SENTINEL_MAT_PATH = SENTINEL_DIR + "/SENTINEL_MAT_9Q"
SENTINEL_MAP_PATH = "/Game/Maps/SENTINEL_MAP_9Q"
SENTINEL_MESH_PATH = "/Game/Meshes/SENTINEL_MESH_9Q"
SENTINEL_FX_PATH = "/Game/FX/SENTINEL_FX_9Q"
SENTINEL_PROP = "SENTINEL_Prop_9Q"


@dataclass(frozen=True)
class ToolEntry:
    tool_name: str
    mode: str
    kwargs: dict = field(default_factory=dict)
    # kwarg names whose values must appear literally in the generated source
    sentinel_checkable: tuple[str, ...] = ()
    # True when an honest error RESULT is the correct behavior under the
    # default all-success stub (e.g. a not-implemented report).
    expect_error: bool = False
    notes: str = ""


_ENTRIES = [
    # ------------------------------------------------------------- actors.py
    ToolEntry(
        "ue_spawn_actor", CODEGEN,
        kwargs=dict(class_name="StaticMeshActor", x=7317.25, y=811.25, z=97.25,
                    rx=14.25, ry=28.25, rz=42.25, label=SENTINEL_LABEL),
        sentinel_checkable=("class_name", "x", "y", "z", "rx", "ry", "rz", "label"),
        notes="codegen via client (_CodeGen.spawn_actor_code)",
    ),
    ToolEntry(
        "ue_delete_actor", CODEGEN,
        kwargs=dict(actor_path=SENTINEL_ACTOR_PATH),
        sentinel_checkable=("actor_path",),
        notes="codegen via client; actor-resolver contract gated in test_honesty",
    ),
    ToolEntry(
        "ue_list_actors", CODEGEN,
        kwargs=dict(class_filter="SENTINEL_Cls9Q"),
        sentinel_checkable=("class_filter",),
        notes="codegen via client (_CodeGen.list_actors_code)",
    ),
    ToolEntry(
        "ue_set_transform", CODEGEN,
        # Sentinel values must not be substrings of each other ("1.25" hides
        # inside "811.25"), or a dropped kwarg can pass the sentinel gate.
        kwargs=dict(actor_path=SENTINEL_ACTOR_PATH, x=7317.25, y=811.25, z=97.25,
                    rx=14.25, ry=28.25, rz=42.25, sx=51.5625, sy=62.8125, sz=73.1875),
        sentinel_checkable=("actor_path", "x", "y", "z", "rx", "ry", "rz", "sx", "sy", "sz"),
        notes="codegen via client; actor-resolver contract gated in test_honesty",
    ),
    ToolEntry(
        "ue_duplicate_actor", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL, offset_x=433.25, offset_y=12.25, offset_z=99.25),
        sentinel_checkable=("actor_label", "offset_x", "offset_y", "offset_z"),
    ),
    ToolEntry(
        "ue_get_actor_bounds", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL),
        sentinel_checkable=("actor_label",),
    ),
    # --------------------------------------------------------- properties.py
    ToolEntry(
        "ue_get_property", DIRECT,
        notes="direct Remote Control HTTP property read (rc.get_property); no Python generated",
    ),
    ToolEntry(
        "ue_set_property", DIRECT,
        notes="direct Remote Control HTTP property write (rc.set_property); no Python generated",
    ),
    # -------------------------------------------------------- python_exec.py
    ToolEntry(
        "ue_execute_python", DIRECT,
        notes="pass-through: executes caller-supplied code verbatim; nothing generated to verify",
    ),
    # ------------------------------------------------------------- assets.py
    ToolEntry(
        "ue_find_assets", CODEGEN,
        kwargs=dict(search_pattern="SENTINELPAT9Q"),
        sentinel_checkable=("search_pattern",),
        notes="codegen via client; quote/backslash escaping gated in test_honesty. "
              "class_filter is accepted but ignored by the current codegen (not gated here).",
    ),
    ToolEntry(
        "ue_create_material", CODEGEN,
        kwargs=dict(name="SENTINEL_MAT_9Q", base_color_r=0.11, base_color_g=0.23,
                    base_color_b=0.37, roughness=0.4375, metallic=0.8125),
        sentinel_checkable=("name", "base_color_r", "base_color_g", "base_color_b",
                            "roughness", "metallic"),
    ),
    ToolEntry(
        "ue_delete_asset", CODEGEN,
        kwargs=dict(asset_path=SENTINEL_ASSET_PATH),
        sentinel_checkable=("asset_path",),
    ),
    # -------------------------------------------------------------- level.py
    ToolEntry("ue_save_level", CODEGEN, notes="codegen via client (_CodeGen.save_level_code)"),
    ToolEntry("ue_get_level_info", CODEGEN, notes="codegen via client (_CodeGen.get_level_info_code)"),
    ToolEntry(
        "ue_load_level", CODEGEN,
        kwargs=dict(level_path=SENTINEL_MAP_PATH),
        sentinel_checkable=("level_path",),
        notes="scripted-failure honesty contract in test_honesty (load_level -> False)",
    ),
    ToolEntry("ue_get_world_info", CODEGEN),
    # ------------------------------------------------------------ mograph.py
    ToolEntry(
        "ue_create_cloner", CODEGEN,
        # x/y/z use collision-free fractions (3.25 hides inside spacing=433.25).
        kwargs=dict(layout="Circle", mesh_path=SENTINEL_MESH_PATH,
                    count_x=7317, count_y=6113, count_z=4231, spacing=433.25,
                    x=151.5625, y=262.8125, z=373.1875, label=SENTINEL_LABEL),
        sentinel_checkable=("layout", "mesh_path", "count_x", "count_y", "count_z",
                            "spacing", "x", "y", "z", "label"),
        notes="sentinel gate is the arg-discard trap (layout/counts/spacing/mesh_path)",
    ),
    ToolEntry(
        "ue_create_niagara_system", CODEGEN,
        kwargs=dict(system_asset=SENTINEL_FX_PATH, x=4.25, y=5.25, z=6.25, label=SENTINEL_LABEL),
        sentinel_checkable=("system_asset", "x", "y", "z", "label"),
    ),
    ToolEntry(
        "ue_create_pcg_graph", CODEGEN,
        kwargs=dict(x=1234.25, y=2345.25, z=3456.25, label=SENTINEL_LABEL),
        sentinel_checkable=("x", "y", "z", "label"),
        notes="extent_* excluded from sentinel gate: embedded transformed (extent/100), not literally",
    ),
    # --------------------------------------------------------- blueprints.py
    ToolEntry(
        "ue_create_blueprint", CODEGEN,
        kwargs=dict(name="SENTINEL_BP_9Q", folder=SENTINEL_DIR, parent_class="Pawn"),
        sentinel_checkable=("name", "folder", "parent_class"),
    ),
    ToolEntry(
        "ue_add_component", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL, component_class="PointLightComponent",
                    component_name="SENTINEL_COMP_9Q"),
        sentinel_checkable=("actor_label", "component_class", "component_name"),
    ),
    ToolEntry(
        "ue_set_component_property", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL, component_class="StaticMeshComponent",
                    property_name=SENTINEL_PROP, value="7317.25"),
        sentinel_checkable=("actor_label", "component_class", "property_name", "value"),
        notes="success-branch exec is the bare-`true` trap",
    ),
    ToolEntry(
        "ue_set_blueprint_defaults", CODEGEN,
        kwargs=dict(blueprint_path=SENTINEL_BP_PATH, properties='{"SENTINEL_Prop_9Q": 7317}'),
        sentinel_checkable=("blueprint_path", "properties"),
    ),
    ToolEntry(
        "ue_compile_blueprint", CODEGEN,
        kwargs=dict(blueprint_path=SENTINEL_BP_PATH),
        sentinel_checkable=("blueprint_path",),
    ),
    ToolEntry(
        "ue_get_actor_components", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL),
        sentinel_checkable=("actor_label",),
    ),
    ToolEntry(
        "ue_spawn_blueprint", CODEGEN,
        kwargs=dict(blueprint_path=SENTINEL_BP_PATH, x=7.25, y=8.25, z=9.25,
                    rx=10.25, ry=11.25, rz=12.25, label=SENTINEL_LABEL),
        sentinel_checkable=("blueprint_path", "x", "y", "z", "rx", "ry", "rz", "label"),
        notes="label kwarg exercises the label_line indentation path",
    ),
    # --------------------------------------------------------- perception.py
    ToolEntry(
        "ue_viewport_percept", DIRECT,
        notes="primary path is HTTP to the ViewportPerception plugin (:30011); the Python "
              "fallback codegen (_fallback_capture) IS exec-simulated in "
              "test_honesty::test_viewport_fallback_does_not_claim_success_with_empty_image",
    ),
    ToolEntry(
        "ue_viewport_watch", DIRECT,
        notes="HTTP-only control of the ViewportPerception plugin; no codegen",
    ),
    ToolEntry(
        "ue_viewport_config", DIRECT,
        notes="HTTP-only configuration of the ViewportPerception plugin; no codegen",
    ),
    ToolEntry(
        "ue_viewport_diff", CODEGEN,
        kwargs=dict(delay_ms=100),
        notes="captures two identical snapshot scripts; delay_ms is a host-side sleep, "
              "not embedded in the generated source",
    ),
    # -------------------------------------------------------------- scene.py
    ToolEntry(
        "ue_get_actor_details", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL),
        sentinel_checkable=("actor_label",),
        notes="success-branch exec is the phantom actor.is_hidden() trap",
    ),
    ToolEntry(
        "ue_query_scene", CODEGEN,
        kwargs=dict(tag_filter=SENTINEL_TAG, name_pattern=SENTINEL_LABEL,
                    near_x=101.25, near_y=202.25, near_z=303.25,
                    radius=9999.25, max_results=137),
        sentinel_checkable=("tag_filter", "name_pattern", "near_x", "near_y", "near_z",
                            "radius", "max_results"),
        notes="filters chosen to MATCH the stub world so the append branch executes",
    ),
    ToolEntry(
        "ue_get_component_details", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL, component_name="StaticMeshComponent"),
        sentinel_checkable=("actor_label", "component_name"),
    ),
    ToolEntry(
        "ue_get_actor_hierarchy", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL),
        sentinel_checkable=("actor_label",),
    ),
    # ------------------------------------------------------------ spatial.py
    ToolEntry(
        "ue_ground_trace", CODEGEN,
        kwargs=dict(x=1234.25, y=5678.25, start_z=91011.25),
        sentinel_checkable=("x", "y", "start_z"),
    ),
    ToolEntry(
        "ue_snap_to_ground", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL, align_to_normal=True, z_offset=77.25),
        sentinel_checkable=("actor_label", "z_offset"),
    ),
    ToolEntry(
        "ue_spatial_query", CODEGEN,
        kwargs=dict(mode="nearest", x=101.25, y=202.25, z=303.25, count=17),
        sentinel_checkable=("mode", "x", "y", "z", "count"),
    ),
    ToolEntry(
        "ue_measure", CODEGEN,
        kwargs=dict(mode="distance", actor_a=SENTINEL_LABEL, actor_b=SENTINEL_LABEL_B),
        sentinel_checkable=("mode", "actor_a", "actor_b"),
    ),
    # ----------------------------------------------------------- lighting.py
    ToolEntry(
        "ue_setup_sky_atmosphere", CODEGEN,
        kwargs=dict(sun_elevation=47.25, sun_azimuth=133.25, sun_intensity=6.25,
                    fog=True, fog_density=0.0625, clouds=True),
        sentinel_checkable=("sun_elevation", "sun_azimuth", "sun_intensity", "fog_density"),
        notes="values embedded via json.dumps(settings) injected ahead of _RIG_CODE",
    ),
    ToolEntry(
        "ue_set_time_of_day", CODEGEN,
        kwargs=dict(hour=13.25),
        sentinel_checkable=("hour",),
        notes="hour surfaces literally as settings['_hour']",
    ),
    ToolEntry(
        "ue_list_mood_presets", DIRECT,
        notes="pure server-side preset catalog; never touches UE",
    ),
    ToolEntry(
        "ue_apply_mood_preset", CODEGEN,
        kwargs=dict(name="noir"),
        notes="preset name resolved server-side; only derived preset values are embedded",
    ),
    ToolEntry(
        "ue_blend_mood_presets", CODEGEN,
        kwargs=dict(preset_a="golden_hour", preset_b="noir", t=0.25),
        notes="blend inputs resolved server-side; only interpolated values are embedded",
    ),
    # ---------------------------------------------------------- materials.py
    ToolEntry(
        "ue_create_material_instance", CODEGEN,
        kwargs=dict(name="SENTINEL_MI_9Q", parent_material=SENTINEL_MAT_PATH, folder=SENTINEL_DIR),
        sentinel_checkable=("name", "parent_material", "folder"),
    ),
    ToolEntry(
        "ue_set_material_parameter", CODEGEN,
        kwargs=dict(material_path=SENTINEL_MAT_PATH, param_name="SENTINEL_Param_9Q",
                    value="0.4375", param_type="scalar"),
        sentinel_checkable=("material_path", "param_name", "value"),
    ),
    ToolEntry(
        "ue_get_material_parameters", CODEGEN,
        kwargs=dict(material_path=SENTINEL_MAT_PATH),
        sentinel_checkable=("material_path",),
        notes="exec gate is the json.dumps-on-Name-keys trap",
    ),
    ToolEntry(
        "ue_assign_material", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL, material_path=SENTINEL_MAT_PATH, slot_index=13),
        sentinel_checkable=("actor_label", "material_path", "slot_index"),
    ),
    # ------------------------------------------------------------- editor.py
    ToolEntry(
        "ue_console_command", CODEGEN,
        kwargs=dict(command="stat SENTINEL_9Q"),
        sentinel_checkable=("command",),
    ),
    ToolEntry(
        "ue_undo", DIRECT,
        notes="honest not-implemented: returns an explanatory error without an editor "
              "round-trip (no editor-transaction route in the UE Python API); "
              "contract pinned in test_honesty",
    ),
    ToolEntry(
        "ue_redo", DIRECT,
        notes="honest not-implemented, same contract as ue_undo",
    ),
    ToolEntry(
        "ue_focus_actor", CODEGEN,
        kwargs=dict(actor_label=SENTINEL_LABEL),
        sentinel_checkable=("actor_label",),
        notes="scripted-failure honesty contract (LevelEditorSubsystem absent) in test_honesty",
    ),
    ToolEntry(
        "ue_select_actors", CODEGEN,
        kwargs=dict(actor_labels_json='["SENTINEL_LBL_9Q"]'),
        sentinel_checkable=("actor_labels_json",),
        notes="labels JSON embedded f-string-escaped; sentinel gate accepts the escaped form",
    ),
    # ---------------------------------------------------------- sequencer.py
    ToolEntry(
        "ue_create_level_sequence", CODEGEN,
        kwargs=dict(name="SENTINEL_SEQ_9Q", folder=SENTINEL_DIR),
        sentinel_checkable=("name", "folder"),
    ),
    ToolEntry(
        "ue_play_sequence", CODEGEN,
        kwargs=dict(sequence_path=SENTINEL_SEQ_PATH, start_time=3.25, playback_rate=1.25),
        sentinel_checkable=("sequence_path", "start_time", "playback_rate"),
    ),
    ToolEntry(
        "ue_add_actor_to_sequence", CODEGEN,
        kwargs=dict(sequence_path=SENTINEL_SEQ_PATH, actor_label=SENTINEL_LABEL),
        sentinel_checkable=("sequence_path", "actor_label"),
    ),
    ToolEntry(
        "ue_add_keyframe", CODEGEN,
        kwargs=dict(sequence_path=SENTINEL_SEQ_PATH, actor_label=SENTINEL_LABEL,
                    property_name=SENTINEL_PROP, time_seconds=4.25, value="7317.25"),
        sentinel_checkable=("sequence_path", "actor_label", "property_name",
                            "time_seconds", "value"),
        expect_error=True,
        notes="honest not-implemented report: an error RESULT is the CORRECT behavior",
    ),
]

REGISTRY: dict[str, ToolEntry] = {e.tool_name: e for e in _ENTRIES}
assert len(REGISTRY) == len(_ENTRIES), "duplicate tool_name in registry"

CODEGEN_TOOLS: list[str] = sorted(n for n, e in REGISTRY.items() if e.mode == CODEGEN)
DIRECT_TOOLS: list[str] = sorted(n for n, e in REGISTRY.items() if e.mode == DIRECT)
