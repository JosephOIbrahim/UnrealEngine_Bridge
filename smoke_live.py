#!/usr/bin/env python3
"""Live-editor smoke harness for UnrealEngine_Bridge.

Runs representative ue_* tools against a RUNNING UE 5.7 editor (with the bridge
active) and checks the RESULT payloads. This is the test the mocked unit suite
cannot do: it confirms the generated unreal.* Python actually works in the editor
(correct API names), surfaces the lighting applied/skipped property mismatches,
and validates the perception image path end to end.

NOT a pytest test (pytest's testpaths is "tests/", so this file at the repo root
is never collected — it requires a live editor that CI does not have).

Usage:
    1. Open UnrealEngine_Bridge.uproject in UE 5.7 and let it finish loading.
       (For the perception-plugin check, enable the ViewportPerception plugin.)
    2. From the repo root:
         python smoke_live.py             # full run (spawns a temp actor + cleans it up;
                                          #            leaves the idempotent sky rig)
         python smoke_live.py --read-only # no scene mutations

Exit code: number of FAILED checks (0 = all good; 2 = could not reach the editor).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys

import httpx
from mcp.server.fastmcp import FastMCP

from remote_control import BASE_URL, AsyncUnrealRemoteControl
from ue_mcp.tools import register_all_tools

PERCEPTION_URL = "http://localhost:30011"
TEST_LABEL = "UEBridgeSmokeTest"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def unwrap(returned: str):
    """Parse a tool's JSON string into (ok, payload_dict, error).

    Tools either return execute_python's {result, output, error} envelope or a
    flat dict; this normalizes both and surfaces any error at either layer.
    """
    try:
        d = json.loads(returned)
    except Exception as e:  # noqa: BLE001
        return False, {}, f"non-JSON response: {e}"
    if not isinstance(d, dict):
        return True, {"value": d}, None
    inner = d.get("result")
    payload = inner if isinstance(inner, dict) else d
    err = d.get("error") or (payload.get("error") if isinstance(payload, dict) else None)
    return (err is None), (payload if isinstance(payload, dict) else {"value": payload}), err


def sniff_image(b64: str):
    """Validate a base64 image by magic bytes + size. Returns (ok, detail)."""
    try:
        raw = base64.b64decode(b64)
    except Exception as e:  # noqa: BLE001
        return False, f"base64 decode failed: {e}"
    if raw[:4] == b"\x89PNG":
        kind = "PNG"
    elif raw[:3] == b"\xff\xd8\xff":
        kind = "JPEG"
    else:
        return False, f"unknown image magic {raw[:8]!r}"
    if len(raw) < 512:
        return False, f"{kind} suspiciously small ({len(raw)} bytes)"
    return True, f"{kind}, {len(raw)} bytes"


class Smoke:
    def __init__(self):
        self.results: list[tuple[str, str, str]] = []

    def record(self, name: str, status: str, detail: str = ""):
        self.results.append((name, status, detail))
        print(f"  [{status:4}] {name:38} {detail}")

    async def attempt(self, name, coro, *, pass_if=None, detail_fn=None):
        """Await a tool coroutine, unwrap it, record PASS/FAIL. Returns (passed, payload)."""
        try:
            out = await coro
        except Exception as e:  # noqa: BLE001
            self.record(name, "FAIL", f"{type(e).__name__}: {e}")
            return False, {}
        ok, payload, err = unwrap(out)
        passed = pass_if(ok, payload) if pass_if else ok
        detail = (detail_fn(payload) if (passed and detail_fn) else "") or (err or "")
        self.record(name, "PASS" if passed else "FAIL", detail)
        return passed, payload


# --------------------------------------------------------------------------- #
# Perception plugin (:30011) — verifies the async-readback path directly
# --------------------------------------------------------------------------- #

async def check_perception_plugin(s: Smoke):
    name = "perception plugin :30011 (async readback)"
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.put(f"{PERCEPTION_URL}/perception/start",
                            json={"fps": 5, "width": 640, "height": 360})
            if r.status_code >= 400:
                s.record(name, "SKIP", f"start -> {r.status_code} (is the plugin enabled?)")
                return
            await asyncio.sleep(1.2)  # enqueue->drain needs a couple of presents
            r = await c.get(f"{PERCEPTION_URL}/perception/frame")
            try:
                await c.put(f"{PERCEPTION_URL}/perception/stop")
            except Exception:  # noqa: BLE001
                pass
            if r.status_code >= 400:
                s.record(name, "FAIL", f"frame -> HTTP {r.status_code}")
                return
            data = r.json()
            if data.get("image"):
                ok, detail = sniff_image(data["image"])
                s.record(name, "PASS" if ok else "FAIL", detail)
            else:
                s.record(name, "FAIL", data.get("error", "no image in response"))
    except (httpx.ConnectError, httpx.ConnectTimeout):
        s.record(name, "SKIP", "not reachable — enable the ViewportPerception plugin")
    except Exception as e:  # noqa: BLE001
        s.record(name, "SKIP", f"{type(e).__name__}: {e}")


# --------------------------------------------------------------------------- #
# Mutating checks (spawn/snap/lighting) — skipped with --read-only
# --------------------------------------------------------------------------- #

async def mutating_checks(s: Smoke, tool):
    print("\n  -- mutating checks (spawns a temp actor, leaves an idempotent sky rig) --")

    spawned, p = await s.attempt(
        "ue_spawn_actor",
        tool("ue_spawn_actor")(class_name="StaticMeshActor", x=0.0, y=0.0, z=5000.0, label=TEST_LABEL),
        detail_fn=lambda p: f"path={p.get('path') or p.get('actor_path') or p.get('name')}",
    )
    spawned_path = p.get("path") or p.get("actor_path") or p.get("name")

    if spawned:
        await s.attempt(
            "ue_snap_to_ground",
            tool("ue_snap_to_ground")(actor_label=TEST_LABEL),
            detail_fn=lambda p: f"ground_z={p.get('ground_z')}",
        )
        await s.attempt(
            "ue_measure[extent on spawned]",
            tool("ue_measure")(mode="extent", actor_a=TEST_LABEL),
            detail_fn=lambda p: f"size={p.get('size')}",
        )
        if spawned_path:
            await s.attempt(
                "ue_delete_actor (cleanup)",
                tool("ue_delete_actor")(actor_path=spawned_path),
                detail_fn=lambda p: "deleted",
            )
        else:
            s.record("ue_delete_actor (cleanup)", "SKIP",
                     f"no path returned — delete '{TEST_LABEL}' manually")

    # KEY check: applied[] must be non-empty, else the unreal.* property names are wrong.
    def light_pass(ok, p):
        return ok and len(p.get("applied", [])) > 0

    def light_detail(p):
        skipped = p.get("skipped", [])
        d = f"applied={len(p.get('applied', []))} skipped={len(skipped)}"
        return d + (f"  SKIPPED={skipped[:6]}" if skipped else "")

    await s.attempt(
        "ue_setup_sky_atmosphere",
        tool("ue_setup_sky_atmosphere")(sun_elevation=35.0, sun_azimuth=120.0),
        pass_if=light_pass, detail_fn=light_detail,
    )
    await s.attempt(
        "ue_apply_mood_preset[overcast]",
        tool("ue_apply_mood_preset")(name="overcast"),
        pass_if=light_pass, detail_fn=light_detail,
    )


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

async def run(read_only: bool) -> int:
    s = Smoke()
    ue = AsyncUnrealRemoteControl()
    server = FastMCP("uebridge-smoke")
    register_all_tools(server, ue)

    def tool(name):
        return server._tool_manager._tools[name].fn

    print("UnrealEngine_Bridge -- live-editor smoke harness")
    print(f"Remote Control: {BASE_URL}    Perception: {PERCEPTION_URL}")
    print("-" * 64)

    # Connectivity gate
    try:
        connected = await ue.is_connected()
    except Exception:  # noqa: BLE001
        connected = False
    if not connected:
        print(f"\n  Cannot reach UE Remote Control at {BASE_URL}.")
        print("  Open UnrealEngine_Bridge.uproject in UE 5.7, make sure the Remote")
        print("  Control web server is listening, then re-run this harness.")
        await ue.close()
        return 2
    s.record("connectivity (is_connected)", "PASS", BASE_URL)

    try:
        await s.attempt(
            "ue_execute_python",
            tool("ue_execute_python")(code="import unreal, json\nprint('RESULT:' + json.dumps({'pong': True}))"),
            pass_if=lambda ok, p: ok and p.get("pong") is True,
            detail_fn=lambda p: "pong",
        )
        await s.attempt(
            "ue_get_level_info", tool("ue_get_level_info")(),
            detail_fn=lambda p: f"map={p.get('name') or p.get('map', '')}",
        )
        _, scene = await s.attempt(
            "ue_query_scene", tool("ue_query_scene")(),
            detail_fn=lambda p: f"{len(p.get('actors', []))} actors",
        )
        await s.attempt(
            "ue_ground_trace", tool("ue_ground_trace")(x=0.0, y=0.0),
            detail_fn=lambda p: f"hit={p.get('hit')}",
        )
        await s.attempt(
            "ue_spatial_query[combined_bounds]", tool("ue_spatial_query")(mode="combined_bounds"),
            detail_fn=lambda p: f"count={p.get('count')}",
        )

        actors = scene.get("actors", []) if isinstance(scene, dict) else []
        if actors and actors[0].get("label"):
            await s.attempt(
                "ue_measure[extent on existing]",
                tool("ue_measure")(mode="extent", actor_a=actors[0]["label"]),
                detail_fn=lambda p: f"size={p.get('size')}",
            )
        else:
            s.record("ue_measure[extent on existing]", "SKIP", "no labeled actors in scene")

        await s.attempt(
            "ue_list_mood_presets", tool("ue_list_mood_presets")(),
            pass_if=lambda ok, p: ok and p.get("count", 0) > 0,
            detail_fn=lambda p: f"{p.get('count')} presets",
        )

        # Perception via the MCP tool (plugin -> /single -> RC fallback chain)
        async def percept():
            return await tool("ue_viewport_percept")(width=640, height=360, format="jpeg")

        try:
            out = await percept()
            ok, p, err = unwrap(out)
            if ok and p.get("image"):
                img_ok, detail = sniff_image(p["image"])
                s.record("ue_viewport_percept", "PASS" if img_ok else "FAIL", detail)
            else:
                s.record("ue_viewport_percept", "FAIL", err or "no image in response")
        except Exception as e:  # noqa: BLE001
            s.record("ue_viewport_percept", "FAIL", f"{type(e).__name__}: {e}")

        # Perception plugin directly (verifies the async-readback fix)
        await check_perception_plugin(s)

        if read_only:
            s.record("(mutating checks)", "SKIP", "--read-only")
        else:
            await mutating_checks(s, tool)
    finally:
        await ue.close()

    passed = sum(1 for _, st, _ in s.results if st == "PASS")
    failed = sum(1 for _, st, _ in s.results if st == "FAIL")
    skipped = sum(1 for _, st, _ in s.results if st == "SKIP")
    print("-" * 64)
    print(f"  {passed} passed, {failed} failed, {skipped} skipped")
    if failed:
        print("\n  FAILURES:")
        for n, st, d in s.results:
            if st == "FAIL":
                print(f"    - {n}: {d}")
    return failed


def main():
    ap = argparse.ArgumentParser(description="Live-editor smoke harness for UnrealEngine_Bridge.")
    ap.add_argument("--read-only", action="store_true", help="skip scene-mutating checks")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args.read_only)))


if __name__ == "__main__":
    main()
