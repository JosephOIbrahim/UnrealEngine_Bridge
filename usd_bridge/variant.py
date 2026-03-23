"""
variant.py

USD variant setting (state machine transitions).

Provides:
- set_variant: Set USD variant selection
- _set_variant_pxr: Set variant using pxr USD library
- _set_variant_text: Set variant using text replacement
"""

import re
from pathlib import Path
from typing import Optional

from .pxr_backend import HAS_PXR
from .io import _atomic_write, _safe_read, get_bridge_file_path


def set_variant(
    variant_set: str,
    variant: str,
    bridge_path: Optional[Path] = None
) -> bool:
    """
    Set USD variant selection (state machine transition).

    Args:
        variant_set: "sync_status" or "message_type"
        variant: Target variant value
        bridge_path: Optional custom bridge directory

    Returns:
        True if successful, False otherwise

    Example:
        set_variant("sync_status", "question_pending")
        set_variant("message_type", "answer")
    """
    file_path = get_bridge_file_path(bridge_path)

    if not file_path.exists():
        return False

    if HAS_PXR:
        return _set_variant_pxr(file_path, variant_set, variant)
    else:
        return _set_variant_text(file_path, variant_set, variant)


def _set_variant_pxr(file_path: Path, variant_set: str, variant: str) -> bool:
    """Set variant using pxr USD library."""
    try:
        from pxr import Usd

        stage = Usd.Stage.Open(str(file_path))
        root = stage.GetPrimAtPath("/BridgeState")
        vsets = root.GetVariantSets()

        if vsets.HasVariantSet(variant_set):
            vsets.GetVariantSet(variant_set).SetVariantSelection(variant)
            stage.Save()
            return True
        return False

    except Exception as e:
        print(f"[USD Bridge] Error setting variant: {e}")
        return False


def _set_variant_text(file_path: Path, variant_set: str, variant: str) -> bool:
    """Set variant using text replacement (fallback)."""
    try:
        content = _safe_read(file_path)
        if content is None:
            return False

        # Replace variant selection in the variants = {...} block
        pattern = rf'(string {variant_set} = ")[^"]*(")'
        replacement = rf'\g<1>{variant}\g<2>'
        new_content = re.sub(pattern, replacement, content)

        if new_content == content:
            return False

        _atomic_write(file_path, new_content)
        return True

    except Exception as e:
        print(f"[USD Bridge] Error setting variant (text): {e}")
        return False
