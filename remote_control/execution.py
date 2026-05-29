"""Execution helpers -- write-to-file + poll-for-result pattern."""

import json
import os
import time
import uuid

from .constants import (
    MAX_RESPONSE_BYTES,
    RESULT_POLL_INTERVAL,
    RESULT_POLL_TIMEOUT,
    logger,
)


def _make_temp_dir() -> str:
    """Create and return the shared temp directory for UE scripts."""
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "ue_mcp_scripts")
    os.makedirs(d, exist_ok=True)
    return d


def _wrap_code(code: str, result_file: str) -> str:
    """Wrap user code with stdout capture and result file output.

    The wrapper:
    1. Redirects stdout to a StringIO buffer
    2. Executes the user code
    3. Writes {"output": captured_stdout, "error": null} to result_file
    4. On exception, writes {"output": partial_stdout, "error": traceback_str}
    """
    # Escape the result path for embedding in Python string
    safe_path = result_file.replace("\\", "/")
    return f'''
import sys as _sys, io as _io, traceback as _tb, json as _json

_buf = _io.StringIO()
_old_stdout = _sys.stdout
_sys.stdout = _buf
_error = None
try:
{_indent(code)}
except Exception:
    _error = _tb.format_exc()
finally:
    _sys.stdout = _old_stdout
    _out = _buf.getvalue()
    with open("{safe_path}", "w", encoding="utf-8") as _rf:
        _json.dump({{"output": _out, "error": _error}}, _rf)
'''


def _indent(code: str, spaces: int = 4) -> str:
    """Indent every line of code by `spaces`."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in code.splitlines())


def _parse_result(raw: dict) -> dict:
    """Parse a result file dict, extracting RESULT: lines if present."""
    output = raw.get("output", "")
    error = raw.get("error")

    # Look for RESULT: lines in the output
    result_data = None
    output_lines = []
    for line in output.splitlines():
        if line.startswith("RESULT:"):
            payload = line[len("RESULT:"):]
            try:
                result_data = json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                result_data = payload
        else:
            output_lines.append(line)

    return {
        "result": result_data,
        "output": "\n".join(output_lines).strip() if output_lines else "",
        "error": error,
    }


def _prepare_execution(temp_dir: str, code: str) -> tuple[str, str, str]:
    """Prepare a script for execution. Returns (result_file, script_file, wrapped_code)."""
    result_id = uuid.uuid4().hex[:12]
    result_file = os.path.join(temp_dir, f"result_{result_id}.json").replace("\\", "/")
    script_file = os.path.join(temp_dir, f"cmd_{result_id}.py").replace("\\", "/")

    if os.path.exists(result_file):
        os.remove(result_file)

    wrapped = _wrap_code(code, result_file)
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(wrapped)

    return result_file, script_file, wrapped


def _build_exec_payload(script_file: str) -> dict:
    """Build the Remote Control call payload for script execution."""
    return {
        "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
        "functionName": "ExecuteConsoleCommand",
        "parameters": {
            "WorldContextObject": "",
            "Command": f"py {script_file}",
        },
    }


def _read_result_file(result_file: str) -> dict:
    """Read and validate a result JSON file with size limits."""
    file_size = os.path.getsize(result_file)
    if file_size > MAX_RESPONSE_BYTES:
        return {
            "result": None,
            "output": "",
            "error": f"Result file too large ({file_size} bytes, max {MAX_RESPONSE_BYTES}). "
                     f"Reduce output size or use file-based data transfer.",
        }
    with open(result_file, encoding="utf-8") as f:
        return json.load(f)


def _poll_result_sync(result_file: str, script_file: str) -> dict:
    """Poll for result file (synchronous)."""
    elapsed = 0.0
    while elapsed < RESULT_POLL_TIMEOUT:
        if os.path.exists(result_file):
            try:
                raw = _read_result_file(result_file)
                os.remove(result_file)
                os.remove(script_file)
                return _parse_result(raw)
            except json.JSONDecodeError as e:
                logger.warning("Corrupt result file %s: %s", result_file, e)
            except OSError as e:
                logger.warning("Could not read result file %s: %s", result_file, e)
        time.sleep(RESULT_POLL_INTERVAL)
        elapsed += RESULT_POLL_INTERVAL

    logger.warning("Timed out after %.1fs waiting for %s", RESULT_POLL_TIMEOUT, result_file)
    _cleanup_files(result_file, script_file)
    return _timeout_result()


async def _poll_result_async(result_file: str, script_file: str) -> dict:
    """Poll for result file (async)."""
    import asyncio
    elapsed = 0.0
    while elapsed < RESULT_POLL_TIMEOUT:
        if os.path.exists(result_file):
            try:
                raw = _read_result_file(result_file)
                os.remove(result_file)
                os.remove(script_file)
                return _parse_result(raw)
            except json.JSONDecodeError as e:
                logger.warning("Corrupt result file %s: %s", result_file, e)
            except OSError as e:
                logger.warning("Could not read result file %s: %s", result_file, e)
        await asyncio.sleep(RESULT_POLL_INTERVAL)
        elapsed += RESULT_POLL_INTERVAL

    logger.warning("Timed out after %.1fs waiting for %s", RESULT_POLL_TIMEOUT, result_file)
    _cleanup_files(result_file, script_file)
    return _timeout_result()


def _cleanup_files(*paths: str):
    for p in paths:
        if os.path.exists(p):
            os.remove(p)


def _timeout_result() -> dict:
    return {
        "result": None,
        "output": "",
        "error": f"Timed out after {RESULT_POLL_TIMEOUT}s waiting for editor to execute script. Check UE5 Output Log for errors.",
    }
