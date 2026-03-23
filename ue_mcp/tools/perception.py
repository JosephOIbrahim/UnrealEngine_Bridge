"""Viewport perception tools for UE5 MCP server.

Consumes from the ViewportPerception C++ plugin's HTTP endpoint (port 30011).
Falls back to SceneCapture2D via ue_execute_python if the plugin is unavailable.

Tier 3I: Includes bridge state correlation — viewport frames are tagged with
the current game state (question, sync_status) for full situational awareness.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

import httpx

from ._types import MCPServer, UEBridge
from ._validation import make_error

logger = logging.getLogger("ue5-mcp.tools.perception")

PERCEPTION_URL = os.environ.get("UE_PERCEPTION_URL", "http://localhost:30011")
PERCEPTION_TIMEOUT = 5.0
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
    """Fallback: capture via SceneCapture2D + Python in the editor.

    This re-renders the scene (performance cost) but works without the C++ plugin.
    """
    code = f"""
import unreal, json, base64, os, tempfile

# Get viewport info
world = unreal.EditorLevelLibrary.get_editor_world()
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
level_name = world.get_name() if world else "Unknown"

# Get active viewport camera
ecs = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
loc, rot = unreal.Vector(), unreal.Rotator()
try:
    vp = unreal.EditorLevelLibrary
    loc = ecs.get_level_viewport_camera_info()[0] if hasattr(ecs, 'get_level_viewport_camera_info') else unreal.Vector()
    rot = ecs.get_level_viewport_camera_info()[1] if hasattr(ecs, 'get_level_viewport_camera_info') else unreal.Rotator()
except Exception:
    pass

# Selected actors
selected = []
sel = unreal.EditorUtilityLibrary.get_selected_assets() if hasattr(unreal, 'EditorUtilityLibrary') else []
try:
    sel_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors()
    selected = [a.get_actor_label() for a in sel_actors]
except Exception:
    pass

# Capture via screenshot
tmp_dir = tempfile.gettempdir().replace("\\\\", "/")
out_path = tmp_dir + "/ue_perception_capture.{format}"

# Use high-res screenshot
success = False
try:
    unreal.AutomationLibrary.take_high_res_screenshot({width}, {height}, out_path)
    success = True
except Exception:
    pass

if not success:
    # Fallback: use viewport screenshot command
    try:
        cmd = f"HighResShot {width}x{height}"
        unreal.SystemLibrary.execute_console_command(world, cmd)
    except Exception:
        pass

# Read and encode the image if it exists
image_b64 = ""
if os.path.exists(out_path):
    with open(out_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("ascii")
    os.remove(out_path)

result = {{
    "image": image_b64,
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
    "fallback": True
}}
print("RESULT:" + json.dumps(result))
"""
    return await ue.execute_python(code)


def _compute_scene_diff(snap1: dict, snap2: dict) -> dict:
    """Compute structural diff between two scene snapshots."""
    diff: dict = {"changed": False, "changes": []}

    r1 = snap1.get("result") or snap1
    r2 = snap2.get("result") or snap2

    if "error" in r1 or "error" in r2:
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
        dist = sum((a - b) ** 2 for a, b in zip(loc1, loc2)) ** 0.5
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
        cam_dist = sum((a - b) ** 2 for a, b in zip(cam_loc1, cam_loc2)) ** 0.5
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
