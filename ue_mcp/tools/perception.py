"""Viewport perception tools for UE5 MCP server.

Consumes from the ViewportPerception C++ plugin's HTTP endpoint (port 30011).
Falls back to SceneCapture2D via ue_execute_python if the plugin is unavailable.

Tier 3I: Includes bridge state correlation — viewport frames are tagged with
the current game state (question, sync_status) for full situational awareness.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

import httpx

from ._types import MCPServer, UEBridge

logger = logging.getLogger("ue5-mcp.tools.perception")

PERCEPTION_URL = os.environ.get("UE_PERCEPTION_URL", "http://localhost:30011")
PERCEPTION_TIMEOUT = 5.0
# take_high_res_screenshot completes on a later frame — the fallback polls for
# the file across separate editor round-trips (see _fallback_capture).
FALLBACK_POLL_ATTEMPTS = 10
FALLBACK_POLL_INTERVAL_S = 0.5
BRIDGE_DIR = Path.home() / ".translators"


def _read_bridge_state() -> dict | None:
    """Read current bridge state from bridge_state.usda (non-blocking, best-effort)."""
    state_file = BRIDGE_DIR / "bridge_state.usda"
    heartbeat_file = BRIDGE_DIR / "heartbeat.json"

    result = {
        "bridge_connected": False,
        "sync_status": None,
        "message_type": None,
        "current_question": None,
        "question_index": None,
        "question_total": None,
        "heartbeat_alive": False,
    }

    # Read bridge state
    if state_file.exists():
        try:
            content = state_file.read_text(encoding="utf-8")
            result["bridge_connected"] = True

            sync_match = re.search(r'string sync_status = "([^"]*)"', content)
            type_match = re.search(r'string message_type = "([^"]*)"', content)
            qid_match = re.search(r'string question_id = "([^"]*)"', content)
            idx_match = re.search(r'int index = (\d+)', content)
            total_match = re.search(r'int total = (\d+)', content)
            text_match = re.search(r'string text = "([^"]*)"', content)

            result["sync_status"] = sync_match.group(1) if sync_match else None
            result["message_type"] = type_match.group(1) if type_match else None
            result["current_question"] = qid_match.group(1) if qid_match else None
            result["question_index"] = int(idx_match.group(1)) if idx_match else None
            result["question_total"] = int(total_match.group(1)) if total_match else None
            if text_match and text_match.group(1):
                result["question_text"] = text_match.group(1)[:100]  # Truncate for payload size
        except (OSError, PermissionError):
            pass

    # Check heartbeat
    if heartbeat_file.exists():
        try:
            age = time.time() - heartbeat_file.stat().st_mtime
            result["heartbeat_alive"] = age < 15
            result["heartbeat_age_s"] = round(age, 1)
        except OSError:
            pass

    return result


async def _perception_request(method: str, path: str, body: dict | None = None) -> dict | None:
    """Make an HTTP request to the perception endpoint. Returns None on connection failure."""
    try:
        async with httpx.AsyncClient(base_url=PERCEPTION_URL, timeout=PERCEPTION_TIMEOUT) as client:
            if method == "GET":
                r = await client.get(path)
            else:
                r = await client.put(path, json=body or {})
            r.raise_for_status()
            return r.json()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        return None


async def _fallback_capture(ue, width: int, height: int, format: str) -> dict:
    """Fallback: capture via editor screenshot + Python in the editor.

    take_high_res_screenshot completes on a LATER frame, so the trigger and the
    file read must be separate editor executions — one combined exec always saw
    a missing file and (before the fix) reported success with an empty image.
    """
    trigger_code = f"""
import unreal, json, tempfile, os

world = unreal.EditorLevelLibrary.get_editor_world()
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
level_name = world.get_name() if world else "Unknown"

ecs = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
loc, rot = unreal.Vector(), unreal.Rotator()
try:
    if hasattr(ecs, 'get_level_viewport_camera_info'):
        loc, rot = ecs.get_level_viewport_camera_info()
except Exception:
    pass

selected = []
try:
    selected = [a.get_actor_label() for a in subsystem.get_selected_level_actors()]
except Exception:
    pass

tmp_dir = tempfile.gettempdir().replace("\\\\", "/")
out_path = tmp_dir + "/ue_perception_capture.{format}"

# A stranded file from a previous capture (timeout/read-failure) would be
# returned as THIS capture's frame — remove it before triggering.
try:
    if os.path.exists(out_path):
        os.remove(out_path)
except Exception:
    pass

trigger = "none"
try:
    unreal.AutomationLibrary.take_high_res_screenshot({width}, {height}, out_path)
    trigger = "automation"
except Exception:
    try:
        unreal.SystemLibrary.execute_console_command(world, "HighResShot {width}x{height}")
        trigger = "console"
    except Exception:
        pass

print("RESULT:" + json.dumps({{
    "width": {width},
    "height": {height},
    "format": "{format}",
    "frame_number": 0,
    "timestamp": 0,
    "camera": {{
        "location": [loc.x, loc.y, loc.z] if hasattr(loc, 'x') else [0, 0, 0],
        "rotation": [rot.pitch, rot.yaw, rot.roll] if hasattr(rot, 'pitch') else [0, 0, 0],
        "fov": 90.0
    }},
    "viewport": {{
        "size": [{width}, {height}],
        "type": "LevelEditor"
    }},
    "selection": selected,
    "scene": {{
        "map": level_name,
        "actor_count": len(actors)
    }},
    "timing": {{
        "delta_time": 0,
        "fps": 0
    }},
    "fallback": True,
    "trigger": trigger,
    "out_path": out_path
}}))
"""
    triggered = await ue.execute_python(trigger_code)
    meta = triggered.get("result")
    if triggered.get("error") or not isinstance(meta, dict):
        return triggered

    out_path = meta.pop("out_path", "")
    meta["image"] = ""

    if meta.get("trigger") != "automation" or not out_path:
        # The console-command route writes to the editor's own screenshot dir —
        # we cannot poll for it, so report metadata-only honestly.
        meta["capture_status"] = "untracked_trigger" if meta.get("trigger") == "console" else "trigger_failed"
        return {"output": "", "error": None, "result": meta}

    poll_code = (
        "import os, json\n"
        f'print("RESULT:" + json.dumps({{"exists": os.path.exists("{out_path}")}}))'
    )
    found = False
    for _ in range(FALLBACK_POLL_ATTEMPTS):
        await asyncio.sleep(FALLBACK_POLL_INTERVAL_S)
        chk = await ue.execute_python(poll_code)
        chk_result = chk.get("result")
        if isinstance(chk_result, dict) and chk_result.get("exists"):
            found = True
            break

    if not found:
        meta["capture_status"] = "timeout"
        meta["image_pending_path"] = out_path
        return {"output": "", "error": None, "result": meta}

    read_code = f"""
import json, base64, os
with open("{out_path}", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode("ascii")
os.remove("{out_path}")
print("RESULT:" + json.dumps({{"image": image_b64}}))
"""
    read = await ue.execute_python(read_code)
    read_result = read.get("result")
    if isinstance(read_result, dict) and read_result.get("image"):
        meta["image"] = read_result["image"]
        meta["capture_status"] = "ok"
    else:
        meta["capture_status"] = "read_failed"
    return {"output": "", "error": None, "result": meta}


def _compute_scene_diff(snap1: dict, snap2: dict) -> dict:
    """Compute structural diff between two scene snapshots."""
    diff: dict = {"changed": False, "changes": []}

    r1 = snap1.get("result") or snap1
    r2 = snap2.get("result") or snap2

    # Truthiness, not key-presence: execute_python always returns an "error" key
    # (None on success), so `"error" in r1` is True even when the capture succeeded.
    if r1.get("error") or r2.get("error"):
        return {"error": "Failed to capture one or both snapshots",
                "snap1_error": r1.get("error"), "snap2_error": r2.get("error")}

    # Actor diff
    actors1 = {a["label"]: a for a in r1.get("actors", [])}
    actors2 = {a["label"]: a for a in r2.get("actors", [])}

    added = set(actors2.keys()) - set(actors1.keys())
    removed = set(actors1.keys()) - set(actors2.keys())

    for label in added:
        diff["changes"].append({"type": "actor_added", "label": label, "class": actors2[label].get("class")})
    for label in removed:
        diff["changes"].append({"type": "actor_removed", "label": label, "class": actors1[label].get("class")})

    # Moved actors
    common = set(actors1.keys()) & set(actors2.keys())
    for label in common:
        loc1 = actors1[label].get("location", [0, 0, 0])
        loc2 = actors2[label].get("location", [0, 0, 0])
        dist = sum((a - b) ** 2 for a, b in zip(loc1, loc2, strict=False)) ** 0.5
        if dist > 1.0:  # threshold: 1 unreal unit
            diff["changes"].append({
                "type": "actor_moved", "label": label,
                "from": loc1, "to": loc2, "distance": round(dist, 2),
            })

    # Camera diff
    cam1 = r1.get("camera", {})
    cam2 = r2.get("camera", {})
    if cam1.get("available") and cam2.get("available"):
        cam_loc1 = cam1.get("location", [0, 0, 0])
        cam_loc2 = cam2.get("location", [0, 0, 0])
        cam_dist = sum((a - b) ** 2 for a, b in zip(cam_loc1, cam_loc2, strict=False)) ** 0.5
        if cam_dist > 1.0:
            diff["changes"].append({
                "type": "camera_moved",
                "from": cam_loc1, "to": cam_loc2, "distance": round(cam_dist, 2),
            })

    # Selection diff
    sel1 = set(r1.get("selected", []))
    sel2 = set(r2.get("selected", []))
    if sel1 != sel2:
        diff["changes"].append({
            "type": "selection_changed",
            "previously_selected": sorted(sel1),
            "now_selected": sorted(sel2),
        })

    # Actor count
    count1 = r1.get("actor_count", 0)
    count2 = r2.get("actor_count", 0)
    if count1 != count2:
        diff["changes"].append({
            "type": "actor_count_changed",
            "before": count1, "after": count2,
        })

    diff["changed"] = len(diff["changes"]) > 0
    diff["snapshot_count"] = 2
    return diff


def register(server: MCPServer, ue: UEBridge) -> None:

    @server.tool(
        name="ue_viewport_percept",
        description=(
            "Capture the UE5 editor viewport -- returns the rendered frame as an image "
            "plus camera, selection, and scene metadata. Gives the AI situated visual awareness."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def viewport_percept(
        width: int = 1280,
        height: int = 720,
        format: str = "jpeg",
        include_image: bool = True,
    ) -> str:
        """Capture a single viewport perception packet with correlated game state."""

        # Try the C++ plugin endpoint first
        result = await _perception_request("GET", "/perception/frame")

        if result is None:
            # Plugin not available -- try single-shot endpoint
            result = await _perception_request("PUT", "/perception/single", {
                "width": width,
                "height": height,
                "format": format,
            })

        if result is None:
            # Fall back to Python-based capture
            fallback = await _fallback_capture(ue, width, height, format)
            if fallback.get("error"):
                return json.dumps({
                    "error": "Viewport perception unavailable",
                    "detail": fallback["error"],
                    "hint": "Ensure the ViewportPerception plugin is enabled, or that the editor is running.",
                }, indent=2)
            result = fallback.get("result", fallback)

        if not include_image and isinstance(result, dict):
            result.pop("image", None)

        # Correlate with bridge game state
        if isinstance(result, dict):
            bridge_state = _read_bridge_state()
            if bridge_state:
                result["game_state"] = bridge_state

        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_viewport_watch",
        description=(
            "Start or stop continuous viewport awareness at the specified rate. "
            "When active, the perception system captures frames continuously."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def viewport_watch(
        action: str = "start",
        fps: float = 5.0,
        width: int = 768,
        height: int = 432,
    ) -> str:
        """Start/stop continuous viewport perception."""

        if action == "start":
            result = await _perception_request("PUT", "/perception/start", {
                "fps": fps,
                "width": width,
                "height": height,
            })
            if result is None:
                return json.dumps({
                    "error": f"ViewportPerception plugin not reachable at {PERCEPTION_URL}",
                    "hint": "Continuous capture requires the C++ plugin. Use ue_viewport_percept for single-shot capture.",
                }, indent=2)
            return json.dumps(result, indent=2)

        elif action == "stop":
            result = await _perception_request("PUT", "/perception/stop")
            if result is None:
                return json.dumps({"status": "stopped", "note": "Plugin was not reachable"}, indent=2)
            return json.dumps(result, indent=2)

        return json.dumps({"error": f"Unknown action '{action}'. Use 'start' or 'stop'."}, indent=2)

    @server.tool(
        name="ue_viewport_config",
        description="Configure the viewport perception system (resolution, format, capture rate).",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def viewport_config(
        max_fps: float | None = None,
        width: int | None = None,
        height: int | None = None,
        format: str | None = None,
        quality: int | None = None,
    ) -> str:
        """Configure the perception system. Only provided fields are updated."""

        config = {}
        if max_fps is not None:
            config["max_fps"] = max_fps
        if width is not None:
            config["width"] = width
        if height is not None:
            config["height"] = height
        if format is not None:
            config["format"] = format
        if quality is not None:
            config["quality"] = quality

        if not config:
            # Query current status
            result = await _perception_request("GET", "/perception/status")
            if result is None:
                return json.dumps({"error": "ViewportPerception plugin not reachable"}, indent=2)
            return json.dumps(result, indent=2)

        result = await _perception_request("PUT", "/perception/config", config)
        if result is None:
            return json.dumps({
                "error": f"ViewportPerception plugin not reachable at {PERCEPTION_URL}",
                "hint": "Configuration requires the C++ plugin to be running.",
            }, indent=2)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_viewport_diff",
        description="Capture two viewport snapshots with a delay and return a structural diff showing what changed (actors, camera, selection). Useful for verifying that scene modifications took effect.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def viewport_diff(
        delay_ms: int = 1000,
    ) -> str:
        """Capture two snapshots and compute structural diff."""
        import asyncio

        if delay_ms < 100 or delay_ms > 30000:
            return json.dumps({"error": "delay_ms must be between 100 and 30000"})

        # Capture scene state at two points in time
        scene_code = '''
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()

actor_list = []
for a in actors:
    try:
        loc = a.get_actor_location()
        actor_list.append({
            "label": a.get_actor_label(),
            "class": a.get_class().get_name(),
            "location": [loc.x, loc.y, loc.z],
        })
    except Exception:
        pass

# Camera info
try:
    viewport = unreal.UnrealEditorSubsystem.get_level_viewport_camera_info() if hasattr(unreal, 'UnrealEditorSubsystem') else None
    camera = {"available": False}
    if viewport:
        loc, rot = viewport
        camera = {"location": [loc.x, loc.y, loc.z], "rotation": [rot.pitch, rot.yaw, rot.roll], "available": True}
except Exception:
    camera = {"available": False}

# Selection
try:
    selected = [a.get_actor_label() for a in subsystem.get_selected_level_actors()]
except Exception:
    selected = []

print("RESULT:" + json.dumps({
    "actors": actor_list,
    "camera": camera,
    "selected": selected,
    "actor_count": len(actor_list),
}))
'''
        # First capture
        snap1 = await ue.execute_python(scene_code)

        # Wait
        await asyncio.sleep(delay_ms / 1000.0)

        # Second capture
        snap2 = await ue.execute_python(scene_code)

        # Compute diff
        diff = _compute_scene_diff(snap1, snap2)
        return json.dumps(diff, indent=2)
