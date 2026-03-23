"""
usd_bridge package

USD-Native Bridge Communication for CC<->UE5.

This package provides functions to read/write USD files for bridge communication,
replacing the JSON-based state.json/answer.json protocol with USD composition semantics.

All public names are re-exported here for backward compatibility:
    from usd_bridge import write_question_usda, read_answer_usda, ...
"""

# --- pxr_backend: HAS_PXR flag ---
from .pxr_backend import HAS_PXR

# --- io: File I/O, path helpers, constants ---
from .io import (
    DEFAULT_BRIDGE_PATH,
    BRIDGE_STATE_FILE,
    BRIDGE_VERSION,
    _file_lock,
    _atomic_write,
    _safe_read,
    _validate_bridge_path,
    get_bridge_file_path,
    ensure_bridge_directory,
    get_timestamp,
)

# --- question: Question writing and answer reading ---
from .question import (
    write_question_usda,
    _write_question_pxr,
    _write_question_text,
    _update_question_incremental,
    read_answer_usda,
    _read_answer_pxr,
    _read_answer_text,
)

# --- variant: State machine transitions ---
from .variant import (
    set_variant,
    _set_variant_pxr,
    _set_variant_text,
)

# --- transition: Transition, finale, ready ---
from .transition import (
    write_transition_usda,
    write_finale_usda,
    write_ready_usda,
)

# --- signals: Behavioral signals and ack ---
from .signals import (
    read_behavioral_signals,
    read_ack_usda,
)

# --- profile: Checksum, EXEC anchors, expert routing ---
from .profile import (
    compute_checksum,
    generate_exec_anchor,
    parse_exec_anchor,
    get_expert_from_signals,
)

# --- validation ---
from .validation import (
    validate_bridge_state,
)

__all__ = [
    # pxr_backend
    "HAS_PXR",
    # io
    "DEFAULT_BRIDGE_PATH",
    "BRIDGE_STATE_FILE",
    "BRIDGE_VERSION",
    "_file_lock",
    "_atomic_write",
    "_safe_read",
    "_validate_bridge_path",
    "get_bridge_file_path",
    "ensure_bridge_directory",
    "get_timestamp",
    # question
    "write_question_usda",
    "_write_question_pxr",
    "_write_question_text",
    "_update_question_incremental",
    "read_answer_usda",
    "_read_answer_pxr",
    "_read_answer_text",
    # variant
    "set_variant",
    "_set_variant_pxr",
    "_set_variant_text",
    # transition
    "write_transition_usda",
    "write_finale_usda",
    "write_ready_usda",
    # signals
    "read_behavioral_signals",
    "read_ack_usda",
    # profile
    "compute_checksum",
    "generate_exec_anchor",
    "parse_exec_anchor",
    "get_expert_from_signals",
    # validation
    "validate_bridge_state",
]
