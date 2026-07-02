# UnrealEngine Bridge

[![Release](https://img.shields.io/github/v/release/JosephOIbrahim/UnrealEngine_Bridge?sort=semver)](https://github.com/JosephOIbrahim/UnrealEngine_Bridge/releases/latest)
[![CI](https://github.com/JosephOIbrahim/UnrealEngine_Bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/JosephOIbrahim/UnrealEngine_Bridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Unreal Engine 5.7](https://img.shields.io/badge/Unreal%20Engine-5.7-0a0a14)](https://www.unrealengine.com/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**Give Claude Code full control of Unreal Engine 5.7.** Spawn actors, tweak materials, light scenes, reason about space, capture the viewport, keyframe animations — all through natural language via the [Model Context Protocol](https://modelcontextprotocol.io/).

58 MCP tools (20 mounted by default · commodity tier via `UE_MCP_PROFILE=full`) | 14 tool modules | 570+ tests | Python 3.11+ · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

> **Epic MCP era:** UE 5.8 ships an official [Unreal MCP](docs/EPIC_MCP_MATRIX.md) covering the commodity control plane (830 tools with AllToolsets). This bridge now mounts its **differentiated core** by default — arbitrary editor Python, console exec, lighting moods, ClonerEffector mograph, continuous perception + scene diffing, normal-aware spatial reasoning, resilience — and keeps the 36 Epic-covered tools available behind `UE_MCP_PROFILE=full`. Dispositions: [EPIC_MCP_MATRIX.md](docs/EPIC_MCP_MATRIX.md).

---

## How It Works

```mermaid
graph LR
    subgraph Claude Code
        A[MCP Client]
    end

    subgraph Python
        B[MCP Server<br/><i>FastMCP · stdio</i>]
        B --> C[Tool Modules<br/><i>14 modules · 56 tools</i>]
        C --> D[Remote Control Bridge<br/><i>httpx · circuit breaker</i>]
    end

    subgraph Unreal Engine 5.7
        E[Remote Control API<br/><i>localhost:30010</i>]
        E --> F[Editor Runtime]
        G[ViewportPerception<br/><i>localhost:30011</i>]
        G --> F
    end

    A -- stdio --> B
    D -- HTTP --> E
    C -. viewport capture .-> G

    style A fill:#5CFFDB,color:#05050D
    style B fill:#5CFFDB,color:#05050D
    style C fill:#12121F,color:#fff
    style D fill:#12121F,color:#fff
    style E fill:#FFCC33,color:#05050D
    style F fill:#12121F,color:#fff
    style G fill:#FFCC33,color:#05050D
```

---

## Quick Start

### Prerequisites

| Requirement | Version |
|---|---|
| Unreal Engine | 5.7 |
| Python | 3.11+ |
| Remote Control API plugin | Enabled in UE5 (ships with engine) |

### 1. Clone & Install

```bash
git clone https://github.com/JosephOIbrahim/UnrealEngine_Bridge.git
cd UnrealEngine_Bridge
pip install -e .
```

### 2. Open the UE5 Project

1. Open `UnrealEngine_Bridge.uproject` in Unreal Engine 5.7
2. Verify the **Remote Control API** plugin is enabled (Edit > Plugins)
3. Confirm `localhost:30010` is reachable (check Output Log for "Remote Control Web Server started")

### 3. Connect Claude Code

Add this to your Claude Code MCP configuration (`~/.claude/settings.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "unreal": {
      "command": "python",
      "args": ["-m", "ue_mcp.mcp_server"],
      "cwd": "/path/to/UnrealEngine_Bridge"
    }
  }
}
```

### 4. Start Building

Open Claude Code and try:

> *"Spawn a cube at the origin, make it red, and rotate it 45 degrees"*

Claude will use `ue_spawn_actor`, `ue_create_material`, `ue_assign_material`, and `ue_set_transform` automatically.

---

## MCP Tools Reference

### Actors (6 tools)
| Tool | Description |
|---|---|
| `ue_spawn_actor` | Create an actor by class name with position/rotation |
| `ue_delete_actor` | Remove an actor from the level |
| `ue_list_actors` | List all level actors, optionally filtered by class |
| `ue_set_transform` | Set location, rotation, and/or scale |
| `ue_duplicate_actor` | Clone an actor with an offset |
| `ue_get_actor_bounds` | Get axis-aligned bounding box |

### Scene Understanding (4 tools)
| Tool | Description |
|---|---|
| `ue_get_actor_details` | Full inspection: class, transform, components, tags, parent |
| `ue_query_scene` | Multi-filter search (class, tag, name pattern, spatial proximity) |
| `ue_get_component_details` | Deep component info (mesh assets, materials, light properties) |
| `ue_get_actor_hierarchy` | Recursive parent-child attachment tree |

### Spatial Reasoning (4 tools)
| Tool | Description |
|---|---|
| `ue_ground_trace` | Line-trace down at (x, y) to find the ground — hit point, normal, distance, actor |
| `ue_snap_to_ground` | Drop an actor onto the surface beneath it, optionally tilting to the slope |
| `ue_spatial_query` | Nearest-N, AABB overlap, combined-bounds footprint, or box-contents queries |
| `ue_measure` | Straight-line distance between actors, or extent + footprint area of one |

### Materials (4 tools)
| Tool | Description |
|---|---|
| `ue_create_material_instance` | Create a MaterialInstanceConstant from a parent material |
| `ue_set_material_parameter` | Set scalar, vector, or texture parameters |
| `ue_get_material_parameters` | List all exposed parameters with current values |
| `ue_assign_material` | Apply a material to a specific mesh slot |

### Blueprints (7 tools)
| Tool | Description |
|---|---|
| `ue_create_blueprint` | Create a new Blueprint asset |
| `ue_add_component` | Add a component to a live actor |
| `ue_set_component_property` | Set a property on a component |
| `ue_set_blueprint_defaults` | Override CDO default values |
| `ue_compile_blueprint` | Compile and save a Blueprint |
| `ue_get_actor_components` | List all components on an actor |
| `ue_spawn_blueprint` | Spawn a Blueprint instance into the level |

### Sequencer & Animation (4 tools)
| Tool | Description |
|---|---|
| `ue_create_level_sequence` | Create a new LevelSequence asset |
| `ue_play_sequence` | Play or scrub a sequence at a given time/rate |
| `ue_add_actor_to_sequence` | Bind a level actor to a sequence |
| `ue_add_keyframe` | Add a keyframe for a property at a given time |

### Perception (4 tools)
| Tool | Description |
|---|---|
| `ue_viewport_percept` | Capture the viewport with camera, selection, and scene metadata |
| `ue_viewport_watch` | Start/stop continuous viewport capture |
| `ue_viewport_config` | Configure capture resolution, format, and rate |
| `ue_viewport_diff` | Two-snapshot structural diff (actors, camera, selection changes) |

### Level (4 tools)
| Tool | Description |
|---|---|
| `ue_save_level` | Save the current level |
| `ue_get_level_info` | Get level name and actor count |
| `ue_load_level` | Load a level by content path |
| `ue_get_world_info` | Streaming levels, world settings, game mode |

### Assets (3 tools)
| Tool | Description |
|---|---|
| `ue_find_assets` | Search the Content Browser by pattern and class |
| `ue_create_material` | Create a material with BaseColor/Roughness/Metallic nodes |
| `ue_delete_asset` | Delete an asset from the Content Browser |

### Motion Graphics (3 tools)
| Tool | Description |
|---|---|
| `ue_create_cloner` | ClonerEffector procedural instancing |
| `ue_create_niagara_system` | Spawn a Niagara particle system |
| `ue_create_pcg_graph` | Create a PCG procedural generation volume |

### Lighting & Atmosphere (5 tools)
| Tool | Description |
|---|---|
| `ue_setup_sky_atmosphere` | Build/update the sky rig (sun, sky, fog, clouds, post) idempotently |
| `ue_set_time_of_day` | Map hour 0–24 → sun elevation/azimuth/colour/intensity |
| `ue_list_mood_presets` | List the built-in cinematic mood presets |
| `ue_apply_mood_preset` | Apply a coordinated sun + fog + clouds + colour-grade package |
| `ue_blend_mood_presets` | Interpolate between two presets (t in 0..1) and apply |

### Editor Utilities (5 tools)
| Tool | Description |
|---|---|
| `ue_console_command` | Execute console commands with structured output parsing |
| `ue_undo` / `ue_redo` | Undo or redo the last editor transaction |
| `ue_focus_actor` | Focus the viewport camera on an actor |
| `ue_select_actors` | Set editor selection by label |

### Properties (2 tools)
| Tool | Description |
|---|---|
| `ue_get_property` | Read any UObject property by path |
| `ue_set_property` | Write any UObject property by path |

### Python Execution (1 tool)
| Tool | Description |
|---|---|
| `ue_execute_python` | Run arbitrary Python in the editor (AST-sandboxed) |

---

## Architecture

```mermaid
graph TB
    subgraph "Python Layer"
        MCP["MCP Server<br/><code>ue_mcp/mcp_server.py</code>"]
        Tools["Tool Modules (14)<br/><code>ue_mcp/tools/</code>"]
        RC["Remote Control Bridge<br/><code>remote_control/</code>"]
        Val["Validation & Sandbox<br/><code>_validation.py</code>"]
        Met["Metrics & Circuit Breaker<br/><code>metrics.py</code>"]
        Log["JSON Logger<br/><code>logging.py</code>"]
    end

    subgraph "File Bridge Layer"
        Orch["Bridge Orchestrator<br/><code>bridge_orchestrator.py</code>"]
        USD["USD Bridge<br/><code>usd_bridge/</code>"]
        FS[("~/.translators/<br/>bridge_state.usda<br/>heartbeat.json")]
    end

    subgraph "C++ Plugins (UE5)"
        Sub["UEBridgeSubsystem<br/><i>State machine · polling</i>"]
        Ed["BridgeEditorSubsystem<br/><i>File watching · process mgmt</i>"]
        VP["ViewportPerception<br/><i>GPU readback · ring buffer</i>"]
        RCAPI["Remote Control API<br/><i>REST · port 30010</i>"]
    end

    MCP --> Tools
    Tools --> Val
    Tools --> RC
    RC --> Met
    MCP --> Log
    RC -- "HTTP" --> RCAPI
    RCAPI --> Sub
    Orch --> USD
    USD --> FS
    FS --> Sub
    Sub --> Ed
    VP -- "HTTP :30011" --> Tools

    style MCP fill:#5CFFDB,color:#05050D
    style Tools fill:#5CFFDB,color:#05050D
    style RCAPI fill:#FFCC33,color:#05050D
    style Sub fill:#12121F,color:#fff
    style VP fill:#FFCC33,color:#05050D
```

### Resilience

| Pattern | Detail |
|---|---|
| **Circuit breaker** | CLOSED → OPEN (5 failures) → HALF_OPEN (30s, 1 probe) → CLOSED |
| **Connection pooling** | 10 max connections, 5 keepalive |
| **Timeout** | 10s adaptive default |
| **Atomic file I/O** | `tempfile` + `os.replace` (NTFS-safe) |
| **Python sandbox** | AST-based validation blocking `os`, `subprocess`, `open`, `getattr`, dunders |

### Security

All Python code executed in UE5 is validated through a multi-layer sandbox:

- **Blocked modules**: `os`, `sys`, `subprocess`, `shutil`, `socket`, `pickle`, `importlib`, and 20+ more
- **Blocked builtins**: `exec`, `eval`, `open`, `getattr`, `globals`, `__import__`
- **Blocked attributes**: `system`, `popen`, `rmtree`, `kill`, plus dangerous dunders
- **Path validation**: Content path traversal (`..`) prevention on all inputs
- **Console safety**: Blocked commands (`exit`, `quit`, `crash`) and newline injection prevention

### Network surface & trust model

The bridge talks to the editor over two **localhost** services: the Unreal Remote Control API (`:30010`) and ViewportPerception (`:30011`). They are designed for a **single trusted operator on a single machine** — the developer running Claude Code and the editor on the same workstation — and should not be exposed to untrusted networks. Viewport perception is **opt-in (disabled by default)**.

See **[SECURITY.md](SECURITY.md)** for the full trust model, operator hardening guidance, and how to report a vulnerability.

---

## Project Structure

```
UnrealEngine_Bridge/
├── ue_mcp/                        # MCP server package
│   ├── mcp_server.py              # FastMCP entry point (stdio)
│   ├── metrics.py                 # Telemetry + observability
│   ├── logging.py                 # Structured JSON logging
│   └── tools/                     # 14 tool modules (56 tools)
│       ├── actors.py              # Spawn, delete, list, transform
│       ├── scene.py               # Query, details, hierarchy
│       ├── spatial.py             # Ground trace, snap-to-ground, measure
│       ├── materials.py           # Create, set params, assign
│       ├── lighting.py            # Sky/atmosphere rig, time of day, mood presets
│       ├── blueprints.py          # Create, compile, components
│       ├── sequencer.py           # Animation / Level Sequence
│       ├── perception.py          # Viewport capture + diff
│       ├── editor.py              # Console, undo/redo, focus
│       ├── level.py               # Save, load, world info
│       ├── assets.py              # Find, create, delete
│       ├── mograph.py             # Cloner, Niagara, PCG
│       ├── properties.py          # Get/set UObject properties
│       ├── python_exec.py         # Sandboxed Python execution
│       ├── _validation.py         # Input sanitization + AST sandbox
│       ├── _codegen.py            # Shared code generation snippets
│       ├── _console_parsers.py    # Structured stat output parsers
│       └── _types.py              # Protocol types
│
├── remote_control/                # UE5 HTTP bridge package
│   ├── circuit_breaker.py         # CLOSED/OPEN/HALF_OPEN state machine
│   ├── async_client.py            # AsyncUnrealRemoteControl (MCP)
│   ├── sync_client.py             # UnrealRemoteControl (standalone)
│   ├── codegen.py                 # UE5 Python script generation
│   ├── execution.py               # File-based result polling
│   └── constants.py               # URLs, timeouts, pool config
│
├── usd_bridge/                    # USD file I/O package
│   ├── io.py                      # Atomic writes, locking, paths
│   ├── question.py                # Question read/write
│   ├── transition.py              # State transitions, finales
│   ├── signals.py                 # Behavioral signal extraction
│   ├── profile.py                 # Cognitive profiling + checksums
│   └── validation.py              # Bridge state validation
│
├── Plugins/
│   ├── UEBridge/                  # Core bridge C++ plugin
│   │   ├── UEBridgeRuntime/       # Subsystem, types, UI, style
│   │   └── UEBridgeEditor/        # File watching, process management
│   └── ViewportPerception/        # GPU readback, ring buffer, HTTP endpoint
│
├── bridge_orchestrator.py         # Game flow orchestration
├── remote_control_bridge.py       # Backward-compat shim → remote_control/
├── usd_bridge.py                  # Backward-compat shim → usd_bridge/
├── tests/                         # 415 tests (pytest)
├── pyproject.toml                 # Build config, dependencies, tooling
└── .github/workflows/ci.yml       # CI: Python 3.11/3.12, coverage, lint
```

---

## Development

### Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

### Running with Coverage

```bash
python -m pytest tests/ --cov=ue_mcp --cov=remote_control --cov-report=term-missing
```

### Linting

```bash
pip install ruff
ruff check ue_mcp/ remote_control/ tests/
```

### Adding a New Tool

1. Create `ue_mcp/tools/your_module.py`
2. Define a `register(server: MCPServer, ue: UEBridge) -> None` function
3. Use `@server.tool()` decorators inside `register()`
4. Validate inputs with sanitizers from `_validation.py`
5. Register in `ue_mcp/tools/__init__.py`
6. Add tests in `tests/`

---

## License

Released under the [MIT License](LICENSE) — Copyright (c) 2026 Joseph Ibrahim.
