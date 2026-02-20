"""
UE5 MCP Server - Gives Claude Code native tool access to the Unreal Editor.

Communicates with UE5 via the Remote Control plugin REST API (localhost:30010).
Runs as an MCP server over stdio transport using FastMCP.

Usage (registered via `claude mcp add`):
    python ue_mcp/mcp_server.py
    # or via entry point:
    ue-mcp
"""

import atexit
import glob
import sys
import os
import json
import logging
import tempfile

# Ensure the ue-bridge root is importable (for remote_control_bridge)
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from mcp.server.fastmcp import FastMCP
from remote_control_bridge import AsyncUnrealRemoteControl, BASE_URL
from ue_mcp.__version__ import __version__
from ue_mcp.metrics import metrics
from ue_mcp.tools import register_all_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("ue5-mcp")

# Create server and bridge
server = FastMCP("unreal-engine")
ue = AsyncUnrealRemoteControl()

# Register all tool modules
register_all_tools(server, ue)


# ══════════════════════════════════════════════════════════════════════════════
# Graceful shutdown
# ══════════════════════════════════════════════════════════════════════════════

def _cleanup():
    """Clean up resources on exit."""
    # Close httpx clients
    try:
        ue.close()
    except Exception:
        pass

    # Remove stale temp files from ue_mcp_scripts
    tmp_dir = os.path.join(tempfile.gettempdir(), "ue_mcp_scripts")
    if os.path.isdir(tmp_dir):
        stale = glob.glob(os.path.join(tmp_dir, "*.py")) + glob.glob(os.path.join(tmp_dir, "*.json"))
        removed = 0
        for f in stale:
            try:
                os.unlink(f)
                removed += 1
            except OSError:
                pass
        if removed:
            logger.info("Cleanup: removed %d temp files from %s", removed, tmp_dir)

atexit.register(_cleanup)


# ══════════════════════════════════════════════════════════════════════════════
# Tools defined here (need access to `ue` and `metrics` instances)
# ══════════════════════════════════════════════════════════════════════════════

@server.tool(
    name="ue_status",
    description="Check if the UE5 editor is running and the Remote Control API is reachable.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def status() -> str:
    """Returns connection status and editor info if available."""
    connected = await ue.is_connected()
    if connected:
        try:
            info = await ue.info()
            return json.dumps({
                "connected": True,
                "version": __version__,
                "info": info,
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "connected": True,
                "version": __version__,
                "info_error": str(e),
            }, indent=2)
    return json.dumps({
        "connected": False,
        "version": __version__,
        "message": f"UE5 editor not reachable at {BASE_URL}. Start the editor with RemoteControl plugin enabled.",
    }, indent=2)


@server.tool(
    name="ue_health_check",
    description=(
        "Get bridge health: version, uptime, circuit breaker state, "
        "request metrics (counts, latencies, error rates). "
        "Use this to diagnose connection issues."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def health_check() -> str:
    """Comprehensive health report for the UE5 bridge."""
    connected = await ue.is_connected()
    cb_state = ue._cb.state if hasattr(ue, "_cb") else "unknown"

    snap = metrics.snapshot()

    return json.dumps({
        "version": __version__,
        "connected": connected,
        "base_url": BASE_URL,
        "circuit_breaker": cb_state,
        "uptime_s": snap["uptime_s"],
        "counters": snap["counters"],
        "latencies": snap["latencies"],
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# Startup
# ══════════════════════════════════════════════════════════════════════════════

def _startup_checks():
    """Run pre-flight checks and log startup info."""
    logger.info("ue-bridge v%s starting (stdio transport)", __version__)
    logger.info("UE5 Remote Control endpoint: %s", BASE_URL)

    # Verify temp dir is writable
    tmp_dir = os.path.join(tempfile.gettempdir(), "ue_mcp_scripts")
    try:
        os.makedirs(tmp_dir, exist_ok=True)
        test_file = os.path.join(tmp_dir, "_startup_check.tmp")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.unlink(test_file)
    except OSError as e:
        logger.warning("Temp directory not writable (%s): %s", tmp_dir, e)

    logger.info("Startup checks passed — ready for connections")


def main():
    """Entry point for the MCP server."""
    _startup_checks()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
