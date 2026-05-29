"""Protocol types for MCP tool registration.

These define the interface contracts between tool modules and the
MCP server / UE5 bridge, enabling type checking without coupling.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MCPServer(Protocol):
    """Protocol for the FastMCP server instance passed to register()."""

    def tool(
        self,
        *,
        name: str,
        description: str,
        annotations: dict[str, bool] | None = None,
    ) -> Callable: ...


@runtime_checkable
class UEBridge(Protocol):
    """Protocol for the async UE5 Remote Control bridge."""

    async def execute_python(self, code: str) -> dict[str, Any]: ...
    async def is_connected(self) -> bool: ...
    async def info(self) -> dict[str, Any]: ...
    async def get_property(self, object_path: str, property_name: str) -> Any: ...
    async def set_property(self, object_path: str, property_name: str, value: Any) -> dict[str, Any]: ...
