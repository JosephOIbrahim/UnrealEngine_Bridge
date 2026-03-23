"""
transition.py

Transition, finale, and ready state writing for the USD bridge.

Provides:
- write_transition_usda: Write transition state to bridge_state.usda
- write_finale_usda: Write finale state to bridge_state.usda
- write_ready_usda: Write ready state to initialize bridge communication
"""

import re
from pathlib import Path
from typing import Optional

from .pxr_backend import HAS_PXR
from .io import (
    _atomic_write,
    _safe_read,
    ensure_bridge_directory,
    get_bridge_file_path,
    get_timestamp,
    BRIDGE_VERSION,
)
from .profile import generate_exec_anchor


# ===============================================================================
# TRANSITION WRITING
# ===============================================================================

def write_transition_usda(
    direction: str,
    next_scene: str,
    progress: float = 0.0,
    from_question_id: str = "",
    bridge_path: Optional[Path] = None
) -> bool:
    """
    Write transition state to bridge_state.usda.

    Args:
        direction: Transition direction (e.g., "forward", "back")
        next_scene: Target scene identifier
        progress: Progress value (0.0 - 1.0)
        from_question_id: Question we're transitioning from
        bridge_path: Optional custom bridge directory

    Returns:
        True if successful, False otherwise
    """
    file_path = get_bridge_file_path(bridge_path)

    if not file_path.exists():
        return False

    if HAS_PXR:
        return _write_transition_pxr(file_path, direction, next_scene, progress, from_question_id)
    else:
        return _write_transition_text(file_path, direction, next_scene, progress, from_question_id)


def _write_transition_pxr(
    file_path: Path,
    direction: str,
    next_scene: str,
    progress: float,
    from_question_id: str
) -> bool:
    """Write transition using pxr USD library."""
    try:
        from pxr import Usd

        stage = Usd.Stage.Open(str(file_path))
        root = stage.GetPrimAtPath("/BridgeState")

        # Set variants
        vsets = root.GetVariantSets()
        if vsets.HasVariantSet("sync_status"):
            vsets.GetVariantSet("sync_status").SetVariantSelection("transition")
        if vsets.HasVariantSet("message_type"):
            vsets.GetVariantSet("message_type").SetVariantSelection("transition")

        # Write transition data
        trans_prim = stage.GetPrimAtPath("/BridgeState/Transition")
        if trans_prim:
            trans_prim.GetAttribute("direction").Set(direction)
            trans_prim.GetAttribute("next_scene").Set(next_scene)
            trans_prim.GetAttribute("progress").Set(progress)
            trans_prim.GetAttribute("from_question_id").Set(from_question_id)

        stage.Save()
        return True

    except Exception as e:
        print(f"[USD Bridge] Error writing transition: {e}")
        return False


def _write_transition_text(
    file_path: Path,
    direction: str,
    next_scene: str,
    progress: float,
    from_question_id: str
) -> bool:
    """Write transition using text replacement (fallback)."""
    try:
        content = _safe_read(file_path)
        if content is None:
            return False

        # Update variants
        content = re.sub(
            r'(string sync_status = ")[^"]*(")',
            r'\g<1>transition\g<2>',
            content
        )
        content = re.sub(
            r'(string message_type = ")[^"]*(")',
            r'\g<1>transition\g<2>',
            content
        )

        # Update transition prim
        def escape(s: str) -> str:
            return s.replace('\\', '\\\\').replace('"', '\\"')

        trans_section = f'''def Xform "Transition" {{
        string direction = "{escape(direction)}"
        string next_scene = "{escape(next_scene)}"
        float progress = {progress}
        string from_question_id = "{escape(from_question_id)}"
    }}'''

        content = re.sub(
            r'def Xform "Transition"[^}]*\}',
            trans_section,
            content,
            flags=re.DOTALL
        )

        _atomic_write(file_path, content)
        return True

    except Exception as e:
        print(f"[USD Bridge] Error writing transition (text): {e}")
        return False


# ===============================================================================
# FINALE WRITING
# ===============================================================================

def write_finale_usda(
    usd_path: str,
    checksum: str,
    message: str = "Cognitive profile complete!",
    total_questions: int = 8,
    questions_answered: int = 8,
    bridge_path: Optional[Path] = None,
    expert: str = "Direct",
    paradigm: str = "Cortex",
    altitude: str = "Ground"
) -> bool:
    """
    Write finale state to bridge_state.usda.

    ThinkingMachines [He2025] compliant: Includes [EXEC:...] anchor with routing params.

    Args:
        usd_path: Path to the generated cognitive profile USD
        checksum: Profile checksum for verification
        message: Completion message
        total_questions: Total number of questions
        questions_answered: Number of questions actually answered
        bridge_path: Optional custom bridge directory
        expert: Final routed expert (for EXEC anchor)
        paradigm: Final paradigm (for EXEC anchor)
        altitude: Final altitude (for EXEC anchor)

    Returns:
        True if successful, False otherwise
    """
    # Generate ThinkingMachines-compliant EXEC anchor
    exec_anchor = generate_exec_anchor(
        checksum=checksum,
        expert=expert,
        paradigm=paradigm,
        altitude=altitude,
        verbosity="standard",
        think_depth="standard"
    )
    # Append anchor to message for traceability
    message_with_anchor = f"{message} {exec_anchor}"
    file_path = get_bridge_file_path(bridge_path)

    if not file_path.exists():
        return False

    if HAS_PXR:
        return _write_finale_pxr(
            file_path, usd_path, checksum, message_with_anchor, total_questions, questions_answered
        )
    else:
        return _write_finale_text(
            file_path, usd_path, checksum, message_with_anchor, total_questions, questions_answered
        )


def _write_finale_pxr(
    file_path: Path,
    usd_path: str,
    checksum: str,
    message: str,
    total_questions: int,
    questions_answered: int
) -> bool:
    """Write finale using pxr USD library."""
    try:
        from pxr import Usd

        stage = Usd.Stage.Open(str(file_path))
        root = stage.GetPrimAtPath("/BridgeState")

        # Set variants
        vsets = root.GetVariantSets()
        if vsets.HasVariantSet("sync_status"):
            vsets.GetVariantSet("sync_status").SetVariantSelection("complete")
        if vsets.HasVariantSet("message_type"):
            vsets.GetVariantSet("message_type").SetVariantSelection("finale")

        # Write finale data
        finale_prim = stage.GetPrimAtPath("/BridgeState/Finale")
        if finale_prim:
            finale_prim.GetAttribute("message").Set(message)
            finale_prim.GetAttribute("usd_path").Set(usd_path)
            finale_prim.GetAttribute("checksum").Set(checksum)
            finale_prim.GetAttribute("total_questions").Set(total_questions)
            finale_prim.GetAttribute("questions_answered").Set(questions_answered)

        stage.Save()
        return True

    except Exception as e:
        print(f"[USD Bridge] Error writing finale: {e}")
        return False


def _write_finale_text(
    file_path: Path,
    usd_path: str,
    checksum: str,
    message: str,
    total_questions: int,
    questions_answered: int
) -> bool:
    """Write finale using text replacement (fallback)."""
    try:
        content = _safe_read(file_path)
        if content is None:
            return False

        # Update variants
        content = re.sub(
            r'(string sync_status = ")[^"]*(")',
            r'\g<1>complete\g<2>',
            content
        )
        content = re.sub(
            r'(string message_type = ")[^"]*(")',
            r'\g<1>finale\g<2>',
            content
        )

        # Update finale prim
        def escape(s: str) -> str:
            return s.replace('\\', '\\\\').replace('"', '\\"')

        finale_section = f'''def Xform "Finale" {{
        string message = "{escape(message)}"
        string usd_path = "{escape(usd_path)}"
        string checksum = "{escape(checksum)}"
        int total_questions = {total_questions}
        int questions_answered = {questions_answered}
    }}'''

        content = re.sub(
            r'def Xform "Finale"[^}]*\}',
            finale_section,
            content,
            flags=re.DOTALL
        )

        _atomic_write(file_path, content)
        return True

    except Exception as e:
        print(f"[USD Bridge] Error writing finale (text): {e}")
        return False


# ===============================================================================
# READY STATE
# ===============================================================================

def write_ready_usda(
    total_questions: int = 8,
    first_scene: str = "",
    bridge_path: Optional[Path] = None
) -> Path:
    """
    Write ready state to initialize bridge communication.

    Args:
        total_questions: Number of questions in questionnaire
        first_scene: First scene identifier
        bridge_path: Optional custom bridge directory

    Returns:
        Path to the written USDA file
    """
    ensure_bridge_directory(bridge_path)
    file_path = get_bridge_file_path(bridge_path)
    timestamp = get_timestamp()

    # Write minimal ready state
    usda_content = f'''#usda 1.0
(
    defaultPrim = "BridgeState"
    doc = "CC↔UE5 Bridge Communication - Ready State"
)

def Xform "BridgeState" (
    kind = "assembly"
    variants = {{
        string sync_status = "idle"
        string message_type = "ready"
    }}
    prepend variantSets = ["sync_status", "message_type"]
    customData = {{
        string bridge_version = "{BRIDGE_VERSION}"
        string protocol = "USD-native"
        string generator = "UEBridge"
    }}
)
{{
    variantSet "sync_status" = {{
        "idle" {{ }}
        "question_pending" {{ double timeout_seconds = 300.0; string pending_since = "" }}
        "answer_received" {{ string received_at = "" }}
        "transition" {{ string transition_direction = "" }}
        "complete" {{ string completion_time = "" }}
        "error" {{ string error_message = ""; string error_code = "" }}
    }}

    variantSet "message_type" = {{
        "none" {{ }}
        "question" {{ }}
        "answer" {{ }}
        "transition" {{ }}
        "finale" {{ }}
        "ack" {{ }}
        "ready" {{ }}
    }}

    def Xform "Message" {{
        string type = ""
        int index = 0
        int total = {total_questions}
        string timestamp = ""
        string question_id = ""
        string text = ""
        string scene = ""
        string progress_display = "0/{total_questions}"
    }}

    def Xform "Options" {{
        def Xform "Option_0" {{ int index = 0; string label = ""; string direction = ""; string semantic_tag = "" }}
        def Xform "Option_1" {{ int index = 1; string label = ""; string direction = ""; string semantic_tag = "" }}
        def Xform "Option_2" {{ int index = 2; string label = ""; string direction = ""; string semantic_tag = "" }}
    }}

    def Xform "Answer" {{
        string question_id = ""
        int option_index = -1
        double response_time_ms = 0.0
        string selected_label = ""
        string selected_direction = ""
        string timestamp = ""
    }}

    def Xform "Transition" {{ string direction = ""; string next_scene = ""; float progress = 0.0; string from_question_id = "" }}
    def Xform "Finale" {{ string message = ""; string usd_path = ""; string checksum = ""; int total_questions = {total_questions}; int questions_answered = 0 }}

    def Xform "Ready" {{
        int total_questions = {total_questions}
        string first_scene = "{first_scene}"
        string bridge_version = "{BRIDGE_VERSION}"
        string protocol = "USD-native"
        string timestamp = "{timestamp}"
    }}

    def Xform "Ack" {{ bool ready = false; string ue_version = ""; string project = ""; string timestamp = "" }}
    def Xform "BehavioralSignals" {{
        double last_response_time_ms = 0.0
        double average_response_time_ms = 0.0
        int hesitation_count = 0
        bool long_hesitation_detected = false
        int rapid_click_count = 0
        int skip_count = 0
        int back_navigation_count = 0
        string detected_state = "focused"
        string recommended_expert = "Direct"
        string burnout_level = "GREEN"
        string momentum_phase = "cold_start"
    }}
    def Xform "CognitiveState" {{ string placeholder = "Reference to cognitive_profile.usda" }}
}}
'''

    _atomic_write(file_path, usda_content)
    return file_path
