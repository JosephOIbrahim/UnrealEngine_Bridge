"""Editor utility tools for UE5 MCP server.

Console commands, undo/redo, viewport focus, and selection management.
"""

from __future__ import annotations

import json
import logging

from ._codegen import find_actor_by_label_snippet
from ._types import MCPServer, UEBridge
from ._validation import (
    escape_for_fstring,
    make_error,
    sanitize_console_command,
    sanitize_label,
)

logger = logging.getLogger("ue5-mcp.tools.editor")


def register(server: MCPServer, ue: UEBridge) -> None:
    @server.tool(
        name="ue_console_command",
        description=(
            "Execute a UE console command and capture output. "
            "Blocked commands: exit, quit, crash, gpf, open, servertravel, killall."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def console_command(command: str) -> str:
        """Execute a UE console command (e.g. 'stat fps', 'show collision')."""
        if err := sanitize_console_command(command):
            return make_error(err)

        safe_cmd = escape_for_fstring(command)
        code = f"""
import unreal, json

try:
    world = unreal.EditorLevelLibrary.get_editor_world()
    result = unreal.SystemLibrary.execute_console_command(world, "{safe_cmd}")
    print("RESULT:" + json.dumps({{"command": "{safe_cmd}", "executed": True}}))
except Exception as e:
    print("RESULT:" + json.dumps({{"error": str(e)}}))
"""
        result = await ue.execute_python(code)

        # Try to parse structured output from known commands
        from ._console_parsers import try_parse_output
        if isinstance(result, dict) and result.get("output"):
            parsed = try_parse_output(command, result["output"])
            if parsed:
                result["structured"] = parsed

        return json.dumps(result, indent=2)

    # The UE Python API exposes no editor-transaction undo/redo route (verified
    # against 5.7; Epic's own 5.8 MCP surface ships none either — see
    # docs/EPIC_MCP_MATRIX.md). These previously probed nonexistent APIs and
    # errored every call; now they say so up front without an editor round-trip.
    @server.tool(
        name="ue_undo",
        description=(
            "Undo the last editor action. NOT IMPLEMENTED: no scriptable "
            "editor-transaction route exists in the UE Python API — returns an "
            "explanatory error. Use Ctrl+Z in the editor."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def undo() -> str:
        """Honest not-implemented: no verified editor-transaction API exists."""
        return make_error(
            "not implemented: the UE Python API exposes no editor-transaction "
            "undo route. Use Ctrl+Z in the editor. Tracked for a verified "
            "console-exec implementation."
        )

    @server.tool(
        name="ue_redo",
        description=(
            "Redo the last undone editor action. NOT IMPLEMENTED: no scriptable "
            "editor-transaction route exists in the UE Python API — returns an "
            "explanatory error. Use Ctrl+Y in the editor."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def redo() -> str:
        """Honest not-implemented: no verified editor-transaction API exists."""
        return make_error(
            "not implemented: the UE Python API exposes no editor-transaction "
            "redo route. Use Ctrl+Y in the editor. Tracked for a verified "
            "console-exec implementation."
        )

    @server.tool(
        name="ue_focus_actor",
        description="Focus the viewport camera on an actor (like pressing F in the editor).",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def focus_actor(actor_label: str) -> str:
        """Focus the viewport on an actor by label."""
        if err := sanitize_label(actor_label, "actor_label"):
            return make_error(err)

        safe_label = escape_for_fstring(actor_label)
        find_block = find_actor_by_label_snippet(f'"{safe_label}"')
        code = f"""
import unreal, json

{find_block}
if actor is None:
    print("RESULT:" + json.dumps({{"error": "Actor not found: {safe_label}"}}))
else:
    subsystem.set_selected_level_actors([actor])
    focused_via = None
    if hasattr(unreal, 'LevelEditorSubsystem'):
        le_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if hasattr(le_sub, 'focus_on_selected_actors'):
            le_sub.focus_on_selected_actors()
            focused_via = "level_editor_subsystem"
    if focused_via is None:
        # 5.7's LevelEditorSubsystem exposes no focus UFUNCTION; the editor
        # console command aligns the active viewport to the selection instead.
        try:
            world = unreal.EditorLevelLibrary.get_editor_world()
            unreal.SystemLibrary.execute_console_command(world, "CAMERA ALIGN ACTIVEVIEWPORT")
            focused_via = "camera_align_console"
        except Exception:
            pass
    if focused_via:
        print("RESULT:" + json.dumps({{"focused": "{safe_label}", "via": focused_via}}))
    else:
        print("RESULT:" + json.dumps({{"error": "No viewport focus method available", "selected": "{safe_label}"}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_select_actors",
        description="Set the editor selection to specified actors by label. Clears previous selection.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def select_actors(actor_labels_json: str) -> str:
        """Select actors by label. actor_labels_json is a JSON array of label strings."""
        try:
            labels = json.loads(actor_labels_json)
            if not isinstance(labels, list):
                return make_error("actor_labels_json must be a JSON array of strings")
        except json.JSONDecodeError as e:
            return make_error(f"Invalid JSON: {e}")

        for lbl in labels:
            if not isinstance(lbl, str):
                return make_error("All labels must be strings")
            if err := sanitize_label(lbl, "label"):
                return make_error(err)

        safe_labels = json.dumps(labels)
        safe_labels_escaped = escape_for_fstring(safe_labels)
        code = f"""
import unreal, json

labels = json.loads('''{safe_labels_escaped}''')
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
selected = []
not_found = []

for label in labels:
    found = False
    for a in actors:
        if a.get_actor_label() == label:
            selected.append(a)
            found = True
            break
    if not found:
        not_found.append(label)

subsystem.set_selected_level_actors(selected)
print("RESULT:" + json.dumps({{
    "selected": [a.get_actor_label() for a in selected],
    "not_found": not_found,
}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
