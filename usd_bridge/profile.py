"""
profile.py

ThinkingMachines [He2025] batch-invariance compliant anchors and profile utilities.

Provides:
- compute_checksum: Deterministic DJB2 checksum for profile dimensions
- generate_exec_anchor: Generate [EXEC:...] anchor string
- parse_exec_anchor: Parse [EXEC:...] anchor to extract routing parameters
- get_expert_from_signals: Route to ADHD_MoE expert based on behavioral signals
"""

import re
from typing import Any, Dict, Optional


def compute_checksum(dimensions: Dict[str, Any]) -> str:
    """
    Compute deterministic checksum for profile (ThinkingMachines [He2025] compliant).

    FIXED algorithm: Sort alphabetically, serialize, DJB2 hash to 8-char hex.
    Same inputs ALWAYS produce same output regardless of call order or batch size.

    Args:
        dimensions: Dict of profile dimensions

    Returns:
        8-character hex checksum
    """
    # FIXED: Sort alphabetically for determinism
    sorted_dims = sorted(dimensions.items())

    # FIXED: Serialize format TRL_v1|key:value|key:value|...
    serialized = "TRL_v1|" + "|".join(f"{k}:{v}" for k, v in sorted_dims)

    # FIXED: DJB2 hash algorithm (batch-invariant)
    hash_val = 5381
    for char in serialized:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
        hash_val &= 0xFFFFFFFF  # Keep 32-bit

    return format(hash_val, '08x')


def generate_exec_anchor(
    checksum: str,
    expert: str = "Direct",
    paradigm: str = "Cortex",
    altitude: str = "Ground",
    verbosity: str = "standard",
    think_depth: str = "standard"
) -> str:
    """
    Generate ThinkingMachines-compliant [EXEC:...] anchor.

    Format: [EXEC:{checksum}|{expert}|{paradigm}|{altitude}|{verbosity}|{think_depth}]

    This anchor encodes the routing parameters used for this response,
    enabling reproducibility verification per ThinkingMachines [He2025].

    Args:
        checksum: Profile checksum (8 hex chars)
        expert: ADHD_MoE expert (Validator|Scaffolder|Restorer|Refocuser|Celebrator|Socratic|Direct)
        paradigm: Cortex (hierarchical) or Mycelium (emergent)
        altitude: 30000ft|15000ft|5000ft|Ground
        verbosity: minimal|standard|detailed
        think_depth: minimal|standard|deep|ultradeep

    Returns:
        Formatted [EXEC:...] anchor string
    """
    return f"[EXEC:{checksum}|{expert}|{paradigm}|{altitude}|{verbosity}|{think_depth}]"


def parse_exec_anchor(anchor: str) -> Optional[Dict[str, str]]:
    """
    Parse [EXEC:...] anchor to extract routing parameters.

    Args:
        anchor: The [EXEC:...] anchor string

    Returns:
        Dict with checksum, expert, paradigm, altitude, verbosity, think_depth
        or None if parsing fails
    """
    match = re.match(r'\[EXEC:([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^\]]+)\]', anchor)
    if not match:
        return None

    return {
        "checksum": match.group(1),
        "expert": match.group(2),
        "paradigm": match.group(3),
        "altitude": match.group(4),
        "verbosity": match.group(5),
        "think_depth": match.group(6)
    }


def get_expert_from_signals(signals: Dict[str, Any]) -> str:
    """
    Route to ADHD_MoE expert based on behavioral signals.

    FIXED PRIORITY (first match wins - ThinkingMachines compliant):
    1. Validator  - frustrated, RED, caps, negative
    2. Scaffolder - overwhelmed, stuck, too_many
    3. Restorer   - depleted, ORANGE, post-crash
    4. Refocuser  - distracted, tangent_over
    5. Celebrator - task_complete, milestone
    6. Socratic   - exploring, high_energy, what if
    7. Direct     - focused, hyperfocused, flow (DEFAULT)

    Args:
        signals: Behavioral signals dict

    Returns:
        Expert name string
    """
    detected_state = signals.get("detected_state", "focused")
    burnout_level = signals.get("burnout_level", "GREEN")
    rapid_clicks = signals.get("rapid_click_count", 0)
    hesitations = signals.get("hesitation_count", 0)

    # FIXED priority order - NEVER reorder or skip

    # Priority 1: Validator
    if detected_state == "frustrated" or burnout_level == "RED" or rapid_clicks > 3:
        return "Validator"

    # Priority 2: Scaffolder
    if detected_state in ("stuck", "overwhelmed") or hesitations > 2:
        return "Scaffolder"

    # Priority 3: Restorer
    if detected_state == "depleted" or burnout_level == "ORANGE":
        return "Restorer"

    # Priority 4: Refocuser
    if detected_state == "distracted":
        return "Refocuser"

    # Priority 5: Celebrator
    if detected_state == "completing":
        return "Celebrator"

    # Priority 6: Socratic
    if detected_state == "exploring":
        return "Socratic"

    # Priority 7: Direct (DEFAULT)
    return "Direct"
