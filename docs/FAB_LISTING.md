# FAB Marketplace Listing — UnrealEngine Bridge

Draft storefront copy + the technical fields FAB requires for a code plugin.
The plugin package (icon, `.uplugin` metadata, compiled binaries) is separate;
this is the listing that wraps it.

---

## Product name

**UnrealEngine Bridge — AI Editor Control (Claude / MCP)**

## Tagline (≤ 80 chars)

Let Claude Code drive your editor — the AI abilities Epic's MCP doesn't ship.

## Category

Code Plugins → Editor / Utility

## Price

Suggested: free or low-cost dev tool (the value is the workflow, not the C++).
The Python MCP server is MIT on GitHub; the marketplace product is the
signed, precompiled, one-click editor plugins.

---

## Short description (≤ 160 chars)

Two editor plugins that give Claude Code eyes and hands in Unreal 5.8:
viewport perception + a Remote-Control bridge. Pairs with the open-source MCP server.

## Full description

Unreal Engine 5.8 ships Epic's official **Unreal MCP** for the commodity control
plane — spawn, transform, materials, Blueprints. **UnrealEngine Bridge is the
other half**: the differentiated AI abilities Epic's server deliberately does
not expose.

Install these two editor plugins, run the open-source MCP server, and Claude
Code (or any MCP client) can:

- **See the viewport** — continuous, render-thread GPU-readback capture served
  as perception packets (frame + camera + selection + scene metadata). Single
  frames, continuous watch, and structural before/after diffs. Epic's MCP has
  no viewport capture at all.
- **Run real editor Python** — the full `unreal` API, not a sandboxed
  tool-script runner.
- **Light a scene by mood** — one command sets a coordinated sun + fog + clouds
  + colour-grade package, or blends two looks.
- **Reason about space with surface normals** — ground traces that return the
  hit point, normal, distance, and actor; snap-to-slope placement.
- **Stay honest** — every tool's result is enforced by an exec-simulated test
  suite; tools report real status, never a hard-coded success.

The bridge coexists cleanly with Epic's official MCP: Epic handles the basics,
this handles the rest, and both run against the same editor.

### What you get (the plugins)

| Plugin | What it does |
|---|---|
| **UE Bridge** | In-editor status panel, directory-watch bridge, Remote Control access — the editor-side control surface. |
| **Viewport Perception** | Render-thread viewport capture over a localhost HTTP endpoint — the AI's "eyes." |

### What you also need (disclosed up front — required by FAB)

This is an **editor-integration + AI-tooling** product, not a self-contained
runtime feature. To use it you also need, all free:

- The **UnrealEngine Bridge MCP server** (open-source, MIT) — a Python process
  the AI client launches. `pip install` from the linked GitHub repo.
- An **MCP client** — Claude Code, Claude Desktop, Cursor, etc.
- The engine's built-in **Remote Control** plugin (enable it; ships with UE).

The plugins do nothing at runtime in a packaged game — they are **editor-only
developer tooling**.

---

## Technical details (FAB fields)

- **Code Modules:**
  - `UEBridgeRuntime` (Runtime)
  - `UEBridgeEditor` (Editor)
  - `ViewportPerception` (EditorNoCommandlet)
- **Number of Blueprints:** 0
- **Number of C++ Classes:** ~12 (subsystems, HTTP endpoint, frame producer, pixel bus, types)
- **Network Replicated:** No
- **Supported Development Platforms:** Windows
- **Supported Target Build Platforms:** Windows (Win64) — editor-only
- **Engine Version:** 5.8
- **Documentation:** https://github.com/JosephOIbrahim/UnrealEngine_Bridge#readme
- **Example / setup guide:** README + `docs/EPIC_MCP_MATRIX.md` (what this adds over Epic's MCP)
- **Support:** https://github.com/JosephOIbrahim/UnrealEngine_Bridge/issues

### Important notes for reviewers

- Both plugins are **editor-only** (`Editor` / `EditorNoCommandlet` module
  types); nothing loads in a cooked build.
- Two **localhost** HTTP surfaces (Remote Control `:30010`, Viewport
  Perception `:30011`) — single-operator dev trust model, not for untrusted
  networks. Viewport Perception is opt-in. See `SECURITY.md`.
- No third-party binaries; no external runtime dependencies beyond the
  engine's own Remote Control + (optional) Python Script plugins.

---

## Gallery assets to produce (human step)

FAB needs storefront imagery the package can't carry:

1. **Featured image** 1920×1080 — the two-server architecture diagram + a
   "Claude driving the editor" screenshot.
2. **Screenshots** (≥ 5, 1920×1080): the in-editor UE Bridge panel; a
   perception frame Claude captured; a mood-preset before/after; a
   ground-trace/snap demo; the health-check output showing both servers.
3. **Thumbnail** 512×512 — the plugin icon on the brand background.

The plugin `Icon128.png` (shipped in each plugin's `Resources/`) is the
in-editor browser icon, not the storefront thumbnail.
