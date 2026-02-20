"""Tool registry for UE5 MCP server."""

from .actors import register as register_actors
from .properties import register as register_properties
from .python_exec import register as register_python_exec
from .assets import register as register_assets
from .level import register as register_level
from .mograph import register as register_mograph
from .blueprints import register as register_blueprints
from .perception import register as register_perception


def register_all_tools(server, ue):
    """Register all tool modules with the MCP server."""
    register_actors(server, ue)
    register_properties(server, ue)
    register_python_exec(server, ue)
    register_assets(server, ue)
    register_level(server, ue)
    register_mograph(server, ue)
    register_blueprints(server, ue)
    register_perception(server, ue)
