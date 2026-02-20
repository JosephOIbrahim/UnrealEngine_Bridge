"""Tests for ue_mcp/tools/_validation.py — AST sandbox and input sanitizers."""

import pytest

from ue_mcp.tools._validation import (
    validate_python_code,
    sanitize_label,
    sanitize_class_name,
    sanitize_content_path,
    sanitize_object_path,
    sanitize_property_name,
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
