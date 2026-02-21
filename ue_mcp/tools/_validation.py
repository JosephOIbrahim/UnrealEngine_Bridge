"""Input validation and security helpers for UE5 MCP tools.

Provides:
- AST-based Python code sandboxing for execute_python
- String sanitization for actor labels, class names, paths
- Path validation for UE content paths and blueprint paths
- Console command sanitization
- f-string escaping for code generation
"""

from __future__ import annotations

import ast
import re
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# PYTHON CODE SANDBOX
# ═══════════════════════════════════════════════════════════════════════════════

# Modules that must never be imported in editor Python
BLOCKED_MODULES = frozenset({
    "subprocess", "shutil", "socket", "http.server", "xmlrpc",
    "ctypes", "multiprocessing", "signal", "pty", "pipes",
    "webbrowser", "antigravity", "turtle", "tkinter",
    "smtplib", "ftplib", "telnetlib", "poplib", "imaplib",
    "nntplib", "xmlrpc.server",
})

# Attribute accesses that are dangerous even on allowed modules
BLOCKED_ATTRS = frozenset({
    "system",       # os.system
    "popen",        # os.popen
    "exec",         # builtins.exec (as attr)
    "eval",         # builtins.eval (as attr)
    "execfile",
    "spawn",        # os.spawn*
    "startfile",    # os.startfile
    "rmtree",       # shutil.rmtree
    "rmdir",        # os.rmdir
    "remove",       # os.remove
    "unlink",       # os.unlink / Path.unlink
    "rename",       # os.rename
    "replace",      # os.replace
    "makedirs",     # os.makedirs (outside project)
    "chown",
    "chmod",
    "kill",         # os.kill
})

# Functions that must never appear as Call targets
BLOCKED_BUILTINS = frozenset({
    "exec", "eval", "compile", "__import__", "breakpoint",
})


class CodeValidationError(Exception):
    """Raised when submitted code fails sandbox validation."""
    pass


def validate_python_code(code: str) -> Optional[str]:
    """Validate Python code for safety before execution in UE5.

    Returns None if safe, or an error message string if blocked.
    """
    # Parse the AST — syntax errors are caught here
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error: {e.msg} (line {e.lineno})"

    for node in ast.walk(tree):
        # Block dangerous imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_root = alias.name.split(".")[0]
                if alias.name in BLOCKED_MODULES or mod_root in BLOCKED_MODULES:
                    return f"Blocked import: '{alias.name}' is not allowed in editor scripts"

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_root = node.module.split(".")[0]
                if node.module in BLOCKED_MODULES or mod_root in BLOCKED_MODULES:
                    return f"Blocked import: 'from {node.module}' is not allowed in editor scripts"

        # Block dangerous attribute access (e.g., os.system, shutil.rmtree)
        elif isinstance(node, ast.Attribute):
            if node.attr in BLOCKED_ATTRS:
                # Check if it's on a known-dangerous module
                if isinstance(node.value, ast.Name) and node.value.id in ("os", "shutil", "pathlib"):
                    return f"Blocked operation: '{node.value.id}.{node.attr}' is not allowed"

        # Block dangerous builtin calls
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BLOCKED_BUILTINS:
                return f"Blocked builtin: '{func.id}()' is not allowed in editor scripts"

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# STRING SANITIZATION
# ═══════════════════════════════════════════════════════════════════════════════

# Valid UE identifier: alphanumeric, underscores, hyphens, spaces, dots
_SAFE_LABEL_RE = re.compile(r'^[\w\s\-\.()]+$', re.UNICODE)

# Valid UE class name: PascalCase identifier, no special chars
_SAFE_CLASS_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# Valid UE content path: /Game/... or /Engine/... with safe chars
_SAFE_PATH_RE = re.compile(r'^/[A-Za-z0-9_][A-Za-z0-9_/\-\.]*$')

# Valid UE object path (includes : and . for subobject addressing)
_SAFE_OBJECT_PATH_RE = re.compile(r'^/[A-Za-z0-9_][A-Za-z0-9_/\-\.\:]*$')

# Property names: alphanumeric, underscores
_SAFE_PROPERTY_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def sanitize_label(label: str, param_name: str = "label") -> Optional[str]:
    """Validate an actor label. Returns error message or None if valid."""
    if not label:
        return f"{param_name} cannot be empty"
    if len(label) > 256:
        return f"{param_name} too long ({len(label)} chars, max 256)"
    if not _SAFE_LABEL_RE.match(label):
        return f"{param_name} contains invalid characters: only alphanumeric, spaces, hyphens, dots, underscores, and parentheses are allowed"
    return None


def sanitize_class_name(class_name: str, param_name: str = "class_name") -> Optional[str]:
    """Validate a UE class name. Returns error message or None if valid."""
    if not class_name:
        return f"{param_name} cannot be empty"
    if len(class_name) > 128:
        return f"{param_name} too long ({len(class_name)} chars, max 128)"
    if not _SAFE_CLASS_RE.match(class_name):
        return f"{param_name} '{class_name}' is not a valid class name (must be alphanumeric/underscores, start with letter)"
    return None


def sanitize_content_path(path: str, param_name: str = "path") -> Optional[str]:
    """Validate a UE content path (/Game/..., /Engine/...). Returns error message or None."""
    if not path:
        return f"{param_name} cannot be empty"
    if len(path) > 512:
        return f"{param_name} too long ({len(path)} chars, max 512)"
    if not _SAFE_PATH_RE.match(path):
        return f"{param_name} '{path}' is not a valid content path (must start with / and contain only safe characters)"
    if ".." in path:
        return f"{param_name} contains path traversal sequence '..'"
    return None


def sanitize_object_path(path: str, param_name: str = "object_path") -> Optional[str]:
    """Validate a UE object path (includes : and . for subobjects). Returns error message or None."""
    if not path:
        return f"{param_name} cannot be empty"
    if len(path) > 1024:
        return f"{param_name} too long ({len(path)} chars, max 1024)"
    if not _SAFE_OBJECT_PATH_RE.match(path):
        return f"{param_name} '{path}' is not a valid object path"
    if ".." in path.replace("..", ""):  # Allow single dots but not ..
        pass  # UE paths legitimately use dots
    return None


def sanitize_property_name(name: str, param_name: str = "property_name") -> Optional[str]:
    """Validate a property name. Returns error message or None."""
    if not name:
        return f"{param_name} cannot be empty"
    if len(name) > 128:
        return f"{param_name} too long ({len(name)} chars, max 128)"
    if not _SAFE_PROPERTY_RE.match(name):
        return f"{param_name} '{name}' is not a valid property name"
    return None


def make_error(message: str) -> str:
    """Create a JSON error response string."""
    import json
    return json.dumps({"error": message}, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# CODE GENERATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def escape_for_fstring(s: str) -> str:
    """Escape a string for safe embedding in an f-string Python code template.

    Handles backslashes, quotes, and newlines to prevent injection
    when building UE5 Python scripts via f-string templates.
    """
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")


# ═══════════════════════════════════════════════════════════════════════════════
# CONSOLE COMMAND SANITIZATION
# ═══════════════════════════════════════════════════════════════════════════════

_BLOCKED_CONSOLE_COMMANDS = frozenset({
    "exit", "quit", "crash", "gpf", "debug crash",
    "restartlevel", "open", "servertravel",
    "killall", "disconnect", "reconnect",
})

_SAFE_CONSOLE_RE = re.compile(r'^[\w\s\.\-=,/]+$')


def sanitize_console_command(cmd: str, param_name: str = "command") -> Optional[str]:
    """Validate a UE console command. Returns error message or None if valid."""
    if not cmd:
        return f"{param_name} cannot be empty"
    if len(cmd) > 512:
        return f"{param_name} too long ({len(cmd)} chars, max 512)"
    cmd_lower = cmd.strip().lower()
    for blocked in _BLOCKED_CONSOLE_COMMANDS:
        if cmd_lower == blocked or cmd_lower.startswith(blocked + " "):
            return f"{param_name} '{blocked}' is blocked for safety"
    if not _SAFE_CONSOLE_RE.match(cmd):
        return f"{param_name} contains invalid characters"
    return None


def sanitize_filename(name: str, param_name: str = "filename") -> Optional[str]:
    """Validate a filename (no path separators). Returns error message or None if valid."""
    if not name:
        return f"{param_name} cannot be empty"
    if len(name) > 256:
        return f"{param_name} too long ({len(name)} chars, max 256)"
    if "/" in name or "\\" in name:
        return f"{param_name} must not contain path separators"
    if ".." in name:
        return f"{param_name} must not contain '..'"
    return None
