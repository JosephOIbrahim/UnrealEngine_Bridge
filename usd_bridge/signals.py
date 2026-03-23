"""
signals.py

Behavioral signals and acknowledgment reading for the USD bridge.

Provides:
- read_behavioral_signals: Read behavioral signals from bridge_state.usda
- read_ack_usda: Read acknowledgment from bridge_state.usda
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from .io import _safe_read, get_bridge_file_path


def read_ack_usda(bridge_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Read acknowledgment from bridge_state.usda.

    Returns:
        Dict with ack data or None if no ack available.
    """
    file_path = get_bridge_file_path(bridge_path)

    if not file_path.exists():
        return None

    try:
        content = _safe_read(file_path)
        if content is None:
            return None

        # Check message_type variant
        type_match = re.search(r'string message_type = "([^"]*)"', content)
        if not type_match or type_match.group(1) != "ack":
            return None

        # Find Ack prim section
        ack_section_match = re.search(
            r'def Xform "Ack"[^{]*\{([^}]*)\}',
            content,
            re.DOTALL
        )
        if not ack_section_match:
            return None

        ack_section = ack_section_match.group(1)

        # Parse attributes
        ready_match = re.search(r'bool ready = (true|false)', ack_section)
        ue_version_match = re.search(r'string ue_version = "([^"]*)"', ack_section)
        project_match = re.search(r'string project = "([^"]*)"', ack_section)

        ready = ready_match.group(1) == "true" if ready_match else False

        if not ready:
            return None

        return {
            "ready": ready,
            "ue_version": ue_version_match.group(1) if ue_version_match else "",
            "project": project_match.group(1) if project_match else "",
        }

    except Exception as e:
        print(f"[USD Bridge] Error reading ack: {e}")
        return None


def read_behavioral_signals(bridge_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Read behavioral signals from bridge_state.usda.

    Used for ADHD_MoE expert routing based on detected user behavior.

    Returns:
        Dict with behavioral signal data.
    """
    file_path = get_bridge_file_path(bridge_path)

    if not file_path.exists():
        return None

    try:
        content = _safe_read(file_path)
        if content is None:
            return None

        # Find BehavioralSignals prim section
        signals_match = re.search(
            r'def Xform "BehavioralSignals"[^{]*\{([^}]*)\}',
            content,
            re.DOTALL
        )
        if not signals_match:
            return None

        signals_section = signals_match.group(1)

        # Parse attributes
        def get_attr(pattern: str, default: Any = "") -> Any:
            match = re.search(pattern, signals_section)
            return match.group(1) if match else default

        return {
            "last_response_time_ms": float(get_attr(r'double last_response_time_ms = ([\d.]+)', "0.0")),
            "average_response_time_ms": float(get_attr(r'double average_response_time_ms = ([\d.]+)', "0.0")),
            "hesitation_count": int(get_attr(r'int hesitation_count = (\d+)', "0")),
            "long_hesitation_detected": get_attr(r'bool long_hesitation_detected = (true|false)', "false") == "true",
            "rapid_click_count": int(get_attr(r'int rapid_click_count = (\d+)', "0")),
            "skip_count": int(get_attr(r'int skip_count = (\d+)', "0")),
            "back_navigation_count": int(get_attr(r'int back_navigation_count = (\d+)', "0")),
            "detected_state": get_attr(r'string detected_state = "([^"]*)"', "focused"),
            "recommended_expert": get_attr(r'string recommended_expert = "([^"]*)"', "Direct"),
            "burnout_level": get_attr(r'string burnout_level = "([^"]*)"', "GREEN"),
            "momentum_phase": get_attr(r'string momentum_phase = "([^"]*)"', "cold_start"),
        }

    except Exception as e:
        print(f"[USD Bridge] Error reading behavioral signals: {e}")
        return None
