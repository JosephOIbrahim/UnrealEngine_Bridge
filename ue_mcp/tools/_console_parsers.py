"""Parsers for structured output from UE5 console commands.

These convert raw text output from common stat/debug commands into
structured JSON for easier consumption by AI agents.
"""
from __future__ import annotations

import re


def parse_stat_fps(output: str) -> dict | None:
    """Parse 'stat fps' output into structured data."""
    fps_match = re.search(r'(\d+(?:\.\d+)?)\s*fps', output, re.IGNORECASE)
    ms_match = re.search(r'(\d+(?:\.\d+)?)\s*ms', output, re.IGNORECASE)
    if fps_match or ms_match:
        result = {"command": "stat fps"}
        if fps_match:
            result["fps"] = float(fps_match.group(1))
        if ms_match:
            result["frame_time_ms"] = float(ms_match.group(1))
        return result
    return None


def parse_stat_unit(output: str) -> dict | None:
    """Parse 'stat unit' output into structured data."""
    result = {"command": "stat unit"}
    patterns = {
        "frame": r'Frame:\s*(\d+(?:\.\d+)?)\s*ms',
        "game": r'Game:\s*(\d+(?:\.\d+)?)\s*ms',
        "draw": r'Draw:\s*(\d+(?:\.\d+)?)\s*ms',
        "gpu": r'GPU:\s*(\d+(?:\.\d+)?)\s*ms',
        "rhit": r'RHIT:\s*(\d+(?:\.\d+)?)\s*ms',
        "swap": r'Swap:\s*(\d+(?:\.\d+)?)\s*ms',
    }
    found = False
    for key, pattern in patterns.items():
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            result[f"{key}_ms"] = float(match.group(1))
            found = True
    return result if found else None


def parse_stat_memory(output: str) -> dict | None:
    """Parse 'stat memory' or 'stat memorychurn' output."""
    result = {"command": "stat memory"}
    patterns = {
        "used_physical": r'Used Physical[^:]*:\s*(\d+(?:\.\d+)?)\s*(MB|GB|KB)',
        "available_physical": r'Available Physical[^:]*:\s*(\d+(?:\.\d+)?)\s*(MB|GB|KB)',
        "used_virtual": r'Used Virtual[^:]*:\s*(\d+(?:\.\d+)?)\s*(MB|GB|KB)',
        "peak_used_physical": r'Peak Used Physical[^:]*:\s*(\d+(?:\.\d+)?)\s*(MB|GB|KB)',
    }
    found = False
    for key, pattern in patterns.items():
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).upper()
            if unit == "KB":
                value /= 1024
            elif unit == "GB":
                value *= 1024
            result[f"{key}_mb"] = round(value, 2)
            found = True
    return result if found else None


# Map of known commands to their parsers
PARSERS: dict[str, callable] = {
    "stat fps": parse_stat_fps,
    "stat unit": parse_stat_unit,
    "stat memory": parse_stat_memory,
    "stat memorychurn": parse_stat_memory,
}


def try_parse_output(command: str, output: str) -> dict | None:
    """Try to parse console command output into structured data.

    Returns structured dict if a parser matches, None otherwise.
    """
    cmd_lower = command.strip().lower()
    parser = PARSERS.get(cmd_lower)
    if parser:
        return parser(output)
    return None
