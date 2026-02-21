# UnrealEngine_Bridge v2.1.0 — Inventory

MCP server bridging Claude Code to Unreal Engine 5 via Remote Control API.

## Summary

| Metric | Count |
|--------|-------|
| MCP Tools | 43 |
| Tool Modules | 11 |
| Tests | 222 |
| Python source files | 27 |
| Total lines (Python) | ~8,000 |

## Dependencies

- **Runtime**: `mcp >=1.0,<2.0`, `httpx >=0.27,<1.0`
- **Optional**: `usd-core >=24.0`
- **Dev**: `pytest >=8.0`, `pytest-asyncio >=0.23`
- **Entry point**: `ue-mcp = ue_mcp.mcp_server:main`

---

## Tools (43 total)

### actors.py — Actor Manipulation (6 tools, 216 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_spawn_actor` | `class_name="StaticMeshActor"`, `x/y/z=0.0`, `rx/ry/rz=0.0`, `label=None` | `ue.spawn_actor()` |
| `ue_delete_actor` | `actor_path` | `ue.delete_actor()` |
| `ue_list_actors` | `class_filter=None` | `ue.list_actors()` |
| `ue_set_transform` | `actor_path`, `x/y/z=None`, `rx/ry/rz=None`, `sx/sy/sz=None` | `ue.set_actor_transform()` |
| `ue_duplicate_actor` | `actor_label`, `offset_x=200.0`, `offset_y/z=0.0` | `ue.execute_python()` |
| `ue_get_actor_bounds` | `actor_label` | `ue.execute_python()` |

### properties.py — Property Access (2 tools, 54 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_get_property` | `object_path`, `property_name` | `ue.get_property()` |
| `ue_set_property` | `object_path`, `property_name`, `value` | `ue.set_property()` |

### python_exec.py — Sandboxed Python (1 tool, 60 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_execute_python` | `code` | `ue.execute_python()` (AST-validated) |

### assets.py — Asset Management (3 tools, 122 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_find_assets` | `search_pattern`, `class_filter=None` | `ue.find_assets()` |
| `ue_create_material` | `name`, `base_color_r/g/b=0.8`, `roughness=0.5`, `metallic=0.0` | `ue.execute_python()` |
| `ue_delete_asset` | `asset_path` | `ue.execute_python()` |

### level.py — Level Management (4 tools, 122 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_save_level` | *(none)* | `ue.save_level()` |
| `ue_get_level_info` | *(none)* | `ue.get_level_info()` |
| `ue_load_level` | `level_path` | `ue.execute_python()` |
| `ue_get_world_info` | *(none)* | `ue.execute_python()` |

### mograph.py — Motion Graphics (3 tools, 196 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_create_cloner` | `layout="Grid"`, `mesh_path`, `count_x/y/z`, `spacing=200.0`, `x/y/z=0.0`, `label=None` | `ue.execute_python()` |
| `ue_create_niagara_system` | `system_asset=None`, `x/y/z=0.0`, `label=None` | `ue.execute_python()` |
| `ue_create_pcg_graph` | `x/y/z=0.0`, `extent_x/y=1000.0`, `extent_z=500.0`, `label=None` | `ue.execute_python()` |

### blueprints.py — Blueprints & Components (7 tools, 391 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_create_blueprint` | `name`, `folder="/Game/Blueprints"`, `parent_class="Actor"` | `ue.execute_python()` |
| `ue_add_component` | `actor_label`, `component_class`, `component_name=None` | `ue.execute_python()` |
| `ue_set_component_property` | `actor_label`, `component_class`, `property_name`, `value` | `ue.execute_python()` |
| `ue_set_blueprint_defaults` | `blueprint_path`, `properties` (JSON) | `ue.execute_python()` |
| `ue_compile_blueprint` | `blueprint_path` | `ue.execute_python()` |
| `ue_get_actor_components` | `actor_label` | `ue.execute_python()` |
| `ue_spawn_blueprint` | `blueprint_path`, `x/y/z=0.0`, `rx/ry/rz=0.0`, `label=None` | `ue.execute_python()` |

### perception.py — Viewport Capture (3 tools, 323 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_viewport_percept` | `width=1280`, `height=720`, `format="jpeg"`, `include_image=True` | HTTP `:30011` / fallback `execute_python()` |
| `ue_viewport_watch` | `action="start"`, `fps=5.0`, `width=768`, `height=432` | HTTP `:30011` |
| `ue_viewport_config` | `max_fps=None`, `width/height=None`, `format=None`, `quality=None` | HTTP `:30011` |

### scene.py — Scene Understanding (4 tools, 317 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_get_actor_details` | `actor_label` | `ue.execute_python()` |
| `ue_query_scene` | `class_filter=None`, `tag_filter=None`, `name_pattern=None`, `near_x/y/z=None`, `radius=1000.0`, `max_results=100` | `ue.execute_python()` |
| `ue_get_component_details` | `actor_label`, `component_name` | `ue.execute_python()` |
| `ue_get_actor_hierarchy` | `actor_label` | `ue.execute_python()` |

### materials.py — Material Editing (5 tools, 265 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_create_material_instance` | `name`, `parent_material`, `folder="/Game/Materials"` | `ue.execute_python()` |
| `ue_set_material_parameter` | `material_path`, `param_name`, `value`, `param_type="scalar"` | `ue.execute_python()` |
| `ue_get_material_parameters` | `material_path` | `ue.execute_python()` |
| `ue_assign_material` | `actor_label`, `material_path`, `slot_index=0` | `ue.execute_python()` |

### editor.py — Editor Utilities (5 tools, 202 lines)

| Tool | Params | Dispatch |
|------|--------|----------|
| `ue_console_command` | `command` | `ue.execute_python()` |
| `ue_undo` | *(none)* | `ue.execute_python()` |
| `ue_redo` | *(none)* | `ue.execute_python()` |
| `ue_focus_actor` | `actor_label` | `ue.execute_python()` |
| `ue_select_actors` | `actor_labels_json` (JSON array) | `ue.execute_python()` |

---

## Dispatch Breakdown

| Method | Tool Count | Description |
|--------|-----------|-------------|
| `ue.execute_python()` | 30 | Generate UE5 Python, send via Remote Control API |
| Named `ue.*` methods | 10 | Direct bridge methods (spawn, delete, list, transform, property, find, save, level_info) |
| HTTP `:30011` | 3 | ViewportPerception plugin (perception tools) |

---

## Core Modules

| File | Lines | Purpose |
|------|-------|---------|
| `ue_mcp/mcp_server.py` | 174 | FastMCP server setup, tool registration, startup |
| `remote_control_bridge.py` | 706 | `AsyncUnrealRemoteControl` + `CircuitBreaker` |
| `usd_bridge.py` | 1,462 | USD-based bridge (USDA read/write, VariantSets, atomic file ops) |
| `bridge_orchestrator.py` | 892 | 8-question cognitive profiling questionnaire driver |
| `ue_mcp/tools/_validation.py` | 239 | Input sanitizers, AST sandbox, f-string escaping |
| `ue_mcp/metrics.py` | 68 | Thread-safe counters + rolling latency (p95) |

### Resilience (in remote_control_bridge.py)

- **Circuit Breaker**: CLOSED -> OPEN (5 failures) -> HALF_OPEN (30s recovery)
- **Connection pooling**: 10 max connections, 5 keepalive
- **Result polling**: 0.2s interval, 10s timeout
- **Metrics**: request count, success/error rates, latency p95

### Security (_validation.py)

**Blocked Python imports**: subprocess, shutil, socket, http.server, xmlrpc, ctypes, multiprocessing, signal, pty, pipes, webbrowser, tkinter, smtplib, ftplib, telnetlib, poplib, imaplib, nntplib

**Blocked attributes**: system, popen, exec, eval, execfile, spawn, startfile, rmtree, rmdir, remove, unlink, rename, replace, makedirs, chown, chmod, kill

**Blocked console commands**: exit, quit, crash, gpf, open, servertravel, killall, restartlevel

---

## Tests (222 total)

| File | Tests | Coverage |
|------|-------|----------|
| `test_validation.py` | 62 | Sanitizers, AST sandbox, f-string escaping |
| `test_editor.py` | 36 | Console cmd validation, code gen, async integration |
| `test_materials.py` | 27 | Material instance/param validation, code gen, async |
| `test_usd_bridge.py` | 27 | USD bridge USDA read/write, VariantSets |
| `test_scene.py` | 22 | Scene query validation, code gen, async |
| `test_actors_async.py` | 17 | Actor tools async integration (spawn, delete, list, transform, dup, bounds) |
| `test_assets_async.py` | 10 | Asset tools async (find, create material, delete) |
| `test_circuit_breaker.py` | 8 | Circuit breaker state transitions |
| `test_level_async.py` | 7 | Level tools async (save, info, load, world info) |
| `test_metrics.py` | 6 | Counter, latency, snapshot |

**Test types**:
- Sync validation (sanitizer accept/reject): 62 tests
- Sync code gen (ast.parse on generated Python): ~22 tests
- Async integration (FastMCP + mock_ue): 76 tests
- Infrastructure (circuit breaker, metrics, USD bridge): 62 tests

---

## File Tree

```
UnrealEngine_Bridge/
├── ue_mcp/                      # MCP server package
│   ├── __init__.py
│   ├── __version__.py           # "2.1.0"
│   ├── mcp_server.py            # FastMCP server + entry point
│   ├── metrics.py               # Counters + latency tracking
│   └── tools/                   # 11 tool modules
│       ├── __init__.py          # register_all_tools()
│       ├── _validation.py       # Sanitizers + AST sandbox
│       ├── actors.py
│       ├── assets.py
│       ├── blueprints.py
│       ├── editor.py
│       ├── level.py
│       ├── materials.py
│       ├── mograph.py
│       ├── perception.py
│       ├── properties.py
│       ├── python_exec.py
│       └── scene.py
├── tests/                       # 222 tests
│   ├── conftest.py              # mock_ue fixture
│   ├── test_actors_async.py
│   ├── test_assets_async.py
│   ├── test_circuit_breaker.py
│   ├── test_editor.py
│   ├── test_level_async.py
│   ├── test_materials.py
│   ├── test_metrics.py
│   ├── test_scene.py
│   ├── test_usd_bridge.py
│   └── test_validation.py
├── remote_control_bridge.py     # AsyncUnrealRemoteControl + CircuitBreaker
├── usd_bridge.py                # USD-based bridge (pxr or text fallback)
├── bridge_orchestrator.py       # 8-question profiling questionnaire
├── pyproject.toml               # Package config
├── CLAUDE.md                    # AI assistant instructions
├── README.md                    # Project overview
├── README_BRIDGE_IMPLEMENTATION.md
├── SETUP_GUIDE.md
├── Build.bat                    # UE project build
├── Launch-UEBridge.ps1          # PowerShell launcher
├── UnrealEngine_Bridge.uproject # UE5 project file
├── Content/Python/              # UE5 editor scripts
│   ├── setup_ue_bridge_ui.py
│   └── test_claude_access.py
├── test_bridge_roundtrip.py     # Manual roundtrip test
└── test_live.py                 # Live editor integration test
```

## Known Issues

None currently tracked.
