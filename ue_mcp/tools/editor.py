"""Editor utility tools for UE5 MCP server.

Console commands, undo/redo, viewport focus, and selection management.
"""

from __future__ import annotations

import json
import logging

from ._validation import (
    sanitize_label, sanitize_object_path, sanitize_console_command,
    escape_for_fstring, make_error,
)

logger = logging.getLogger("ue5-mcp.tools.editor")


def register(server, ue):
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
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_undo",
        description="Undo the last editor action. Equivalent to Ctrl+Z.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def undo() -> str:
        """Undo the last editor transaction."""
        code = """
import unreal, json

try:
    result = unreal.EditorLevelLibrary.editor_undo() if hasattr(unreal.EditorLevelLibrary, 'editor_undo') else unreal.SystemLibrary.transaction_undo()
    print("RESULT:" + json.dumps({"undone": True}))
except Exception as e:
    # Fall back to GEditor undo via Python
    try:
        import unreal
        unreal.EditorLevelLibrary.editor_undo()
        print("RESULT:" + json.dumps({"undone": True}))
    except Exception as e2:
        print("RESULT:" + json.dumps({"error": str(e2)}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_redo",
        description="Redo the last undone editor action. Equivalent to Ctrl+Y.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def redo() -> str:
        """Redo the last undone editor transaction."""
        code = """
import unreal, json

try:
    result = unreal.EditorLevelLibrary.editor_redo() if hasattr(unreal.EditorLevelLibrary, 'editor_redo') else unreal.SystemLibrary.transaction_redo()
    print("RESULT:" + json.dumps({"redone": True}))
except Exception as e:
    try:
        unreal.EditorLevelLibrary.editor_redo()
        print("RESULT:" + json.dumps({"redone": True}))
    except Exception as e2:
        print("RESULT:" + json.dumps({"error": str(e2)}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

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
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{safe_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "Actor not found: {safe_label}"}}))
else:
    # Select the actor and focus
    subsystem.set_selected_level_actors([actor])
    # Use editor utility to focus on selection
    unreal.EditorLevelLibrary.set_selected_level_actors([actor])
    # Trigger viewport focus
    if hasattr(unreal, 'LevelEditorSubsystem'):
        le_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if hasattr(le_sub, 'focus_on_selected_actors'):
            le_sub.focus_on_selected_actors()
    print("RESULT:" + json.dumps({{"focused": "{safe_label}"}}))
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
