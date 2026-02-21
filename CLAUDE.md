# CLAUDE.md

This file provides guidance to Claude Code when working with the UnrealEngine_Bridge project.

## Project Overview

**UnrealEngine_Bridge** is an agentic AI bridge connecting Claude Code to Unreal Engine 5.7. It enables AI-driven workflows where Claude can perceive, reason about, and manipulate UE5 scenes through MCP tools, a file-based bridge protocol, and the Remote Control API.

Forked from TranslatorsGame/ue-bridge. The original focused on cognitive profiling game delivery; this fork focuses on **expanding agentic capabilities** -- making Claude a more capable, autonomous collaborator inside Unreal Engine.

## Commands

```bash
# UE5 project
# Open UnrealEngine_Bridge.uproject in UE 5.7 Editor

# Python bridge
python bridge_orchestrator.py          # Start bridge (USD mode, JSON fallback)
python bridge_orchestrator.py --json   # Force JSON mode
python bridge_orchestrator.py --test   # Write test question and exit

# MCP server
pip install -e ".[dev]"               # Install with dev dependencies
python -m ue_mcp.mcp_server           # Start MCP server (stdio)

# Tests
python -m pytest tests/ -v            # All tests
python -m pytest tests/test_usd_bridge.py -v    # USD bridge tests
python -m pytest tests/test_circuit_breaker.py   # Resilience tests
```

## Architecture

```
UnrealEngine_Bridge/
├── Plugins/
│   ├── UEBridge/                    # Core bridge plugin
│   │   └── Source/
│   │       ├── UEBridgeRuntime/     # Ships in builds: subsystem, types, UI, style
│   │       └── UEBridgeEditor/      # Editor-only: file watching, process mgmt
│   └── ViewportPerception/          # Viewport capture + metadata for AI perception
├── Source/
│   └── UnrealEngineBridge/          # Game module (thin relay to plugin)
│       ├── BridgeComponent.*        # Legacy BP-bindable component
│       └── UI/                      # Slate widgets (title, questions, profile)
├── ue_mcp/                          # MCP server for Claude Code
│   ├── mcp_server.py               # FastMCP entry point (stdio)
│   ├── remote_control_bridge.py     # HTTP wrapper for UE5 Remote Control API
│   ├── metrics.py                   # Telemetry + circuit breaker
│   └── tools/                       # 8 tool modules
│       ├── actors.py                # spawn, delete, list, transform, properties
│       ├── properties.py            # get/set/list UObject properties
│       ├── python_exec.py           # Execute Python in UE editor context
│       ├── assets.py                # load, list, find references
│       ├── level.py                 # level info, load level
│       ├── mograph.py               # Motion graphics / procedural modeling
│       ├── blueprints.py            # compile, get pins
│       └── perception.py            # Viewport screenshots + bridge state
├── bridge_orchestrator.py           # Python game flow orchestration
├── usd_bridge.py                    # USD/JSON file I/O, profile generation
├── remote_control_bridge.py         # Standalone RC API wrapper
└── tests/                           # pytest suite
```

### Communication Stack

```
Claude Code  <--MCP (stdio)-->  ue_mcp/mcp_server.py
                                      |
                               HTTP (localhost:30010)
                                      |
                              UE5 Remote Control API
                                      |
                              UE5 Editor / Runtime
```

### File-Based Bridge Protocol

```
Python Backend                    UE5 Plugin (UEBridgeSubsystem)
─────────────────                 ────────────────────────────────
Writes to ~/.translators/   ←→   Polls ~/.translators/ at 10Hz
  bridge_state.usda                 Reads questions, writes answers
  state.json (fallback)             Tracks behavioral signals
  cognitive_profile.usda            Displays UI widgets
  heartbeat.json (5s)
```

## Key Files

| File | Role |
|------|------|
| `Plugins/UEBridge/Source/UEBridgeRuntime/Public/BridgeTypes.h` | All structs, enums, delegates |
| `Plugins/UEBridge/Source/UEBridgeRuntime/Public/UEBridgeSubsystem.h` | Main subsystem (state machine, polling) |
| `Plugins/UEBridge/Source/UEBridgeRuntime/Public/UEBridgeStyle.h` | Slate style system |
| `ue_mcp/tools/*.py` | MCP tool implementations |
| `usd_bridge.py` | USD I/O, checksum, profile generation |
| `bridge_orchestrator.py` | Game flow state machine |

## Agentic Capabilities (Current)

### What Claude Can Do via MCP

| Capability | Tools | Status |
|-----------|-------|--------|
| **Perceive** viewport | `ue_viewport_percept` | Working |
| **Spawn/delete** actors | `spawn_actor`, `delete_actor`, `list_actors` | Working |
| **Transform** actors | `set_transform` | Working |
| **Read/write** properties | `get_property`, `set_property`, `list_properties` | Working |
| **Execute** Python in editor | `ue_execute_python` | Working |
| **Manage** assets | `load_asset`, `list_assets`, `find_references` | Working |
| **Control** levels | `get_level_info`, `load_level` | Working |
| **Compile** Blueprints | `compile_blueprint`, `get_blueprint_pins` | Working |

### Agentic Gaps (Priority Improvements)

These are the capabilities that would make Claude a significantly better UE5 collaborator:

1. **Scene understanding** -- Claude can capture viewport but lacks structured scene graph queries (get all actors of type, spatial queries, hierarchy traversal)
2. **Material/shader editing** -- No tools for creating or modifying materials, Material Instances, or shader parameters
3. **Animation control** -- No Sequencer integration, no ability to play/scrub/keyframe animations
4. **Blueprint graph editing** -- Can compile but can't create/wire nodes programmatically
5. **Build/cook pipeline** -- No tools for packaging, cooking, or build validation
6. **Multi-frame perception** -- Single viewport snapshot; no video/sequence capture or diff-based change detection
7. **Console command execution** -- Limited; needs structured output parsing
8. **Plugin hot-reload** -- Changes to C++ require full editor restart

## Resilience

- **Circuit breaker**: CLOSED -> OPEN (5 failures) -> HALF_OPEN (30s) -> CLOSED
- **Connection pooling**: 10 max, 5 keepalive
- **Adaptive timeout**: 10s default
- **Atomic file I/O**: tempfile + os.replace (NTFS-safe)
- **Advisory locking**: msvcrt on Windows

## What You Can Change Freely

- MCP tool implementations (ue_mcp/tools/)
- Python bridge logic
- Test coverage
- Build configuration
- Bug fixes, performance

## What Requires Discussion

- New MCP tool categories
- Changes to bridge protocol (affects both Python and C++ sides)
- UEBridgeSubsystem state machine changes
- New C++ plugin modules

## Code Patterns

### Adding a New MCP Tool

1. Create `ue_mcp/tools/your_tool.py`
2. Define functions decorated with `@mcp.tool()`
3. Use `AsyncUnrealRemoteControl` for UE5 communication
4. Register in `ue_mcp/mcp_server.py`
5. Add tests in `tests/`

### Remote Control API Pattern

```python
from remote_control_bridge import AsyncUnrealRemoteControl

async with AsyncUnrealRemoteControl() as rc:
    result = await rc.execute_python("unreal.EditorLevelLibrary.get_all_level_actors()")
```

### C++ Subsystem Pattern

```cpp
// Access from anywhere
UUEBridgeSubsystem* Bridge = GetGameInstance()->GetSubsystem<UUEBridgeSubsystem>();
Bridge->OnQuestionReady.AddDynamic(this, &AMyActor::HandleQuestion);
```
