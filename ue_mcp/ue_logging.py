"""Structured JSON logging for the UE5 MCP server."""
from __future__ import annotations

import json
import logging
import sys
import time


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "tool"):
            log_entry["tool"] = record.tool
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        return json.dumps(log_entry, default=str)


def configure_logging(level: str = "INFO", json_format: bool = True) -> logging.Logger:
    """Configure logging for the MCP server.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR).
        json_format: If True, use JSON formatter. If False, use standard formatter.

    Returns:
        The configured ue5-mcp logger.
    """
    lvl = getattr(logging, level.upper(), logging.INFO)

    def _make_handler() -> logging.Handler:
        h = logging.StreamHandler(sys.stderr)
        if json_format:
            h.setFormatter(JSONFormatter())
        else:
            h.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            ))
        return h

    # Configure BOTH logger trees: the MCP server ("ue5-mcp.*") and the USD bridge
    # ("ue5-bridge.*"). Each gets its own handler with propagate=False. Without the
    # ue5-bridge handler, usd_bridge records had no handler in their chain and were
    # silently dropped below WARNING once basicConfig was removed.
    configured = []
    for name in ("ue5-mcp", "ue5-bridge"):
        lg = logging.getLogger(name)
        lg.setLevel(lvl)
        for handler in lg.handlers[:]:  # avoid duplicate handlers on re-init
            lg.removeHandler(handler)
        lg.addHandler(_make_handler())
        lg.propagate = False
        configured.append(lg)

    return configured[0]
