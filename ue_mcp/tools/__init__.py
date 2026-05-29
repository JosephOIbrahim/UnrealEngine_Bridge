"""Tool registry for UE5 MCP server."""

from ._types import MCPServer, UEBridge
from .actors import register as register_actors
from .assets import register as register_assets
from .blueprints import register as register_blueprints
from .editor import register as register_editor
from .level import register as register_level
from .lighting import register as register_lighting
from .materials import register as register_materials
from .mograph import register as register_mograph
from .perception import register as register_perception
from .properties import register as register_properties
from .python_exec import register as register_python_exec
from .scene import register as register_scene
from .sequencer import register as register_sequencer
from .spatial import register as register_spatial


def register_all_tools(server: MCPServer, ue: UEBridge) -> None:
    """Register all tool modules with the MCP server."""
    register_actors(server, ue)
    register_properties(server, ue)
    register_python_exec(server, ue)
    register_assets(server, ue)
    register_level(server, ue)
    register_mograph(server, ue)
    register_blueprints(server, ue)
    register_perception(server, ue)
    register_scene(server, ue)
    register_spatial(server, ue)
    register_lighting(server, ue)
    register_materials(server, ue)
    register_editor(server, ue)
    register_sequencer(server, ue)
