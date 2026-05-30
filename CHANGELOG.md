# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-30

First tagged release. Demo-ready on a maintainer's machine; see **Status** below for what stands between this and a distributable plugin.

### Added
- **Agentic MCP tool surface** — 56 tools across 14 modules exposed to Claude Code over stdio (`ue_mcp/mcp_server.py`):
  - **Perceive**: viewport screenshots + bridge state (`ue_viewport_percept`, `perception`)
  - **Scene**: actor spawn/delete/list, transforms, scene-graph queries, spatial queries (`actors`, `scene`, `spatial`)
  - **Properties**: get/set/list UObject properties (`properties`)
  - **Assets**: load, list, find references (`assets`)
  - **Levels**: level info + load (`level`)
  - **Materials**: material / material-instance / shader-parameter editing (`materials`)
  - **Lighting**: lighting setup and control (`lighting`)
  - **Sequencer**: animation / keyframing integration (`sequencer`)
  - **Motion graphics**: procedural modeling / cloners (`mograph`)
  - **Blueprints**: compile + pin introspection (`blueprints`)
  - **Editor**: editor-context operations (`editor`)
  - **Python**: AST-sandboxed Python execution in the editor (`python_exec`)
- **Editor integration** — toolbar button, Tools-menu entry, and a dockable "UE Bridge" Window tab with a Slate control panel (live status + wired Start/Stop), plus the brand icon registered as a Slate brush.
- **File-based bridge protocol** — atomic USD/JSON state exchange under `~/.translators/` with a JSON fallback path and a 5s heartbeat.
- **Two UE 5.7 plugins** — `UEBridge` (runtime + editor) and `ViewportPerception` (capture), both carrying `EngineVersion 5.7.0`.
- **MIT LICENSE**, consistent across `LICENSE`, `README.md`, and `pyproject.toml`.
- **CI** — GitHub Actions running pytest + ruff on the Python bridge (`.github/workflows/ci.yml`).

### Changed
- Launcher rebranded to the agentic tool and repointed at `UnrealEngine_Bridge.uproject`; the legacy "Translators" game demoted behind an opt-in `-Game` switch.
- Build.bat / target / invocation names reconciled across all three references.
- Plugin descriptor metadata (DocsURL / SupportURL / CreatedBy) repointed to this repo, authored by Joseph Ibrahim.

### Security
- Viewport perception is now **disabled by default** (`ViewportPerception.uplugin` `EnabledByDefault=false`) — opt-in only.
- Remote Control surface shrunk: console-exec disabled by default; Python execution flows through an AST sandbox in the MCP layer.
- Hardened shipped configuration defaults.

### Resilience
- Circuit breaker (CLOSED → OPEN at 5 failures → HALF_OPEN after 30s → CLOSED).
- Connection pooling (10 max / 5 keepalive), 10s adaptive timeout.
- Atomic NTFS-safe file I/O (tempfile + `os.replace`) with msvcrt advisory locking.

### Status

v0.1.0 is **demo-ready on a maintainer's machine — not yet a distribution-ready plugin.** It runs end-to-end against Unreal Engine 5.7 on the maintainer's setup. The shipped trust model is a single trusted operator on a single machine; see [SECURITY.md](SECURITY.md). Before a 1.0, the packaging path (bundling the Python bridge inside the plugin, a portable project configuration, and a C++ plugin build in CI) and additional hardening are still in progress.

Pre-1.0, the public API, the MCP tool surface, and the bridge protocol may change without notice.
