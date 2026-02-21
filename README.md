# UnrealEngine Bridge

**An agentic AI bridge connecting Claude Code to Unreal Engine 5.7.** Claude can perceive, reason about, and manipulate UE5 scenes through MCP tools, a file-based bridge protocol, and the Remote Control API.

Forked from [TranslatorsGame/ue-bridge](https://github.com/JosephOIbrahim/translators-game). This version focuses on expanding agentic capabilities.

## What's Included

| Component | Description |
|-----------|-------------|
| **UEBridge plugin** | Drop-in UE5 plugin with Runtime + Editor modules |
| **ViewportPerception plugin** | Viewport capture with metadata for AI perception |
| **MCP server** | 8 tool modules for Claude Code integration |
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

## MCP Tools

| Tool | Purpose |
|------|---------|
| `spawn_actor` | Create actors in the level |
| `delete_actor` | Remove actors |
| `list_actors` | Query all actors |
| `set_transform` | Position/rotate/scale actors |
| `get_property` / `set_property` | Read/write UObject properties |
| `ue_execute_python` | Run Python in UE editor context |
| `load_asset` / `list_assets` | Asset management |
| `get_level_info` / `load_level` | Level operations |
| `compile_blueprint` | Blueprint compilation |
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
└── tools/                             # Tool modules (8)

bridge_orchestrator.py                 # Game flow orchestration
usd_bridge.py                          # USD I/O + profile generation
tests/                                 # pytest suite
```

## License

Copyright 2026 Joseph Ibrahim. All rights reserved.
