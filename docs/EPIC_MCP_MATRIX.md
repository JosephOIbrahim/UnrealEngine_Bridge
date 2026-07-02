# EPIC_MCP_MATRIX.md — Retirement Contract of Record

**UnrealEngine_Bridge `ue_mcp` (58 tools) vs Epic's official Unreal MCP surface (UE 5.8)**

## 1. Provenance

| Field | Value |
|---|---|
| Probe date | 2026-07-02 (live capture) |
| Engine | Unreal Engine 5.8.0 |
| Server | Built-in **Experimental** plugin `ModelContextProtocol` (MCP server only — ships **zero** tools) + `ToolsetRegistry` + **AllToolsets** aggregate plugin enabled |
| Endpoint | `http://127.0.0.1:8000/mcp`, HTTP + SSE, MCP protocol `2025-11-25` |
| Capture files | `docs/epic_mcp/probe_raw_5.8.0_alltoolsets.json` (full surface), `docs/epic_mcp/probe_raw_5.8.0_default.json` (blank-project default), `docs/epic_mcp/programmatic_exec_environment.json` (exec sandbox) |
| Probed surface | **52 toolsets / 830 tools** (authoritative, per the server's own toolset list). The capture's raw parse recorded 55 candidate toolset names; 3 of them — `GetAssetDiscoveryInfo`, `FindNiagaraScripts`, `GetNiagaraScriptDigest` — are description bullets of `NiagaraToolsets.NiagaraToolset_Assets` mis-parsed as toolset names and rejected by `describe_toolset`. All 830 tools live in the 52 real toolsets. |
| Our surface | 58 tools: 56 `@server.tool` registrations across 14 modules in `ue_mcp/tools/`, plus `ue_status` / `ue_health_check` in `ue_mcp/mcp_server.py` |

**How to regenerate**: enable `ModelContextProtocol` + `AllToolsets`, start the editor (console: `ModelContextProtocol.StartServer`), then `python scripts/probe_epic_mcp.py docs/epic_mcp/probe_raw_<ver>.json`. Rerun per engine version and diff.

### Enablement story

- **Blank default** (plugin enabled, nothing else): the only registered toolset is `ToolsetRegistry.AgentSkillToolset` (4 skill-CRUD tools: `CreateSkill`, `UpdateSkill`, `ListSkills`, `GetSkills`). Everything else is opt-in.
- **AllToolsets** plugin enabled: the full probed surface of 52 toolsets / 830 tools. Individual `Toolsets/*` plugins can be enabled piecemeal instead.

### Tool Search Mode (default **ON**)

- With `bEnableToolSearch=true` (default), `tools/list` exposes **only 3 meta-tools** — `list_toolsets`, `describe_toolset`, `call_tool` — and every concrete tool is reached via `call_tool` meta-dispatch. Confirmed in this capture: `tools/list` returned exactly those 3.
- `bEnableToolSearch=false` flips all 830 tools to first-class `tools/list` entries.
- Settings live in `[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]` in `EditorPerProjectUserSettings.ini`: `ServerPortNumber`, `ServerUrlPath`, `bAutoStartServer`, `bEnableToolSearch`. CLI override: `-ModelContextProtocolPort=N`.
- Ergonomics implication used in verdicts below: under search mode, every concrete call pays the `call_tool` dispatch indirection, and **all tool execution is serialized onto the game thread** — multi-call compositions are materially slower than a single purpose-built tool.

### Transport / security facts

- Loopback HTTP+SSE with Origin checking; **no authentication**. Same localhost trust model we disclose in our own SECURITY.md.
- Serial game-thread execution of tool calls.
- **EULA §6(e)**: Epic warns about sending project data to LLMs — adopting this surface means scene/asset data flows to the connected model; flag in project onboarding.

---

## 2. Our-tools disposition table

Naming legend — Epic tools are cited by exact registered name, with these prefixes abbreviated:

| Abbreviation | Full registered prefix |
|---|---|
| `ActorTools.*` | `editor_toolset.toolsets.actor.ActorTools.*` |
| `PrimitiveTools.*` | `editor_toolset.toolsets.primitive.PrimitiveTools.*` |
| `SceneTools.*` | `editor_toolset.toolsets.scene.SceneTools.*` |
| `ObjectTools.*` | `editor_toolset.toolsets.object.ObjectTools.*` |
| `AssetTools.*` | `editor_toolset.toolsets.asset.AssetTools.*` |
| `BlueprintTools.*` | `editor_toolset.toolsets.blueprint.BlueprintTools.*` |
| `MaterialTools.*` | `editor_toolset.toolsets.material.MaterialTools.*` |
| `MaterialInstanceTools.*` | `editor_toolset.toolsets.material_instance.MaterialInstanceTools.*` |
| `StaticMeshTools.*` / `SkeletalMeshTools.*` | `editor_toolset.toolsets.static_mesh.*` / `editor_toolset.toolsets.skeletal_mesh.*` |
| `SequencerTools.*` | `animation_toolset.toolsets.sequencer.SequencerTools.*` |
| `KeyframingTools.*` | `animation_toolset.toolsets.keyframing.SequencerKeyframingTools.*` |
| `EditorApp.*` | `EditorToolset.EditorAppToolset.*` |
| `NiagaraSystem.*` | `NiagaraToolsets.NiagaraToolset_System.*` |
| `PCG.*` | `PCGToolset.PCGToolset.*` |
| `Programmatic.*` | `editor_toolset.toolsets.programmatic.ProgrammaticToolset.*` |

| Module | Our tool | Epic equivalent(s) (probe-verified) | Coverage | Verdict | Notes / reopen condition |
|---|---|---|---|---|---|
| actors.py | `ue_spawn_actor` | `SceneTools.add_to_scene_from_class` (+ `PrimitiveTools.add_cube/add_sphere/add_cylinder/add_cone` for shape components) | FULL | RETIRE | Spawns any Actor class at a transform with optional name. |
| actors.py | `ue_delete_actor` | `SceneTools.remove_from_scene` | FULL | RETIRE | — |
| actors.py | `ue_list_actors` | `SceneTools.find_actors` | FULL | RETIRE | Filters: name substring, `actor_type`, tag, AABB bounds, subtree root. |
| actors.py | `ue_set_transform` | `ActorTools.set_actor_transform` (read side: `ActorTools.get_actor_transform`) | FULL | RETIRE | Epic adds `ActorTools.look_at` we never had. |
| actors.py | `ue_duplicate_actor` | none — whole-probe search: `AssetTools.duplicate` is assets/folders only; no level-actor duplication tool exists | NONE | KEEP | Reopen if Epic adds an actor-duplicate/clipboard tool to SceneTools. |
| actors.py | `ue_get_actor_bounds` | `ActorTools.get_actor_bounds` | FULL | RETIRE | World-space AABB, exact match. |
| assets.py | `ue_find_assets` | `AssetTools.find_assets`; bonus: `SemanticSearchToolset.SemanticSearchToolset.Search` | FULL | RETIRE | Epic side is strictly stronger (semantic + registry search). |
| assets.py | `ue_create_material` | `MaterialTools.create_material` + `MaterialTools.add_expression` + `MaterialTools.connect_to_output` | FULL (composition) | RETIRE | Our base-color/roughness/metallic bootstrap is reproducible; Epic also edits full expression graphs (see §3). |
| assets.py | `ue_delete_asset` | `AssetTools.delete` | FULL | RETIRE | — |
| blueprints.py | `ue_create_blueprint` | `BlueprintTools.create` | FULL | RETIRE | — |
| blueprints.py | `ue_add_component` | `ActorTools.add_component` | FULL | RETIRE | Epic's works on "actor instance or blueprint" — superset of our live-actor-only tool. |
| blueprints.py | `ue_set_component_property` | `ObjectTools.set_properties` | FULL | RETIRE | Component resolved via `ActorTools.get_components`. |
| blueprints.py | `ue_set_blueprint_defaults` | `BlueprintTools.get_default_object` + `ObjectTools.set_properties` | FULL (composition) | RETIRE | Same CDO-write semantics. |
| blueprints.py | `ue_compile_blueprint` | `BlueprintTools.compile_blueprint` | FULL | RETIRE | — |
| blueprints.py | `ue_get_actor_components` | `ActorTools.get_components` | FULL | RETIRE | Supports `component_type` filter. |
| blueprints.py | `ue_spawn_blueprint` | `SceneTools.add_to_scene_from_asset` | FULL | RETIRE | — |
| editor.py | `ue_console_command` | **none** — verified across all 830 tools: only `EditorApp.SearchCVars` (CVar *lookup*, not exec) and `EditorToolset.LogsToolset.SetVerbosity/GetVerbosity`; no general console-command execution exists | NONE | KEEP | Our blocklist-guarded exec + structured output parsing has no Epic counterpart. Reopen if Epic ships an exec tool. |
| editor.py | `ue_undo` | none — no undo/redo/transaction tool in the probe | NONE | KEEP | Honest not-implemented since M1 (no editor-transaction route in the UE Python API either); slot reserved for a verified implementation. |
| editor.py | `ue_redo` | none (same search) | NONE | KEEP | Same as `ue_undo`. |
| editor.py | `ue_focus_actor` | `EditorApp.FocusOnActors` | FULL | RETIRE | Epic caveat: cannot be called while PIE is active. |
| editor.py | `ue_select_actors` | `EditorApp.SelectActors` (read side: `EditorApp.GetSelectedActors`) | FULL | RETIRE | — |
| level.py | `ue_save_level` | `AssetTools.save_assets` (empty list = save all dirty) + `SceneTools.save_actor` (OFPA actors) | FULL | RETIRE | — |
| level.py | `ue_get_level_info` | `SceneTools.get_current_level` + `SceneTools.find_actors` (count client-side) | FULL (composition) | RETIRE | — |
| level.py | `ue_load_level` | `SceneTools.load_level` | FULL | RETIRE | — |
| level.py | `ue_get_world_info` | partial: `ObjectTools.get_properties` on WorldSettings (game mode, settings); **no streaming-levels enumeration tool anywhere in the probe** | PARTIAL | KEEP-PARTIAL | Keep for streaming-level + world-composition reporting; defer game-mode/world-settings reads to `ObjectTools.get_properties`. |
| lighting.py | `ue_setup_sky_atmosphere` | none — whole-probe search for atmosphere/sky/fog/cloud/sun tooling: zero hits. Raw primitives only (`SceneTools.add_to_scene_from_class` + `ObjectTools.set_properties`) | NONE | KEEP | Our find-or-spawn idempotent sky rig is an orchestration Epic doesn't offer. |
| lighting.py | `ue_set_time_of_day` | none (same search) | NONE | KEEP | Sun elevation/azimuth/K-temperature model is ours alone. |
| lighting.py | `ue_list_mood_presets` | none | NONE | KEEP | Preset catalog is our IP. |
| lighting.py | `ue_apply_mood_preset` | none | NONE | KEEP | Coordinated sun+fog+cloud+post-process grade package. |
| lighting.py | `ue_blend_mood_presets` | none | NONE | KEEP | Preset interpolation, no Epic counterpart. |
| materials.py | `ue_create_material_instance` | `MaterialInstanceTools.create` | FULL | RETIRE | — |
| materials.py | `ue_set_material_parameter` | `MaterialInstanceTools.set_scalar_parameter` / `set_vector_parameter` / `set_texture_parameter` (+ `set_static_switch_parameter`, which we lack) | FULL | RETIRE | — |
| materials.py | `ue_get_material_parameters` | `MaterialInstanceTools.list_parameters` (+ `get_scalar_parameter` / `get_vector_parameter` / `get_texture_parameter`) | FULL | RETIRE | — |
| materials.py | `ue_assign_material` | `StaticMeshTools.set_material` / `SkeletalMeshTools.set_material` (asset-level slots, affects all instances) + `ObjectTools.set_properties` on a component's `OverrideMaterials` (per-instance) | PARTIAL | RETIRE | No dedicated per-instance-slot tool, but the two paths jointly cover it. Reopen if `OverrideMaterials` writes via `ObjectTools.set_properties` prove unreliable in practice. |
| mograph.py | `ue_create_cloner` | none — whole-probe search for cloner/effector: zero hits (ClonerEffector plugin has no Epic MCP toolset) | NONE | KEEP | Reopen if a ClonerEffector toolset ships. |
| mograph.py | `ue_create_niagara_system` | `NiagaraSystem.CreateNiagaraSystem` (template-based asset creation) + `SceneTools.add_to_scene_from_asset` (spawn in level) | FULL (composition) | RETIRE | Epic's Niagara surface (56 tools) then goes far deeper — emitters, modules, renderers, stack I/O. |
| mograph.py | `ue_create_pcg_graph` | `PCG.CreateGraph` + `PCG.SpawnGraphInstance` | FULL | RETIRE | Epic adds full node-graph editing + `PCG.ExecuteGraphInstance` (see §3). |
| perception.py | `ue_viewport_percept` | `EditorApp.CaptureViewport` (with world-grid + label annotations) + `EditorApp.GetCameraTransform` + `EditorApp.GetSelectedActors` + `EditorApp.GetVisibleActors` (frustum) | PARTIAL | KEEP-PARTIAL | Epic covers the single-shot capture + metadata bundle; our continuous-watch integration, structural diffing, and game-state correlation are not covered. Defer one-off captures to Epic; keep the correlated-perception path. |
| perception.py | `ue_viewport_watch` | none — no continuous/streaming capture tool in the probe | NONE | KEEP | — |
| perception.py | `ue_viewport_config` | none — configures **our** perception subsystem (resolution/format/rate), which stays | NONE | KEEP | Retire only if the whole perception subsystem retires. |
| perception.py | `ue_viewport_diff` | none — no snapshot-diff tool in the probe | NONE | KEEP | Structural scene-diff verification is a differentiator. |
| properties.py | `ue_get_property` | `ObjectTools.get_properties` (+ `ObjectTools.list_properties`, `ObjectTools.get_class`) | FULL | RETIRE | — |
| properties.py | `ue_set_property` | `ObjectTools.set_properties` (+ `ObjectTools.reset_properties`, which we lack) | FULL | RETIRE | — |
| python_exec.py | `ue_execute_python` | **not equivalent**: `Programmatic.execute_tool_script` is a **sandboxed batch runner** — module allowlist `json/math/datetime/copy/re/time`, **no `unreal` import**, must define `run()->dict`, can only call `execute_tool(tool_name, json_input)` over registered tools (per `Programmatic.get_execution_environment`) | NONE | KEEP | Our arbitrary editor-Python with full `unreal` API access has no Epic counterpart. This is the escape hatch for everything Epic hasn't tooled. |
| scene.py | `ue_get_actor_details` | `SceneTools.find_actors` + `ActorTools.get_actor_transform` + `ActorTools.get_components` + `ActorTools.get_tags` + `ObjectTools.get_properties` | FULL (composition) | RETIRE | ~4 serial calls vs 1, but complete. |
| scene.py | `ue_query_scene` | `SceneTools.find_actors` (name substring, `actor_type`, tag, world-space AABB `bounds`, optional physics `collision_channels`) | PARTIAL | RETIRE | Filtered listing is covered outright. Caveat: `find_actors` returns actor refs only — location-bearing results (incl. sphere refinement of the radius mode) cost O(N) `ActorTools.get_actor_transform` follow-ups under serial dispatch. Reopen if that composition proves too slow in practice. |
| scene.py | `ue_get_component_details` | `ActorTools.get_components` + `ObjectTools.get_properties` (+ `StaticMeshTools.get_material_slots` where relevant) | FULL (composition) | RETIRE | — |
| scene.py | `ue_get_actor_hierarchy` | partial: `SceneTools.find_actors` (`root` = subtree, flat), `ActorTools.get_parent_component`, `ActorTools.get_root_component`, `ActorTools.get_component_actor` | PARTIAL | KEEP-PARTIAL | Epic offers per-hop primitives, no one-shot recursive attachment tree; N-call reconstruction is expensive under serial game-thread + `call_tool` dispatch. Reopen if Epic ships a scene-outliner tree query (its `get_outliner_tree` is Sequencer-only). |
| sequencer.py | `ue_create_level_sequence` | `SequencerTools.create_level_sequence` | FULL | RETIRE | — |
| sequencer.py | `ue_play_sequence` | `SequencerTools.play`, `pause`, `play_to`, `set_playhead_frame`, `set_playback_speed`, `is_playing` | FULL | RETIRE | Epic scrubbing is real playhead control, superior to our rate-0 hack. |
| sequencer.py | `ue_add_actor_to_sequence` | `SequencerTools.add_actors` / `add_actors_by_name` (+ `add_spawnable_from_class`, `add_spawnable_from_instance`) | FULL | RETIRE | — |
| sequencer.py | `ue_add_keyframe` | `SequencerTools.add_track_to_binding` + `SequencerTools.set_property_name_and_path` + `KeyframingTools.add_key_float` / `add_key_bool` / `add_key_integer` / `add_key_string` | FULL | RETIRE | Epic's 140-tool SequencerTools + 22-tool KeyframingTools (curve editor, key baking, defaults) dwarf our 4. |
| spatial.py | `ue_ground_trace` | `SceneTools.trace_world` | PARTIAL | KEEP-PARTIAL | Probe-verified schema: `trace_world` returns **distance only** — no hit point, no surface normal, no hit actor. Our normal + hit-actor payload is required for placement reasoning. Defer plain distance checks to Epic. |
| spatial.py | `ue_snap_to_ground` | none — no snap tool; faithful composition impossible because slope-alignment needs the surface normal `trace_world` doesn't return | NONE | KEEP | Reopen if `trace_world` gains normal/hit-actor output. |
| spatial.py | `ue_spatial_query` | partial: `box_contents` mode ≈ `SceneTools.find_actors` (`bounds`); `nearest` / `overlap` / `combined_bounds` require client-side math over `ActorTools.get_actor_bounds` per actor | PARTIAL | KEEP-PARTIAL | Defer box-contents to `find_actors`; keep nearest/overlap/union modes (O(N) Epic calls otherwise). |
| spatial.py | `ue_measure` | `ActorTools.get_actor_transform` + `ActorTools.get_actor_bounds` (distance/extent arithmetic client-side) | PARTIAL | RETIRE | Pure convenience arithmetic over two probe-verified reads; not worth a legacy tool. |
| mcp_server.py | `ue_status` | none applicable — checks **our** editor/Remote Control reachability, not Epic's server | NONE | KEEP | Bridge self-monitoring; MCP-level ping is not a substitute for RC-API liveness. |
| mcp_server.py | `ue_health_check` | none — reports **our** bridge version, uptime, circuit-breaker state, request metrics | NONE | KEEP | Monitors infrastructure Epic knows nothing about. |

### Verification notes (whole-probe negative searches)

Grounded claims of absence, each from a full-text search over all 830 names + descriptions:

- **General console-command execution**: absent. Only `EditorApp.SearchCVars` (find CVars by name) and `LogsToolset.SetVerbosity`/`GetVerbosity`. `ConfigSettingsToolset` writes settings sections, not console exec.
- **Undo/redo/transactions**: absent.
- **Sky/atmosphere/fog/cloud/sun/time-of-day**: absent.
- **Level-actor duplication**: absent (`AssetTools.duplicate` is content-browser only).
- **Snap-to-ground / surface alignment**: no standalone tool for EXISTING actors, and no surface-normal output anywhere. (A spawn-time `snap_to_ground` argument does exist on `SceneTools.add_to_scene_from_class`/`add_to_scene_from_asset`.)
- **Cloner/Effector**: absent.
- **Continuous viewport capture / snapshot diff**: absent (single-shot `CaptureViewport`/`CaptureEditorImage`/`CaptureAssetImage` only).
- **Arbitrary editor Python**: absent — `Programmatic.execute_tool_script` sandbox confirmed as described in the header.
- **MCPClientToolset**: not present in this capture; not claimed.

---

## 3. Epic-exclusive capabilities (adoption map)

Surfaces we never had — this is what enabling AllToolsets buys beyond parity:

- **Blueprint graph editing** (`BlueprintTools`, 53): full node create/wire/arrange (`create_node`, `connect_pins`, `break_pins`), a **graph DSL** (`read_graph_dsl` / `write_graph_dsl` / `get_graph_dsl_docs`), functions/params/events/dispatchers, variables incl. replication. Closes our #4 agentic gap outright.
- **Material expression graphs** (`MaterialTools`, 22): `add_expression`, `connect_expressions`, `connect_to_output`, `layout_expressions`, `recompile`, `create_function`, `create_parameter_collection`.
- **Animation stack**: `ControlRigTools` (44) + `SequencerControlRigTools` (72, anim layers, control snapping) + `SequencerOutlinerTools` (18, incl. `get_outliner_tree`) + conditions (9) + custom bindings (8) + FBX/anim `import_fbx`/`export_fbx` (6).
- **Niagara deep editing** (56 across 5 toolsets): emitters, modules, renderers, stack input schema/values, compile state, issue fixes.
- **PCG graph authoring** (31): node-level graph editing, `ExecuteGraphInstance`, `DrawSpline` (interactive user-in-the-loop spline capture), `PCGSpatialToolset.RunPCGInstantGraph`.
- **GAS** (14): GameplayCues, AttributeSets, live AbilitySystem inspection.
- **UMG** (23) and **Slate inspection** (14): widget-tree authoring and accessibility-snapshot reading of the live editor UI.
- **Dataflow** (22), **PhysicsAsset** (17), **StaticMesh/SkeletalMesh asset pipelines** (16 + 22: import, LODs, Nanite, collision, sockets, material slots), **Texture** (2).
- **Plugin management** (`PluginToolset`, 17): create/enable plugins, dependency graphs — partially addresses our #8 gap.
- **Editor app control** (`EditorApp`, 21): **PIE start/stop**, camera get/set, screen↔world projection, content-browser navigation, `GetVisibleActors` frustum queries, annotated viewport capture.
- **Logs** (4): session log tail + per-category verbosity.
- **AgentSkills** (4): in-project skill CRUD — the only default-on toolset.
- **Semantic search** (2): embedding search over indexed Content Browser assets.
- **Data assets**: CurveTable (9), DataTable (10), StringTable (8), DataAsset (1), DataRegistry (7).
- **Gameplay frameworks**: StateTree (9), BehaviorTree (7), Conversation graphs (7, read-only), GameFeatures (7), GameplayTags (6), WorldConditions (2).
- **Automation testing** (7) and **ConfigSettings** (8): run automation tests; read/write project settings sections.
- **Programmatic batching** (2): `execute_tool_script` amortizes round-trips across registered tools (sandboxed; not a Python replacement).

---

## 4. Headline numbers

| Metric | Value |
|---|---|
| Epic surface (AllToolsets, UE 5.8.0) | 52 toolsets / **830 tools** |
| Our surface | 14 modules + server / **58 tools** |
| Coverage: FULL (incl. by-composition) | **33** |
| Coverage: PARTIAL | **8** |
| Coverage: NONE | **17** |

### Retirement arithmetic

| Verdict | Count | Tools |
|---|---|---|
| **RETIRE** (behind legacy flag) | **36** | all of actors.py except `ue_duplicate_actor` (5); all assets.py (3); all blueprints.py (7); `ue_focus_actor`, `ue_select_actors` (2); level.py except `ue_get_world_info` (3); all materials.py (4); mograph niagara+pcg (2); both properties.py (2); scene.py except `ue_get_actor_hierarchy` (3); all sequencer.py (4); `ue_measure` (1) |
| **KEEP-PARTIAL** | **5** | `ue_get_world_info`, `ue_viewport_percept`, `ue_get_actor_hierarchy`, `ue_ground_trace`, `ue_spatial_query` |
| **KEEP** | **17** | `ue_duplicate_actor`; `ue_console_command`, `ue_undo`, `ue_redo`; all 5 lighting.py; `ue_create_cloner`; `ue_viewport_watch`, `ue_viewport_config`, `ue_viewport_diff`; `ue_execute_python`; `ue_snap_to_ground`; `ue_status`, `ue_health_check` |

**Bottom line**: 36 of 58 tools (62%) retire behind the legacy flag. What survives is exactly our differentiated surface: arbitrary editor Python, guarded console exec, the undo/redo capability slots, the lighting/mood orchestration layer, ClonerEffector mograph, continuous perception with structural diffing, normal-aware spatial reasoning, and bridge self-monitoring — plus five partial keeps whose reopen conditions are written into their rows.
