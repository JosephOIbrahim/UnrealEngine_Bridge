"""Fixtures for the exec-sim harness.

Registers all tools ONCE per session against:

- a recording fake server (satisfies the MCPServer Protocol; stores
  ``{name: (fn, annotations)}``), and
- a capture UE client that subclasses the REAL ``AsyncUnrealRemoteControl``
  but overrides only ``execute_python`` -- so client-side codegen delegation
  (spawn_actor -> _CodeGen.spawn_actor_code, ...) is exercised verbatim while
  every generated script is captured instead of sent over HTTP.

Tests are plain sync functions; async tool coroutines are driven with
``asyncio.run`` (pytest-asyncio strict mode stays untouched).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from remote_control.async_client import AsyncUnrealRemoteControl  # noqa: E402
from tests.exec_sim.registry import REGISTRY  # noqa: E402
from ue_mcp.tools import register_all_tools  # noqa: E402


class RecordingServer:
    """Fake MCP server: records registrations instead of serving them."""

    def __init__(self):
        self.tools: dict[str, tuple] = {}

    def tool(self, *, name: str, description: str, annotations: dict | None = None):
        def decorator(fn):
            if name in self.tools:
                raise AssertionError(f"duplicate tool registration: {name}")
            self.tools[name] = (fn, annotations)
            return fn

        return decorator


class CaptureUE(AsyncUnrealRemoteControl):
    """Real client delegation, fake transport.

    Deliberately does NOT call super().__init__ -- no HTTP client, no circuit
    breaker. The convenience methods (spawn_actor, delete_actor, list_actors,
    set_actor_transform, find_assets, get_level_info, save_level) run their
    real code paths and land in this overridden execute_python.
    """

    def __init__(self):  # noqa: D107 -- see class docstring
        self.captured: list[str] = []
        # Shape mirrors remote_control.execution._parse_result output.
        self.result: dict = {"result": None, "output": "", "error": None}

    async def execute_python(self, code: str) -> dict:
        self.captured.append(code)
        return dict(self.result)


class Toolbox:
    """Session-wide registration + code capture with per-tool caching."""

    def __init__(self):
        self.server = RecordingServer()
        self.ue = CaptureUE()
        # The harness gates every tool's codegen regardless of what the
        # default profile mounts — always register the full surface.
        register_all_tools(self.server, self.ue, profile="all")
        self._code_cache: dict[str, list[str]] = {}

    @property
    def registered_names(self) -> set[str]:
        return set(self.server.tools)

    def invoke(self, tool_name: str, **kwargs) -> list[str]:
        """Invoke a registered tool coroutine; return the captured scripts."""
        fn, _annotations = self.server.tools[tool_name]
        self.ue.captured = []
        asyncio.run(fn(**kwargs))
        return list(self.ue.captured)

    def codes_for(self, tool_name: str) -> list[str]:
        """Captured scripts for the registry's canonical sentinel kwargs (cached)."""
        if tool_name not in self._code_cache:
            entry = REGISTRY[tool_name]
            self._code_cache[tool_name] = self.invoke(tool_name, **entry.kwargs)
        return self._code_cache[tool_name]


@pytest.fixture(scope="session")
def toolbox() -> Toolbox:
    return Toolbox()
