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


def register(server, ue):

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
