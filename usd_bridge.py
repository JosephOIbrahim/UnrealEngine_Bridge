"""
usd_bridge.py

USD-Native Bridge Communication for CC↔UE5

This module provides functions to read/write USD files for bridge communication,
replacing the JSON-based state.json/answer.json protocol with USD composition semantics.

Key Functions:
- write_question_usda(): Write question to bridge_state.usda
- read_answer_usda(): Read answer from bridge_state.usda
- write_transition_usda(): Write transition state
- write_finale_usda(): Write finale with profile reference
- set_variant(): Set USD variant selection (state machine)

USD Advantages over JSON:
- VariantSets provide native state machine without code
- Composition semantics (LIVRPS) resolve conflicts automatically
- References pull in full cognitive substrate
- Schema validation built into USD

Requirements:
- pip install usd-core (OpenUSD Python bindings)
- Falls back to text-based USDA generation if pxr unavailable

Author: Translators Bridge v2.0.0
"""

from contextlib import contextmanager
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Optional, Dict, Any, List

logger = logging.getLogger("ue5-bridge.usd")

# Try to import OpenUSD Python bindings
try:
    from pxr import Usd, Sdf, UsdGeom
    HAS_PXR = True
except ImportError:
    HAS_PXR = False
    print("[USD Bridge] Warning: pxr not available, using text-based USDA generation")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_BRIDGE_PATH = Path.home() / ".translators"
BRIDGE_STATE_FILE = "bridge_state.usda"
BRIDGE_VERSION = "2.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# ATOMIC FILE I/O
# ═══════════════════════════════════════════════════════════════════════════════

@contextmanager
def _file_lock(file_path: Path, timeout: float = 5.0):
    """Advisory file lock using msvcrt on Windows, fcntl on Unix.

    Acquires an exclusive lock on a .lock file adjacent to the target.
    Falls back to no-op if locking is unavailable.
    """
    lock_path = file_path.with_suffix(file_path.suffix + ".lock")
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w", encoding="utf-8")
        try:
            import msvcrt
            import time
            deadline = time.monotonic() + timeout
            while True:
                try:
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        logger.warning("File lock timeout on %s", file_path.name)
                        break
                    time.sleep(0.05)
        except ImportError:
            try:
                import fcntl
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass  # No locking available — proceed without
        yield
    finally:
        if lock_fd is not None:
            try:
                try:
                    import msvcrt
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                except (ImportError, OSError):
                    pass
                lock_fd.close()
            except OSError:
                pass


def _atomic_write(file_path: Path, content: str) -> None:
    """Write content to file atomically via tmp + os.replace (NTFS-safe), with file locking."""
    parent = file_path.parent
    with _file_lock(file_path):
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp", prefix=".bridge_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(file_path))
        except BaseException:
            # Clean up temp file on any failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def _safe_read(file_path: Path, retries: int = 3, delay: float = 0.05) -> Optional[str]:
    """Read file with retry on Windows file-lock errors."""
    import time
    for attempt in range(retries):
        try:
            return file_path.read_text(encoding="utf-8")
        except (PermissionError, OSError):
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# CORE USD FUNCTIONS (using pxr when available)
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_bridge_path(bridge_path: Optional[Path]) -> Path:
    """Validate and resolve a bridge path, preventing path traversal.

    All bridge file operations MUST go through this function to ensure
    files stay within the expected bridge directory.
    """
    base_path = (bridge_path or DEFAULT_BRIDGE_PATH).resolve()
    allowed_root = DEFAULT_BRIDGE_PATH.resolve()
    try:
        base_path.relative_to(allowed_root)
    except ValueError:
        raise ValueError(
            f"Bridge path '{base_path}' is outside the allowed directory '{allowed_root}'. "
            f"Path traversal is not permitted."
        )
    return base_path


def get_bridge_file_path(bridge_path: Optional[Path] = None) -> Path:
    """Get path to bridge_state.usda."""
    base_path = _validate_bridge_path(bridge_path)
    return base_path / BRIDGE_STATE_FILE


def ensure_bridge_directory(bridge_path: Optional[Path] = None) -> Path:
    """Ensure bridge directory exists."""
    base_path = _validate_bridge_path(bridge_path)
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path


def get_timestamp() -> str:
    """Get ISO 8601 timestamp."""
    from datetime import timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION WRITING
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# ANSWER READING
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# VARIANT SETTING (STATE MACHINE)
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSITION WRITING
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# FINALE WRITING
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# READY/ACK HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIORAL SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# THINKINGMACHINES [He2025] BATCH-INVARIANCE COMPLIANT ANCHORS
# Same signals → Same routing → Same behavior
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY / TESTING
# ═══════════════════════════════════════════════════════════════════════════════

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


if __name__ == "__main__":
    # Test the bridge module
    print("USD Bridge Module Test")
    print("=" * 50)
    print(f"pxr available: {HAS_PXR}")
    print(f"Bridge path: {DEFAULT_BRIDGE_PATH}")
    print(f"Bridge file: {get_bridge_file_path()}")
    print()

    # Write a test question
    print("Writing test question...")
    write_question_usda(
        question_id="test_q1",
        text="When working on a complex problem, do you prefer to...",
        options=[
            {"label": "Break it into small pieces", "direction": "low"},
            {"label": "See the full picture first", "direction": "high"},
            {"label": "Jump between both", "direction": "mid"}
        ],
        index=0,
        total=8,
        scene="test_scene"
    )

    # Validate
    print("\nValidating bridge state...")
    validation = validate_bridge_state()
    print(f"Valid: {validation['valid']}")
    print(f"Sync status: {validation['sync_status']}")
    print(f"Message type: {validation['message_type']}")
    if validation["errors"]:
        print(f"Errors: {validation['errors']}")
    if validation["warnings"]:
        print(f"Warnings: {validation['warnings']}")

    print("\nDone!")
