# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-02 — the Epic MCP era

> **Version renumbering:** the public line continues from v0.1.1. An internal
> 2.x numbering existed in-repo but was never released; it was retired in this
> release. `pyproject` now reads the single version source
> (`ue_mcp/__version__.py`) via hatchling, and tags must match it.

UE 5.8 ships Epic's official **Unreal MCP** (830 tools across 52 toolsets with
`AllToolsets`). This release repositions the bridge around what Epic does NOT
ship, with every decision grounded in a live probe of the real surface.

### Changed — the retirement flip
- **Tiered tool registry** at the `register_all_tools()` seam. Default profile
  is `core`: **20 tools mounted** (the differentiated layer + `ue_status`/
  `ue_health_check`). `UE_MCP_PROFILE=full` remounts the 36 Epic-covered
  commodity tools; `all` adds the two honest not-implemented slots.
- `ue_health_check` now reports the active profile, mount counts, and Epic
  MCP (`:8000`) reachability.
- `ue_undo`/`ue_redo` return an explicit not-implemented error (no editor
  round-trip): no scriptable editor-transaction route exists in the UE Python
  API, and they previously probed nonexistent APIs on every call.

### Added
- **`docs/EPIC_MCP_MATRIX.md`** — the retirement contract-of-record: verdicts
  for all 58 tools against the probed Epic surface, plus raw captures
  (`docs/epic_mcp/`) and a repeatable prober (`scripts/probe_epic_mcp.py`).
- **Exec-simulating test harness** (`tests/exec_sim/`): a strict fake `unreal`
  module, per-tool sentinel registry, compile/exec/sentinel gates, and
  scripted-failure honesty contracts. Proven red on the pre-fix tree — every
  failure mapped 1:1 to a known bug (see `tests/exec_sim/README.md`).
  **580 tests total** (was 415).
- `tests/test_registry_tiers.py` pins the matrix arithmetic and profile
  semantics; tier/tool drift fails CI in both directions.
- Two-server `.mcp.json` (this bridge over stdio + Epic's server on `:8000`);
  `ModelContextProtocol` + `AllToolsets` staged `Optional: true` in the
  `.uproject` (no-ops on 5.7, self-enables on 5.8).

### Fixed
- **All 11 confirmed bugs** from the 2026-06-11 hand-verified review: the
  level-actor resolver (asset-API misuse in delete/transform), `true`→`True`
  NameError, spawn-blueprint label indent, `load_level` false success,
  `focus_actor` unconditional success, phantom `is_hidden()`, unescaped
  `find_assets` patterns, the cloner arg-discard, the viewport-fallback race,
  material-parameter API-family mixing, and the wheel-killing shim import.
- Adversarial-verification findings fixed pre-merge: a stale-frame regression
  in the perception fallback, wrong ClonerEffector class names for 5.7 (all
  cloner writes are now read-back-verified), a working `CAMERA ALIGN` focus
  route, and `find_assets` escaping moved into the codegen chokepoint.
- `metrics` uptime rounding (coarse-clock test flake).

### Removed
- **The legacy Translators questionnaire runtime**: the game-flow state
  machine entry points, trivia UI, Blueprint relay component, and the
  repo-root runner. The `usd_bridge/` package is parked in-repo, out of the
  ship path.

### Engine & packaging (UE 5.8)
- **Retargeted to UE 5.8** (`EngineAssociation` 5.8; both plugins
  `EngineVersion` 5.8.0). The `ViewportPerception` `FrameProducer` was ported
  for 5.8's changed `OnBackBufferReadyToPresent` signature (`FTextureRHIRef`
  → `ISlateViewportProvider&`) behind a dual-version `#if`, so it still
  compiles against 5.7. Verified: the editor target builds clean on 5.8.
- **Marketplace-ready plugins**: branded 128×128 icons, storefront-grade
  `.uplugin` metadata, explicit `Category` specifiers on every
  Blueprint-exposed property (required for engine-module distribution), and a
  clean `RunUAT BuildPlugin -installed` package. Draft storefront copy in
  `docs/FAB_LISTING.md`. The plugins can now be installed engine-wide and
  picked from Edit → Plugins in any 5.8 project.

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
