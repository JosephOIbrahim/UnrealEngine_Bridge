# UnrealEngine Bridge

**An agentic AI bridge connecting Claude Code to Unreal Engine 5.7.** Claude can perceive, reason about, and manipulate UE5 scenes through MCP tools, a file-based bridge protocol, and the Remote Control API.

Forked from [TranslatorsGame/ue-bridge](https://github.com/JosephOIbrahim/translators-game). This version focuses on expanding agentic capabilities.

## What's Included

| Component | Description |
|-----------|-------------|
| **UEBridge plugin** | Drop-in UE5 plugin with Runtime + Editor modules |
| **ViewportPerception plugin** | Viewport capture with metadata for AI perception |
| **MCP server** | 11 tool modules (39 tools) for Claude Code integration |
| **Bridge orchestrator** | Python game flow with USD-native file I/O |
| **Behavioral tracking** | Response time, hesitation, burnout detection |

## Quick Start

### 1. UE5 Setup

1. Open `UnrealEngine_Bridge.uproject` in UE 5.7
2. Go to **Edit > Plugins**, search "UE Bridge", enable it
3. Restart the editor
4. Verify Remote Control is active on `localhost:30010`

### 2. Python Setup

```bash
pip install -e ".[dev]"
python bridge_orchestrator.py
```

### 3. MCP Integration

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "ue-bridge": {
      "command": "python",
      "args": ["-m", "ue_mcp.mcp_server"],
      "cwd": "C:/Users/User/UnrealEngine_Bridge"
    }
  }
}
```

## MCP Tools (39)

### Actors (6)
| Tool | Purpose |
|------|---------|
| `ue_spawn_actor` | Create actors in the level |
| `ue_delete_actor` | Remove actors |
| `ue_list_actors` | Query all actors |
| `ue_set_transform` | Position/rotate/scale actors |
| `ue_duplicate_actor` | Duplicate an actor with offset |
| `ue_get_actor_bounds` | Get axis-aligned bounding box |

### Scene Understanding (4)
| Tool | Purpose |
|------|---------|
| `ue_get_actor_details` | Full actor info: class, transform, components, tags, parent |
| `ue_query_scene` | Filtered queries with class, tag, name, and spatial search |
| `ue_get_component_details` | Deep component inspection (mesh, materials, lights) |
| `ue_get_actor_hierarchy` | Parent-child attachment tree (max depth 10) |

### Materials (4)
| Tool | Purpose |
|------|---------|
| `ue_create_material_instance` | Create MaterialInstanceConstant from parent |
| `ue_set_material_parameter` | Set scalar/vector/texture parameters |
| `ue_get_material_parameters` | List all exposed parameters with values |
| `ue_assign_material` | Apply material to actor mesh component |

### Editor Utilities (5)
| Tool | Purpose |
|------|---------|
| `ue_console_command` | Execute console commands (with safety blocklist) |
| `ue_undo` / `ue_redo` | Undo/redo editor actions |
| `ue_focus_actor` | Focus viewport on actor |
| `ue_select_actors` | Set editor selection by label |

### Properties (2)
| Tool | Purpose |
|------|---------|
| `ue_get_property` | Read UObject properties |
| `ue_set_property` | Write UObject properties |

### Assets (3)
| Tool | Purpose |
|------|---------|
| `ue_find_assets` | Search Content Browser |
| `ue_create_material` | Create material with wired BaseColor/Roughness/Metallic nodes |
| `ue_delete_asset` | Delete asset from Content Browser |

### Level (4)
| Tool | Purpose |
|------|---------|
| `ue_save_level` | Save current level |
| `ue_get_level_info` | Level name and actor count |
| `ue_load_level` | Load a level by content path |
| `ue_get_world_info` | Streaming levels, world settings, game mode |

### Blueprints (7)
| Tool | Purpose |
|------|---------|
| `ue_create_blueprint` | Create Blueprint asset |
| `ue_add_component` | Add component to live actor |
| `ue_set_component_property` | Set property on actor component |
| `ue_set_blueprint_defaults` | Set CDO default values |
| `ue_compile_blueprint` | Compile and save Blueprint |
| `ue_get_actor_components` | List components on actor |
| `ue_spawn_blueprint` | Spawn Blueprint instance |

### Motion Graphics (3)
| Tool | Purpose |
|------|---------|
| `ue_create_cloner` | ClonerEffector instancing |
| `ue_create_niagara_system` | Niagara particle system |
| `ue_create_pcg_graph` | PCG procedural volume |

### Perception (1+)
| Tool | Purpose |
|------|---------|
| `ue_viewport_percept` | Viewport screenshot + metadata |

## Architecture

```
Claude Code (MCP client)
    |
    v
MCP Server (stdio) -- ue_mcp/mcp_server.py
    |
    v
HTTP (localhost:30010)
    |
    v
UE5 Remote Control API
    |
    v
UE5 Editor
```

### File-Based Bridge

For game flow (questions/answers), a file-based protocol uses `~/.translators/`:

- `bridge_state.usda` -- USD VariantSets as state machine
- `state.json` / `answer.json` -- JSON fallback
- `cognitive_profile.usda` -- Generated profile
- `heartbeat.json` -- Liveness (5s interval)

The `UUEBridgeSubsystem` polls at 10Hz with adaptive backoff.

## Project Structure

```
Plugins/
├── UEBridge/
│   └── Source/
│       ├── UEBridgeRuntime/           # Subsystem, types, UI widgets, style
│       └── UEBridgeEditor/            # File watching, process management
└── ViewportPerception/                # AI perception layer

Source/UnrealEngineBridge/             # Game module
├── BridgeComponent.*                  # Legacy BP relay
└── UI/                                # Slate widgets

ue_mcp/                                # MCP server
├── mcp_server.py                      # Entry point
├── remote_control_bridge.py           # UE5 HTTP wrapper
└── tools/                             # Tool modules (11, 39 tools)

bridge_orchestrator.py                 # Game flow orchestration
usd_bridge.py                          # USD I/O + profile generation
tests/                                 # pytest suite
```

## License

Copyright 2026 Joseph Ibrahim. All rights reserved.
