"""Structured JSON logging for the UE5 MCP server."""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import Optional


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
        The configured root logger for ue5-mcp.
    """
    logger = logging.getLogger("ue5-mcp")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates on re-init
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        ))
    logger.addHandler(handler)
    logger.propagate = False

    return logger
