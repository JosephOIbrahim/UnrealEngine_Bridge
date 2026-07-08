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
import json
import os
import tempfile

import httpx
from mcp.server.fastmcp import FastMCP

from remote_control import BASE_URL, AsyncUnrealRemoteControl, preflight
from ue_mcp.__version__ import __version__
from ue_mcp.metrics import metrics
from ue_mcp.tools import register_all_tools
from ue_mcp.ue_logging import configure_logging

logger = configure_logging()

# Create server and bridge
server = FastMCP("unreal-engine")
ue = AsyncUnrealRemoteControl()

# Epic's official Unreal MCP (UE 5.8+) — probed for the health report only.
EPIC_MCP_URL = os.environ.get("UE_EPIC_MCP_URL", "http://127.0.0.1:8000/mcp")

# Register tool modules, filtered by UE_MCP_PROFILE (default "core" since the
# Epic-MCP retirement flip — see docs/EPIC_MCP_MATRIX.md).
registry = register_all_tools(server, ue)
if registry.profile_warning:
    logger.warning(registry.profile_warning)
logger.info(
    "tool profile %r: %d mounted, %d unmounted",
    registry.profile, len(registry.registered), len(registry.skipped),
)


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
        "Use this to diagnose connection issues. Pass deep=true to also run the "
        "capability preflight (can the bridge actually execute, not just connect)."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def health_check(deep: bool = False) -> str:
    """Comprehensive health report for the UE5 bridge."""
    connected = await ue.is_connected()
    cb_state = ue._cb.state if hasattr(ue, "_cb") else "unknown"

    snap = metrics.snapshot()

    epic_reachable = False
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            await client.get(EPIC_MCP_URL)
            epic_reachable = True  # any HTTP response proves the server is up
    except Exception:
        # Diagnostics must never raise — e.g. httpx.InvalidURL from a
        # misconfigured UE_EPIC_MCP_URL is not an HTTPError subclass.
        pass

    report = {
        "version": __version__,
        "connected": connected,
        "base_url": BASE_URL,
        "circuit_breaker": cb_state,
        "uptime_s": snap["uptime_s"],
        "counters": snap["counters"],
        "latencies": snap["latencies"],
        "tool_profile": registry.profile,
        "tools_mounted": len(registry.registered),
        "tools_unmounted": len(registry.skipped),
        "epic_mcp": {"url": EPIC_MCP_URL, "reachable": epic_reachable},
    }
    if registry.unclassified:
        report["unclassified_tools"] = registry.unclassified
    if registry.profile_warning:
        report["profile_warning"] = registry.profile_warning
    if deep:
        pf = await preflight(ue)
        report["preflight"] = {
            "ok": pf.ok,
            "rung": pf.rung,
            "cause": pf.cause,
            "fix": pf.fix,
            "engine_version": pf.engine_version,
        }
    return json.dumps(report, indent=2)


@server.tool(
    name="ue_preflight",
    description=(
        "Capability preflight: probe whether the bridge can ACTUALLY execute "
        "against the editor, not merely connect. Runs a ladder -- reachable, "
        "remote function calls permitted, a value round-trips, full Python "
        "round-trip -- stops at the first failure, and returns the named cause "
        "plus the one-line fix (with the raw Remote Control error body as "
        "evidence). Use this whenever tools error but ue_status says connected -- "
        "e.g. UE 5.8's bAllowAnyRemoteFunctionCall block."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def preflight_check() -> str:
    """Run the capability ladder and report the first failure with a fix."""
    pf = await preflight(ue)
    return json.dumps({
        "ok": pf.ok,
        "rung": pf.rung,
        "cause": pf.cause,
        "fix": pf.fix,
        "evidence": pf.evidence,
        "engine_version": pf.engine_version,
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
