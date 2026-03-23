"""
question.py

Question writing and answer reading for the USD bridge.

Provides:
- write_question_usda: Write question to bridge_state.usda
- _write_question_pxr: Write question using pxr USD library
- _write_question_text: Write question using text-based USDA generation
- _update_question_incremental: Incrementally update existing bridge_state.usda
- read_answer_usda: Read answer from bridge_state.usda
- _read_answer_pxr: Read answer using pxr USD library
- _read_answer_text: Read answer using text parsing
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .pxr_backend import HAS_PXR
from .io import (
    _atomic_write,
    _safe_read,
    ensure_bridge_directory,
    get_bridge_file_path,
    get_timestamp,
    BRIDGE_VERSION,
)


def write_question_usda(
    question_id: str,
    text: str,
    options: List[Dict[str, str]],
    index: int,
    total: int,
    scene: str = "",
    bridge_path: Optional[Path] = None
) -> Path:
    """
    Write a question to bridge_state.usda.

    Args:
        question_id: Unique identifier for the question (e.g., "load", "ground")
        text: Question text to display
        options: List of dicts with 'label' and 'direction' keys
        index: 0-based question index
        total: Total number of questions
        scene: Scene identifier for visual transitions
        bridge_path: Optional custom bridge directory

    Returns:
        Path to the written USDA file

    Example:
        write_question_usda(
            question_id="load",
            text="When working on a complex problem, do you prefer to...",
            options=[
                {"label": "Break it into small pieces", "direction": "low"},
                {"label": "See the full picture first", "direction": "high"},
                {"label": "Jump between both", "direction": "mid"}
            ],
            index=0,
            total=8
        )
    """
    ensure_bridge_directory(bridge_path)
    file_path = get_bridge_file_path(bridge_path)
    timestamp = get_timestamp()

    if HAS_PXR:
        return _write_question_pxr(
            file_path, question_id, text, options, index, total, scene, timestamp
        )
    else:
        return _write_question_text(
            file_path, question_id, text, options, index, total, scene, timestamp
        )


def _write_question_pxr(
    file_path: Path,
    question_id: str,
    text: str,
    options: List[Dict[str, str]],
    index: int,
    total: int,
    scene: str,
    timestamp: str
) -> Path:
    """Write question using pxr USD library."""
    from pxr import Usd

    # Create or open stage
    if file_path.exists():
        stage = Usd.Stage.Open(str(file_path))
    else:
        stage = Usd.Stage.CreateNew(str(file_path))
        stage.SetDefaultPrim(stage.DefinePrim("/BridgeState", "Xform"))

    root = stage.GetPrimAtPath("/BridgeState")

    # Set variants for state machine
    vsets = root.GetVariantSets()
    if vsets.HasVariantSet("sync_status"):
        vsets.GetVariantSet("sync_status").SetVariantSelection("question_pending")
    if vsets.HasVariantSet("message_type"):
        vsets.GetVariantSet("message_type").SetVariantSelection("question")

    # Write message data
    msg_prim = stage.GetPrimAtPath("/BridgeState/Message")
    if msg_prim:
        msg_prim.GetAttribute("type").Set("question")
        msg_prim.GetAttribute("index").Set(index)
        msg_prim.GetAttribute("total").Set(total)
        msg_prim.GetAttribute("timestamp").Set(timestamp)
        msg_prim.GetAttribute("question_id").Set(question_id)
        msg_prim.GetAttribute("text").Set(text)
        msg_prim.GetAttribute("scene").Set(scene)
        msg_prim.GetAttribute("progress_display").Set(f"{index + 1}/{total}")

    # Write options
    for i, opt in enumerate(options[:3]):
        opt_prim = stage.GetPrimAtPath(f"/BridgeState/Options/Option_{i}")
        if opt_prim:
            opt_prim.GetAttribute("index").Set(i)
            opt_prim.GetAttribute("label").Set(opt.get("label", ""))
            opt_prim.GetAttribute("direction").Set(opt.get("direction", ""))
            opt_prim.GetAttribute("semantic_tag").Set(opt.get("semantic_tag", ""))

    stage.Save()
    return file_path


def _update_question_incremental(
    file_path: Path,
    question_id: str,
    text: str,
    options: List[Dict[str, str]],
    index: int,
    total: int,
    scene: str,
    timestamp: str
) -> bool:
    """Incrementally update an existing bridge_state.usda (patch, not rewrite).

    Returns True if successful, False if full rewrite needed (file missing/corrupt).
    """
    content = _safe_read(file_path)
    if content is None or 'def Xform "Message"' not in content:
        return False

    def esc(s: str) -> str:
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    # 1. Update variants
    content = re.sub(r'(string sync_status = ")[^"]*(")', r'\g<1>question_pending\g<2>', content)
    content = re.sub(r'(string message_type = ")[^"]*(")', r'\g<1>question\g<2>', content)

    # 2. Replace Message prim
    new_message = f'''def Xform "Message" {{
        string type = "question"
        int index = {index}
        int total = {total}
        string timestamp = "{timestamp}"
        string question_id = "{esc(question_id)}"
        string text = "{esc(text)}"
        string scene = "{esc(scene)}"
        string progress_display = "{index + 1}/{total}"
    }}'''
    content = re.sub(r'def Xform "Message"[^}]*\}', new_message, content, flags=re.DOTALL)

    # 3. Replace Options prim (rebuild with new options)
    options_inner = ""
    for i, opt in enumerate(options[:3]):
        label = esc(opt.get("label", ""))
        direction = esc(opt.get("direction", ""))
        semantic_tag = esc(opt.get("semantic_tag", ""))
        options_inner += f'''
        def Xform "Option_{i}" {{
            int index = {i}
            string label = "{label}"
            string direction = "{direction}"
            string semantic_tag = "{semantic_tag}"
        }}
'''
    new_options = f'def Xform "Options" {{{options_inner}    }}'
    content = re.sub(r'def Xform "Options"[^}]*(?:\{[^}]*\}[^}]*)*\}', new_options, content, flags=re.DOTALL)

    # 4. Reset answer prim for new question
    new_answer = '''def Xform "Answer" {
        string question_id = ""
        int option_index = -1
        double response_time_ms = 0.0
        string selected_label = ""
        string selected_direction = ""
        string timestamp = ""
    }'''
    content = re.sub(r'def Xform "Answer"[^}]*\}', new_answer, content, flags=re.DOTALL)

    _atomic_write(file_path, content)
    return True


def _write_question_text(
    file_path: Path,
    question_id: str,
    text: str,
    options: List[Dict[str, str]],
    index: int,
    total: int,
    scene: str,
    timestamp: str
) -> Path:
    """Write question using text-based USDA generation (fallback when pxr unavailable).

    Tries incremental update first; falls back to full rewrite if file doesn't exist.
    """
    # Try incremental update if file already exists
    if file_path.exists():
        if _update_question_incremental(file_path, question_id, text, options, index, total, scene, timestamp):
            return file_path

    # Escape strings for USDA
    def escape_usda_string(s: str) -> str:
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    options_usda = ""
    for i, opt in enumerate(options[:3]):
        label = escape_usda_string(opt.get("label", ""))
        direction = escape_usda_string(opt.get("direction", ""))
        semantic_tag = escape_usda_string(opt.get("semantic_tag", ""))
        options_usda += f'''
        def Xform "Option_{i}" {{
            int index = {i}
            string label = "{label}"
            string direction = "{direction}"
            string semantic_tag = "{semantic_tag}"
        }}
'''

    usda_content = f'''#usda 1.0
(
    defaultPrim = "BridgeState"
    doc = "CC↔UE5 Bridge Communication - Generated {timestamp}"
)

def Xform "BridgeState" (
    kind = "assembly"
    variants = {{
        string sync_status = "question_pending"
        string message_type = "question"
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
        "question_pending" {{
            double timeout_seconds = 300.0
            string pending_since = "{timestamp}"
        }}
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
        string type = "question"
        int index = {index}
        int total = {total}
        string timestamp = "{timestamp}"
        string question_id = "{escape_usda_string(question_id)}"
        string text = "{escape_usda_string(text)}"
        string scene = "{escape_usda_string(scene)}"
        string progress_display = "{index + 1}/{total}"
    }}

    def Xform "Options" {{
{options_usda}
    }}

    def Xform "Answer" {{
        string question_id = ""
        int option_index = -1
        double response_time_ms = 0.0
        string selected_label = ""
        string selected_direction = ""
        string timestamp = ""
    }}

    def Xform "Transition" {{
        string direction = ""
        string next_scene = ""
        float progress = 0.0
        string from_question_id = ""
    }}

    def Xform "Finale" {{
        string message = ""
        string usd_path = ""
        string checksum = ""
        int total_questions = {total}
        int questions_answered = 0
    }}

    def Xform "Ready" {{
        int total_questions = {total}
        string first_scene = "{escape_usda_string(scene)}"
        string bridge_version = "{BRIDGE_VERSION}"
        string protocol = "USD-native"
    }}

    def Xform "Ack" {{
        bool ready = false
        string ue_version = ""
        string project = ""
        string timestamp = ""
    }}

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

    def Xform "CognitiveState" {{
        string placeholder = "Reference to cognitive_profile.usda"
    }}
}}
'''

    _atomic_write(file_path, usda_content)
    return file_path


# ===============================================================================
# ANSWER READING
# ===============================================================================

def read_answer_usda(bridge_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Read answer from bridge_state.usda.

    Returns:
        Dict with answer data or None if no answer available.
        {
            "question_id": str,
            "option_index": int,
            "response_time_ms": float,
            "selected_label": str,
            "selected_direction": str,
            "timestamp": str
        }
    """
    file_path = get_bridge_file_path(bridge_path)

    if not file_path.exists():
        return None

    if HAS_PXR:
        return _read_answer_pxr(file_path)
    else:
        return _read_answer_text(file_path)


def _read_answer_pxr(file_path: Path) -> Optional[Dict[str, Any]]:
    """Read answer using pxr USD library."""
    try:
        from pxr import Usd

        stage = Usd.Stage.Open(str(file_path))

        # Check if answer is pending
        root = stage.GetPrimAtPath("/BridgeState")
        vsets = root.GetVariantSets()
        if vsets.HasVariantSet("sync_status"):
            status = vsets.GetVariantSet("sync_status").GetVariantSelection()
            if status != "answer_received":
                return None

        # Read answer data
        answer_prim = stage.GetPrimAtPath("/BridgeState/Answer")
        if not answer_prim:
            return None

        question_id = answer_prim.GetAttribute("question_id").Get()
        option_index = answer_prim.GetAttribute("option_index").Get()

        if option_index < 0:
            return None

        return {
            "question_id": question_id,
            "option_index": option_index,
            "response_time_ms": answer_prim.GetAttribute("response_time_ms").Get(),
            "selected_label": answer_prim.GetAttribute("selected_label").Get(),
            "selected_direction": answer_prim.GetAttribute("selected_direction").Get(),
            "timestamp": answer_prim.GetAttribute("timestamp").Get(),
        }

    except Exception as e:
        print(f"[USD Bridge] Error reading answer: {e}")
        return None


def _read_answer_text(file_path: Path) -> Optional[Dict[str, Any]]:
    """Read answer using text parsing (fallback when pxr unavailable)."""
    try:
        content = _safe_read(file_path)
        if content is None:
            return None

        # Check sync_status variant
        sync_match = re.search(r'string sync_status = "([^"]*)"', content)
        if not sync_match or sync_match.group(1) != "answer_received":
            return None

        # Find Answer prim section
        answer_section_match = re.search(
            r'def Xform "Answer"[^{]*\{([^}]*)\}',
            content,
            re.DOTALL
        )
        if not answer_section_match:
            return None

        answer_section = answer_section_match.group(1)

        # Parse attributes
        def get_attr(pattern: str, default: Any = "") -> Any:
            match = re.search(pattern, answer_section)
            return match.group(1) if match else default

        question_id = get_attr(r'string question_id = "([^"]*)"')
        option_index = int(get_attr(r'int option_index = (-?\d+)', "-1"))

        if option_index < 0:
            return None

        return {
            "question_id": question_id,
            "option_index": option_index,
            "response_time_ms": float(get_attr(r'double response_time_ms = ([\d.]+)', "0.0")),
            "selected_label": get_attr(r'string selected_label = "([^"]*)"'),
            "selected_direction": get_attr(r'string selected_direction = "([^"]*)"'),
            "timestamp": get_attr(r'string timestamp = "([^"]*)"'),
        }

    except Exception as e:
        print(f"[USD Bridge] Error reading answer (text): {e}")
        return None
