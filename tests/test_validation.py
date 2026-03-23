"""Tests for ue_mcp/tools/_validation.py — AST sandbox and input sanitizers."""

import pytest

from ue_mcp.tools._validation import (
    validate_python_code,
    sanitize_label,
    sanitize_class_name,
    sanitize_content_path,
    sanitize_object_path,
    sanitize_property_name,
    sanitize_material_value,
    sanitize_console_command,
    sanitize_filename,
    escape_for_fstring,
    make_error,
)


# ── AST sandbox ──────────────────────────────────────────────────────────────

class TestValidatePythonCode:
    """validate_python_code blocks dangerous code and allows safe code."""

    def test_safe_code_allowed(self):
        assert validate_python_code("import unreal\nprint('hello')") is None

    def test_safe_unreal_operations(self):
        code = """
import unreal, json
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
print("RESULT:" + json.dumps({"count": len(actors)}))
"""
        assert validate_python_code(code) is None

    def test_blocks_subprocess(self):
        err = validate_python_code("import subprocess")
        assert err is not None
        assert "subprocess" in err

    def test_blocks_shutil(self):
        err = validate_python_code("import shutil")
        assert err is not None

    def test_blocks_os_system(self):
        err = validate_python_code("import os\nos.system('rm -rf /')")
        assert err is not None

    def test_blocks_os_popen(self):
        err = validate_python_code("import os\nos.popen('whoami')")
        assert err is not None

    def test_blocks_eval(self):
        err = validate_python_code("eval('1+1')")
        assert err is not None

    def test_blocks_exec(self):
        err = validate_python_code("exec('print(1)')")
        assert err is not None

    def test_blocks_dunder_import(self):
        err = validate_python_code("__import__('os')")
        assert err is not None

    def test_blocks_ctypes(self):
        err = validate_python_code("import ctypes")
        assert err is not None

    def test_blocks_socket(self):
        err = validate_python_code("import socket")
        assert err is not None

    def test_blocks_from_import(self):
        err = validate_python_code("from subprocess import run")
        assert err is not None

    def test_allows_json(self):
        assert validate_python_code("import json") is None

    def test_allows_math(self):
        assert validate_python_code("import math") is None

    def test_syntax_error_returns_error(self):
        err = validate_python_code("def foo(")
        assert err is not None


# ── Input sanitizers ─────────────────────────────────────────────────────────

class TestSanitizeLabel:
    def test_valid_label(self):
        assert sanitize_label("MyActor_01") is None

    def test_valid_label_with_spaces(self):
        assert sanitize_label("My Actor") is None

    def test_empty_label(self):
        assert sanitize_label("") is not None

    def test_too_long(self):
        assert sanitize_label("a" * 300) is not None

    def test_semicolon_rejected(self):
        assert sanitize_label("actor;drop") is not None

    def test_backtick_rejected(self):
        assert sanitize_label("actor`test") is not None


class TestSanitizeClassName:
    def test_valid_class(self):
        assert sanitize_class_name("StaticMeshActor") is None

    def test_invalid_starts_with_digit(self):
        assert sanitize_class_name("1BadClass") is not None

    def test_invalid_special_chars(self):
        assert sanitize_class_name("My;Class") is not None

    def test_empty(self):
        assert sanitize_class_name("") is not None


class TestSanitizeContentPath:
    def test_valid_path(self):
        assert sanitize_content_path("/Game/Materials/Chrome") is None

    def test_valid_engine_path(self):
        assert sanitize_content_path("/Engine/BasicShapes/Cube") is None

    def test_traversal_rejected(self):
        assert sanitize_content_path("/Game/../../../etc/passwd") is not None

    def test_no_leading_slash(self):
        assert sanitize_content_path("Game/Materials") is not None

    def test_empty(self):
        assert sanitize_content_path("") is not None


class TestSanitizeObjectPath:
    def test_valid_path(self):
        assert sanitize_object_path("/Game/Maps/Main.Main:PersistentLevel.Cube_1") is None

    def test_traversal_rejected(self):
        assert sanitize_object_path("../../etc/passwd") is not None

    def test_empty(self):
        assert sanitize_object_path("") is not None


class TestSanitizePropertyName:
    def test_valid(self):
        assert sanitize_property_name("RelativeLocation") is None

    def test_valid_with_underscore(self):
        assert sanitize_property_name("base_color_r") is None

    def test_empty(self):
        assert sanitize_property_name("") is not None

    def test_special_chars(self):
        assert sanitize_property_name("prop;name") is not None


class TestMakeError:
    def test_returns_json_string(self):
        import json
        result = json.loads(make_error("test error"))
        assert result["error"] == "test error"


# ── escape_for_fstring ──────────────────────────────────────────────────────

class TestEscapeForFstring:
    def test_escapes_backslash(self):
        assert escape_for_fstring("a\\b") == "a\\\\b"

    def test_escapes_double_quote(self):
        assert escape_for_fstring('a"b') == 'a\\"b'

    def test_escapes_single_quote(self):
        assert escape_for_fstring("a'b") == "a\\'b"

    def test_escapes_newline(self):
        assert escape_for_fstring("a\nb") == "a\\nb"

    def test_plain_string_unchanged(self):
        assert escape_for_fstring("hello_world") == "hello_world"

    def test_combined_escaping(self):
        result = escape_for_fstring('path\\to\n"file"')
        assert "\\\\" in result
        assert "\\n" in result
        assert '\\"' in result


# ── sanitize_console_command ────────────────────────────────────────────────

class TestSanitizeConsoleCommand:
    def test_valid_command(self):
        assert sanitize_console_command("stat fps") is None

    def test_valid_cvar(self):
        assert sanitize_console_command("r.SetRes 1920x1080") is None

    def test_blocks_exit(self):
        assert sanitize_console_command("exit") is not None

    def test_blocks_quit(self):
        assert sanitize_console_command("quit") is not None

    def test_blocks_crash(self):
        assert sanitize_console_command("crash") is not None

    def test_blocks_gpf(self):
        assert sanitize_console_command("gpf") is not None

    def test_blocks_open_with_args(self):
        assert sanitize_console_command("open /Game/Maps/Test") is not None

    def test_blocks_killall(self):
        assert sanitize_console_command("killall") is not None

    def test_case_insensitive(self):
        assert sanitize_console_command("EXIT") is not None

    def test_blocks_special_chars(self):
        assert sanitize_console_command("stat fps; rm -rf /") is not None

    def test_empty(self):
        assert sanitize_console_command("") is not None

    def test_too_long(self):
        assert sanitize_console_command("x" * 513) is not None


# ── sanitize_filename ──────────────────────────────────────────────────────

class TestSanitizeFilename:
    def test_valid_filename(self):
        assert sanitize_filename("MyMaterial_01") is None

    def test_empty(self):
        assert sanitize_filename("") is not None

    def test_too_long(self):
        assert sanitize_filename("x" * 257) is not None

    def test_rejects_forward_slash(self):
        assert sanitize_filename("path/file") is not None

    def test_rejects_backslash(self):
        assert sanitize_filename("path\\file") is not None

    def test_rejects_double_dot(self):
        assert sanitize_filename("..hidden") is not None


# ── sanitize_material_value ───────────────────────────────────────────────

class TestSanitizeMaterialValue:
    # scalar
    def test_scalar_valid_float(self):
        assert sanitize_material_value("0.5", "scalar") is None

    def test_scalar_valid_negative(self):
        assert sanitize_material_value("-1.0", "scalar") is None

    def test_scalar_valid_integer(self):
        assert sanitize_material_value("1", "scalar") is None

    def test_scalar_rejects_non_numeric(self):
        assert sanitize_material_value("abc", "scalar") is not None

    def test_scalar_rejects_empty(self):
        assert sanitize_material_value("", "scalar") is not None

    # vector
    def test_vector_valid_rgb(self):
        assert sanitize_material_value("1.0,0.0,0.0", "vector") is None

    def test_vector_valid_rgba(self):
        assert sanitize_material_value("1.0,0.5,0.0,1.0", "vector") is None

    def test_vector_allows_spaces(self):
        assert sanitize_material_value("1.0, 0.5, 0.0", "vector") is None

    def test_vector_rejects_two_components(self):
        assert sanitize_material_value("1.0,0.0", "vector") is not None

    def test_vector_rejects_five_components(self):
        assert sanitize_material_value("1.0,0.0,0.0,1.0,0.5", "vector") is not None

    def test_vector_rejects_non_numeric_component(self):
        assert sanitize_material_value("1.0,abc,0.0", "vector") is not None

    def test_vector_rejects_empty(self):
        assert sanitize_material_value("", "vector") is not None

    # texture
    def test_texture_valid_path(self):
        assert sanitize_material_value("/Game/Textures/T_Wood", "texture") is None

    def test_texture_rejects_invalid_path(self):
        assert sanitize_material_value("not/valid", "texture") is not None

    def test_texture_rejects_traversal(self):
        assert sanitize_material_value("/Game/../etc/passwd", "texture") is not None


class TestSandboxBypassPrevention:
    """Tests for sandbox bypass vectors that were previously unblocked."""

    def test_getattr_bypass_blocked(self):
        """getattr(os, 'system') should be blocked."""
        code = "import os\ngetattr(os, 'system')('echo pwned')"
        result = validate_python_code(code)
        assert result is not None
        assert "getattr" in result.lower() or "blocked" in result.lower()

    def test_getattr_safe_usage_blocked(self):
        """getattr is blocked even for safe-looking usage (defense in depth)."""
        code = "x = getattr(obj, 'name')"
        result = validate_python_code(code)
        assert result is not None

    def test_importlib_blocked(self):
        """importlib.import_module should be blocked."""
        code = "import importlib\nimportlib.import_module('subprocess')"
        result = validate_python_code(code)
        assert result is not None
        assert "importlib" in result.lower() or "blocked" in result.lower()

    def test_importlib_from_blocked(self):
        """from importlib import import_module should be blocked."""
        code = "from importlib import import_module"
        result = validate_python_code(code)
        assert result is not None

    def test_dunder_subclasses_blocked(self):
        """__subclasses__ access should be blocked."""
        code = "x = object.__subclasses__()"
        result = validate_python_code(code)
        assert result is not None
        assert "__subclasses__" in result

    def test_dunder_globals_blocked(self):
        """__globals__ access should be blocked."""
        code = "x = func.__globals__"
        result = validate_python_code(code)
        assert result is not None
        assert "__globals__" in result

    def test_dunder_mro_blocked(self):
        """__mro__ access should be blocked."""
        code = "x = str.__mro__"
        result = validate_python_code(code)
        assert result is not None

    def test_dunder_builtins_blocked(self):
        """__builtins__ access should be blocked."""
        code = "x = __builtins__.__import__('os')"
        result = validate_python_code(code)
        assert result is not None

    def test_dunder_code_blocked(self):
        """__code__ access should be blocked."""
        code = "x = func.__code__.co_consts"
        result = validate_python_code(code)
        assert result is not None

    def test_dunder_reduce_blocked(self):
        """__reduce__ access should be blocked (pickle exploit vector)."""
        code = "x = obj.__reduce__()"
        result = validate_python_code(code)
        assert result is not None

    def test_safe_dunders_allowed(self):
        """Safe dunders like __init__, __str__, __repr__ should still work."""
        code = "x = obj.__init__()\ny = str.__name__\nz = obj.__class__"
        result = validate_python_code(code)
        assert result is None, f"Safe dunder blocked: {result}"

    def test_safe_dunder_len_allowed(self):
        """__len__ should be allowed."""
        code = "x = obj.__len__()"
        result = validate_python_code(code)
        assert result is None, f"Safe dunder blocked: {result}"

    def test_blocked_attr_without_known_parent(self):
        """Blocked attrs should be caught even without os/shutil/pathlib parent."""
        code = "x.system('dangerous')"
        result = validate_python_code(code)
        assert result is not None
        assert "system" in result.lower()

    def test_chained_dangerous_attr(self):
        """Chained access to dangerous attr should be caught."""
        code = "a.b.c.rmtree('/tmp')"
        result = validate_python_code(code)
        assert result is not None

    def test_unreal_safe_attrs_still_work(self):
        """Normal unreal API calls should still pass."""
        code = """
import unreal
editor = unreal.EditorLevelLibrary
actors = editor.get_all_level_actors()
for a in actors:
    label = a.get_actor_label()
"""
        result = validate_python_code(code)
        assert result is None, f"Unreal API blocked: {result}"
