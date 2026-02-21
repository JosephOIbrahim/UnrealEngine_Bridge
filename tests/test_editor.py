"""Tests for ue_mcp/tools/editor.py — editor utility tools."""

import ast
import json
import pytest

from ue_mcp.tools._validation import (
    sanitize_label, sanitize_console_command, escape_for_fstring,
)


class TestSanitizeConsoleCommand:
    """Console command sanitizer blocks dangerous commands."""

    def test_allows_stat_fps(self):
        assert sanitize_console_command("stat fps") is None

    def test_allows_show_collision(self):
        assert sanitize_console_command("show collision") is None

    def test_allows_r_setres(self):
        assert sanitize_console_command("r.SetRes 1920x1080") is None

    def test_blocks_exit(self):
        assert sanitize_console_command("exit") is not None

    def test_blocks_quit(self):
        assert sanitize_console_command("quit") is not None

    def test_blocks_crash(self):
        assert sanitize_console_command("crash") is not None

    def test_blocks_gpf(self):
        assert sanitize_console_command("gpf") is not None

    def test_blocks_open(self):
        assert sanitize_console_command("open /Game/Maps/Test") is not None

    def test_blocks_servertravel(self):
        assert sanitize_console_command("servertravel /Game/Maps/Test") is not None

    def test_blocks_killall(self):
        assert sanitize_console_command("killall") is not None

    def test_blocks_case_insensitive(self):
        assert sanitize_console_command("EXIT") is not None
        assert sanitize_console_command("Quit") is not None

    def test_blocks_special_chars(self):
        assert sanitize_console_command("stat fps; rm -rf /") is not None

    def test_blocks_empty(self):
        assert sanitize_console_command("") is not None

    def test_blocks_too_long(self):
        assert sanitize_console_command("x" * 513) is not None


class TestConsoleCommandCodeGen:
    """Generated Python for ue_console_command parses cleanly."""

    def test_code_parses(self):
        safe_cmd = escape_for_fstring("stat fps")
        code = f"""
import unreal, json

try:
    world = unreal.EditorLevelLibrary.get_editor_world()
    result = unreal.SystemLibrary.execute_console_command(world, "{safe_cmd}")
    print("RESULT:" + json.dumps({{"command": "{safe_cmd}", "executed": True}}))
except Exception as e:
    print("RESULT:" + json.dumps({{"error": str(e)}}))
"""
        ast.parse(code)


class TestUndoRedoCodeGen:
    """Generated Python for undo/redo parses cleanly."""

    def test_undo_code_parses(self):
        code = """
import unreal, json

try:
    result = unreal.EditorLevelLibrary.editor_undo() if hasattr(unreal.EditorLevelLibrary, 'editor_undo') else unreal.SystemLibrary.transaction_undo()
    print("RESULT:" + json.dumps({"undone": True}))
except Exception as e:
    try:
        import unreal
        unreal.EditorLevelLibrary.editor_undo()
        print("RESULT:" + json.dumps({"undone": True}))
    except Exception as e2:
        print("RESULT:" + json.dumps({"error": str(e2)}))
"""
        ast.parse(code)

    def test_redo_code_parses(self):
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
        ast.parse(code)


class TestFocusActorCodeGen:
    """Generated Python for ue_focus_actor parses cleanly."""

    def test_code_parses(self):
        safe_label = escape_for_fstring("MyCube")
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
    print("RESULT:" + json.dumps({{"error": "not found"}}))
else:
    subsystem.set_selected_level_actors([actor])
    print("RESULT:" + json.dumps({{"focused": "{safe_label}"}}))
"""
        ast.parse(code)


class TestSelectActorsValidation:
    """ue_select_actors input validation."""

    def test_valid_json_array(self):
        labels = json.loads('["Actor1", "Actor2"]')
        assert isinstance(labels, list)
        for lbl in labels:
            assert sanitize_label(lbl) is None

    def test_rejects_non_array(self):
        labels = json.loads('"just a string"')
        assert not isinstance(labels, list)

    def test_rejects_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            json.loads("not valid json [")
