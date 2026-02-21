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
