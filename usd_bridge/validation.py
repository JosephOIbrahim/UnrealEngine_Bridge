"""
validation.py

Bridge state validation for the USD bridge.

Provides:
- validate_bridge_state: Validate bridge_state.usda for correctness
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from .pxr_backend import HAS_PXR
from .io import _safe_read, get_bridge_file_path


def validate_bridge_state(bridge_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Validate bridge_state.usda for correctness.

    Returns:
        Dict with validation results.
    """
    file_path = get_bridge_file_path(bridge_path)
    result = {
        "valid": False,
        "file_exists": file_path.exists(),
        "errors": [],
        "warnings": [],
        "sync_status": None,
        "message_type": None,
    }

    if not file_path.exists():
        result["errors"].append(f"File not found: {file_path}")
        return result

    try:
        content = _safe_read(file_path)
        if content is None:
            result["errors"].append("Could not read file (locked or permission denied)")
            return result

        # Check USDA header
        if not content.startswith("#usda 1.0"):
            result["errors"].append("Missing or invalid USDA header")

        # Check default prim
        if 'defaultPrim = "BridgeState"' not in content:
            result["errors"].append("Missing defaultPrim = 'BridgeState'")

        # Check required prims
        required_prims = ["Message", "Options", "Answer", "Transition", "Finale", "Ready", "Ack"]
        for prim in required_prims:
            if f'def Xform "{prim}"' not in content:
                result["errors"].append(f"Missing required prim: {prim}")

        # Parse variant selections
        sync_match = re.search(r'string sync_status = "([^"]*)"', content)
        type_match = re.search(r'string message_type = "([^"]*)"', content)

        result["sync_status"] = sync_match.group(1) if sync_match else None
        result["message_type"] = type_match.group(1) if type_match else None

        if not result["sync_status"]:
            result["errors"].append("Could not parse sync_status variant")
        if not result["message_type"]:
            result["errors"].append("Could not parse message_type variant")

        # Validation result
        result["valid"] = len(result["errors"]) == 0

        if HAS_PXR:
            # Additional validation with pxr
            try:
                from pxr import Usd

                stage = Usd.Stage.Open(str(file_path))
                root = stage.GetPrimAtPath("/BridgeState")
                if not root:
                    result["errors"].append("Could not open /BridgeState prim with pxr")
                    result["valid"] = False
            except Exception as e:
                result["warnings"].append(f"pxr validation warning: {e}")

    except Exception as e:
        result["errors"].append(f"Error reading file: {e}")

    return result
