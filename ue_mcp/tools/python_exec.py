"""Python execution tool for UE5 MCP server.

This is the most powerful tool - it can run arbitrary Python in the editor context,
giving full access to the unreal module and all editor subsystems.

Security: Code is validated via AST analysis before execution to block dangerous
operations (subprocess, os.system, file deletion, etc.).
"""

from __future__ import annotations

import json
import logging

from ._validation import validate_python_code, make_error

logger = logging.getLogger("ue5-mcp.tools.python_exec")


def register(server, ue):
    @server.tool(
        name="ue_execute_python",
        description=(
            "Execute Python code inside the UE5 editor. "
            "The code has access to the 'unreal' module and all editor APIs. "
            "Use print() to return output. This is the most powerful tool - "
            "use it when no specific tool exists for your operation."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def execute_python(code: str) -> str:
        """Execute Python code in the UE5 editor.

        The code runs in the editor's Python environment with full access to:
        - unreal module (actors, assets, subsystems, etc.)
        - All editor utility libraries
        - File I/O within the project

        Use print() statements to return results.

        Blocked operations (for safety):
        - subprocess, shutil, socket imports
        - os.system, os.popen, os.remove, os.unlink
        - exec(), eval(), compile(), __import__()
        """
        # Validate code before sending to editor
        error = validate_python_code(code)
        if error:
            logger.warning("Code validation blocked: %s", error)
            return make_error(f"Code validation failed: {error}")

        logger.info("Executing Python (%d chars)", len(code))
        result = await ue.execute_python(code)
        if isinstance(result, dict) and result.get("error"):
            logger.warning("Python exec error: %s", result["error"][:200])
        return json.dumps(result, indent=2)
