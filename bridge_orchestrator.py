#!/usr/bin/env python3
"""
Translators Bridge Orchestrator v2.0.0
Drives the cognitive profiling questionnaire through USD-native or JSON file-based bridge.

USD-Native Communication (v2.0.0):
- Uses bridge_state.usda with VariantSets as state machine
- Behavioral signals enable ADHD_MoE expert routing
- Full cognitive substrate integration via USD composition

Legacy JSON Communication (v1.0.0):
- Uses state.json / answer.json for backward compatibility
- Falls back to JSON if USD module unavailable

Usage:
    python bridge_orchestrator.py           # Run with USD (fallback to JSON)
    python bridge_orchestrator.py --json    # Force JSON mode
    python bridge_orchestrator.py --test    # Write test question and exit
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Try to import USD bridge module
try:
    from usd_bridge import (
        write_question_usda,
        read_answer_usda,
        write_transition_usda,
        write_finale_usda,
        write_ready_usda,
        read_ack_usda,
        read_behavioral_signals,
        set_variant,
        validate_bridge_state,
        get_bridge_file_path,
        ensure_bridge_directory,
        compute_checksum as _usd_compute_checksum,
    )
    HAS_USD_BRIDGE = True
except ImportError:
    HAS_USD_BRIDGE = False
    print("[Bridge] USD bridge module not available, using JSON mode")

# ============================================
#  Configuration
# ============================================

BRIDGE_DIR = Path.home() / ".translators"
STATE_FILE = BRIDGE_DIR / "state.json"
ANSWER_FILE = BRIDGE_DIR / "answer.json"
ACK_FILE = BRIDGE_DIR / "ack.json"
PROFILE_FILE = BRIDGE_DIR / "cognitive_profile.usda"

POLL_INTERVAL_MIN = 0.05   # 50ms — fast start
POLL_INTERVAL_MAX = 0.5    # 500ms — ceiling
POLL_BACKOFF_FACTOR = 1.5  # multiply interval each miss
BRIDGE_VERSION = "2.0.0"
HEARTBEAT_INTERVAL = 5.0   # seconds between heartbeat writes
HEARTBEAT_FILE = BRIDGE_DIR / "heartbeat.json"

# USD mode flag (set by CLI args or auto-detect)
USE_USD_MODE = HAS_USD_BRIDGE

# ============================================
#  The 8 Calibration Questions
#  Updated for USD Cognitive Substrate v4.3.0
#  Each question maps to a cognitive dimension (0.0-1.0)
# ============================================

QUESTIONS = [
    {
        "id": "load",
        "text": "How much can you hold at once\nbefore it starts to blur?",
        "dimension": "cognitive_density",  # USD dimension mapping
        "scene": "forest_edge",
        "options": [
            {"label": "Not much. One thing at a time.", "direction": "low", "trait": "focused", "value": 0.2},
            {"label": "Quite a lot. I can hold complexity.", "direction": "high", "trait": "parallel", "value": 0.8},
            {"label": "It varies. Some days more than others.", "direction": "mid", "trait": "adaptive", "value": 0.5}
        ]
    },
    {
        "id": "pace",
        "text": "When you're working on something\nthat matters to you...",
        "dimension": "processing_pace",
        "scene": "forest_path",
        "options": [
            {"label": "I go deep. Hours disappear.", "direction": "low", "trait": "hyperfocus", "value": 0.2},
            {"label": "I take breaks. Steady rhythm.", "direction": "high", "trait": "sustainable", "value": 0.8},
            {"label": "Bursts of intensity, then rest.", "direction": "mid", "trait": "cyclical", "value": 0.5}
        ]
    },
    {
        "id": "uncertainty",
        "text": "When facing the unknown...",
        "dimension": "uncertainty_tolerance",
        "scene": "misty_clearing",
        "options": [
            {"label": "I need a plan before I move.", "direction": "low", "trait": "structured", "value": 0.2},
            {"label": "I explore. The path reveals itself.", "direction": "high", "trait": "emergent", "value": 0.8},
            {"label": "I sketch a direction, then adapt.", "direction": "mid", "trait": "iterative", "value": 0.5}
        ]
    },
    {
        "id": "feedback",
        "text": "How do you know\nyou're on the right track?",
        "dimension": "guidance_frequency",
        "scene": "ancient_tree",
        "options": [
            {"label": "External validation. Others confirm.", "direction": "high", "trait": "external", "value": 0.8},
            {"label": "Internal sense. I just know.", "direction": "low", "trait": "internal", "value": 0.2},
            {"label": "Results. The work speaks.", "direction": "mid", "trait": "empirical", "value": 0.5}
        ]
    },
    {
        "id": "recovery",
        "text": "After intense effort,\nwhat restores you?",
        "dimension": "home_altitude",  # Grounding vs elevated perspective
        "scene": "quiet_stream",
        "options": [
            {"label": "Solitude. Silence. Nothing.", "direction": "low", "trait": "solitary", "value": 0.2},
            {"label": "Connection. People. Talk.", "direction": "high", "trait": "social", "value": 0.8},
            {"label": "Movement. Change of scene.", "direction": "mid", "trait": "kinetic", "value": 0.5}
        ]
    },
    {
        "id": "starting",
        "text": "Beginning something new...",
        "dimension": "default_paradigm",
        "scene": "dawn_ridge",
        "options": [
            {"label": "Is hard. I circle before landing.", "direction": "low", "trait": "cautious", "value": 0.2},
            {"label": "Is exciting. I dive in.", "direction": "high", "trait": "eager", "value": 0.8},
            {"label": "Depends on whether I chose it.", "direction": "mid", "trait": "autonomous", "value": 0.5}
        ]
    },
    {
        "id": "completion",
        "text": "When something is 'done'...",
        "dimension": "feedback_style",
        "scene": "summit_view",
        "options": [
            {"label": "I know exactly when. Clean edges.", "direction": "low", "trait": "definitive", "value": 0.2},
            {"label": "It's never quite done. Always more.", "direction": "high", "trait": "perfectionist", "value": 0.8},
            {"label": "Done enough to ship. Move on.", "direction": "mid", "trait": "pragmatic", "value": 0.5}
        ]
    },
    {
        "id": "essence",
        "text": "At your core,\nyou are someone who...",
        "dimension": "tangent_tolerance",
        "scene": "mirror_pool",
        "options": [
            {"label": "Builds. Makes things exist.", "direction": "low", "trait": "builder", "value": 0.2},
            {"label": "Connects. Sees relationships.", "direction": "mid", "trait": "connector", "value": 0.5},
            {"label": "Discovers. Follows curiosity.", "direction": "high", "trait": "explorer", "value": 0.8}
        ]
    }
]

# ============================================
#  Display
# ============================================

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    DIM = '\033[90m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class HeartbeatWriter:
    """Background thread that writes heartbeat.json every HEARTBEAT_INTERVAL seconds."""

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                heartbeat = {
                    "timestamp": datetime.now().isoformat(),
                    "pid": __import__("os").getpid(),
                    "bridge_version": BRIDGE_VERSION,
                    "alive": True,
                }
                # Write atomically via tmp + replace
                import tempfile, os
                fd, tmp = tempfile.mkstemp(dir=str(BRIDGE_DIR), suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(heartbeat, f)
                os.replace(tmp, str(HEARTBEAT_FILE))
            except Exception:
                pass  # Best-effort — don't crash the bridge
            self._stop_event.wait(HEARTBEAT_INTERVAL)


def _adaptive_sleep(poll_interval: float) -> float:
    """Sleep and return the next (backed-off) interval."""
    time.sleep(poll_interval)
    return min(poll_interval * POLL_BACKOFF_FACTOR, POLL_INTERVAL_MAX)


def clear_screen():
    try:
        import os
        if sys.stdout.isatty():
            os.system('cls' if os.name == 'nt' else 'clear')
        else:
            print("\n" + "=" * 60 + "\n")
    except Exception:
        pass

def print_banner():
    clear_screen()
    print(f"""
{Colors.CYAN}  +-----------------------------------------------------------+
  |                                                           |
  |   {Colors.BOLD}THE TRANSLATORS{Colors.RESET}{Colors.CYAN} -- Cognitive Profile Orchestrator       |
  |                                                           |
  |   Waiting for UE5 connection...                           |
  |                                                           |
  +-----------------------------------------------------------+{Colors.RESET}
""")

def print_progress(current: int, total: int):
    filled = int((current / total) * 30)
    bar = "#" * filled + "." * (30 - filled)
    print(f"\n  {Colors.CYAN}Progress: [{bar}] {current}/{total}{Colors.RESET}")

def print_question(q: dict, index: int, total: int):
    clear_screen()
    print_progress(index, total)
    print(f"""
{Colors.BOLD}  Question {index + 1} of {total}{Colors.RESET}
{Colors.DIM}  Scene: {q['scene']}{Colors.RESET}

{Colors.CYAN}  {q['text'].replace(chr(10), chr(10) + '  ')}{Colors.RESET}

  Waiting for answer in UE5...
""")

# ============================================
#  Bridge Communication
# ============================================

def _atomic_write_json(file_path: Path, data: dict) -> None:
    """Write JSON atomically via tmp + os.replace."""
    fd, tmp = tempfile.mkstemp(dir=str(file_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, str(file_path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ensure_bridge_dir():
    """Create bridge directory if it doesn't exist."""
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    return BRIDGE_DIR.exists()

def clear_bridge_files():
    """Remove stale communication files."""
    for f in [STATE_FILE, ANSWER_FILE, ACK_FILE, HEARTBEAT_FILE]:
        if f.exists():
            f.unlink()

def write_question(question: dict, index: int, total: int):
    """Write question to bridge_state.usda (USD) or state.json (JSON fallback)."""
    global USE_USD_MODE

    if USE_USD_MODE and HAS_USD_BRIDGE:
        # USD-native mode
        try:
            write_question_usda(
                question_id=question["id"],
                text=question["text"],
                options=[
                    {
                        "label": opt["label"],
                        "direction": opt["direction"],
                        "semantic_tag": opt.get("trait", "")
                    }
                    for opt in question["options"]
                ],
                index=index,
                total=total,
                scene=question.get("scene", ""),
                bridge_path=BRIDGE_DIR
            )
            return
        except Exception as e:
            print(f"{Colors.YELLOW}  USD write failed, falling back to JSON: {e}{Colors.RESET}")
            USE_USD_MODE = False

    # JSON fallback
    state = {
        "type": "question",
        "index": index,
        "total": total,
        "id": question["id"],
        "text": question["text"],
        "scene": question["scene"],
        "dimension": question.get("dimension", ""),  # Include dimension for profile
        "options": [
            {
                "index": i,
                "label": opt["label"],
                "direction": opt["direction"],
                "value": opt.get("value", 0.5)  # Include numeric value
            }
            for i, opt in enumerate(question["options"])
        ],
        "timestamp": datetime.now().isoformat(),
        "bridge_version": BRIDGE_VERSION
    }

    _atomic_write_json(STATE_FILE, state)

def wait_for_answer(question: dict = None, timeout: float = 300.0) -> Optional[dict]:
    """Wait for answer from UE5 (USD or JSON mode) with adaptive backoff polling."""
    global USE_USD_MODE
    start = time.time()
    poll_interval = POLL_INTERVAL_MIN  # Start fast, back off on misses

    while time.time() - start < timeout:
        # Try USD mode first
        if USE_USD_MODE and HAS_USD_BRIDGE:
            try:
                answer_data = read_answer_usda(BRIDGE_DIR)
                if answer_data and answer_data.get("option_index", -1) >= 0:
                    # Match question_id if provided
                    if question and answer_data.get("question_id") != question.get("id"):
                        poll_interval = _adaptive_sleep(poll_interval)
                        continue

                    # Clear answer state
                    set_variant("sync_status", "idle", BRIDGE_DIR)

                    # Read behavioral signals for ADHD_MoE routing
                    signals = read_behavioral_signals(BRIDGE_DIR)
                    if signals:
                        answer_data["behavioral_signals"] = signals

                    # Map to legacy format for compatibility
                    return {
                        "type": "answer",
                        "question_id": answer_data.get("question_id", ""),
                        "option_index": answer_data.get("option_index", 0),
                        "response_time_ms": answer_data.get("response_time_ms", 0),
                        "answer": {
                            "question_id": answer_data.get("question_id", ""),
                            "option_index": answer_data.get("option_index", 0),
                            "response_time_ms": answer_data.get("response_time_ms", 0),
                        },
                        "behavioral_signals": answer_data.get("behavioral_signals", {})
                    }
            except Exception as e:
                if time.time() - start < 5:  # Only log once at start
                    print(f"{Colors.DIM}  USD read: {e}{Colors.RESET}")

        # JSON fallback
        if ANSWER_FILE.exists():
            try:
                with open(ANSWER_FILE, 'r', encoding='utf-8') as f:
                    answer = json.load(f)
                # Clear the answer file after reading
                ANSWER_FILE.unlink()
                return answer
            except (json.JSONDecodeError, IOError):
                pass

        poll_interval = _adaptive_sleep(poll_interval)

    return None

def write_transition(direction: str, next_scene: str, progress: float = 0.0, from_question_id: str = ""):
    """Write transition state for UE5 (USD or JSON mode)."""
    global USE_USD_MODE

    if USE_USD_MODE and HAS_USD_BRIDGE:
        try:
            write_transition_usda(
                direction=direction,
                next_scene=next_scene,
                progress=progress,
                from_question_id=from_question_id,
                bridge_path=BRIDGE_DIR
            )
            return
        except Exception as e:
            print(f"{Colors.DIM}  USD transition failed: {e}{Colors.RESET}")

    # JSON fallback
    state = {
        "type": "transition",
        "direction": direction,
        "next_scene": next_scene,
        "progress": progress,
        "from_question_id": from_question_id,
        "timestamp": datetime.now().isoformat(),
        "bridge_version": BRIDGE_VERSION
    }

    _atomic_write_json(STATE_FILE, state)


def write_finale(profile_path: str, checksum: str = "", total_answered: int = 8):
    """Write finale state for UE5 (USD or JSON mode)."""
    global USE_USD_MODE

    if USE_USD_MODE and HAS_USD_BRIDGE:
        try:
            write_finale_usda(
                usd_path=profile_path,
                checksum=checksum,
                message="Cognitive profile complete! Your profile is ready for AI consumption.",
                total_questions=len(QUESTIONS),
                questions_answered=total_answered,
                bridge_path=BRIDGE_DIR
            )
            return
        except Exception as e:
            print(f"{Colors.DIM}  USD finale failed: {e}{Colors.RESET}")

    # JSON fallback
    state = {
        "type": "finale",
        "usd_path": profile_path,
        "checksum": checksum,
        "total_questions": len(QUESTIONS),
        "questions_answered": total_answered,
        "message": "Cognitive profile complete!",
        "timestamp": datetime.now().isoformat(),
        "bridge_version": BRIDGE_VERSION
    }

    _atomic_write_json(STATE_FILE, state)

# ============================================
#  Profile Generation (USD Cognitive Substrate v4.3.0)
# ============================================

def compute_checksum(dimensions: dict) -> str:
    """Compute deterministic checksum for profile. Delegates to usd_bridge canonical implementation."""
    if HAS_USD_BRIDGE:
        return _usd_compute_checksum(dimensions)
    # Inline fallback when usd_bridge unavailable
    sorted_dims = sorted(dimensions.items())
    serialized = "TRL_v1|" + "|".join(f"{k}:{v}" for k, v in sorted_dims)
    hash_val = 5381
    for char in serialized:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
        hash_val &= 0xFFFFFFFF
    return format(hash_val, '08x')


def generate_profile(answers: list) -> dict:
    """Generate cognitive profile from answers."""
    traits = {}       # Legacy: trait names
    dimensions = {}   # USD: numeric values (0.0-1.0)

    for i, answer in enumerate(answers):
        q = QUESTIONS[i]
        option_idx = answer.get("option_index", 0)
        if "answer" in answer:
            option_idx = answer["answer"].get("option_index", option_idx)

        if 0 <= option_idx < len(q["options"]):
            option = q["options"][option_idx]
            dimension_name = q.get("dimension", q["id"])
            traits[q["id"]] = option.get("trait", "")
            dimensions[dimension_name] = option.get("value", 0.5)

    return {
        "traits": traits,
        "dimensions": dimensions,
        "version": "TRL_v1"
    }

def export_usda(profile: dict, answers: list) -> tuple:
    """Export profile as USDA file (USD Cognitive Substrate v4.3.0 format)."""
    dimensions = profile.get("dimensions", {})
    traits = profile.get("traits", {})
    checksum = compute_checksum(dimensions)
    timestamp = datetime.now().isoformat()

    # Build answer prims
    answer_prims = []
    for i, answer in enumerate(answers):
        q = QUESTIONS[i]
        option_idx = answer.get("option_index", 0)
        if "answer" in answer:
            option_idx = answer["answer"].get("option_index", option_idx)
        response_time = answer.get("response_time_ms", 0)
        if "answer" in answer:
            response_time = answer["answer"].get("response_time_ms", response_time)

        if 0 <= option_idx < len(q["options"]):
            option = q["options"][option_idx]
            answer_prims.append(f'''
        def Xform "{q['id']}" {{
            int option_index = {option_idx}
            string value = "{option.get('direction', '')}"
            string trait = "{option.get('trait', '')}"
            float response_time = {response_time}
        }}''')

    usda_content = f'''#usda 1.0
(
    defaultPrim = "CognitiveSubstrate"
    doc = """Cognitive Profile Generated by The Translators v{BRIDGE_VERSION}
    USD Cognitive Substrate v4.3.0 compliant
    Checksum: {checksum}
    Generated: {timestamp}
    """
)

def Xform "CognitiveSubstrate" (
    kind = "component"
    customData = {{
        string generator = "UEBridge"
        string version = "{profile.get('version', 'TRL_v1')}"
        string checksum = "{checksum}"
        string generated = "{timestamp}"
        string translators_anchor = "[TRANSLATORS:{checksum}]"
    }}
)
{{
    # === PROFILE LAYER ===
    # Cognitive dimensions (0.0 - 1.0) for AI consumption
    # Maps to USD Cognitive Substrate L1 (Profile)

    def Xform "Profile" (
        doc = "Cognitive profile dimensions derived from questionnaire"
    )
    {{
        float cognitive_density = {dimensions.get("cognitive_density", 0.5)}
        float home_altitude = {dimensions.get("home_altitude", 0.5)}
        float guidance_frequency = {dimensions.get("guidance_frequency", 0.5)}
        float default_paradigm = {dimensions.get("default_paradigm", 0.5)}
        float feedback_style = {dimensions.get("feedback_style", 0.5)}
        float uncertainty_tolerance = {dimensions.get("uncertainty_tolerance", 0.5)}
        float processing_pace = {dimensions.get("processing_pace", 0.5)}
        float tangent_tolerance = {dimensions.get("tangent_tolerance", 0.5)}
    }}

    # === SESSION LAYER ===
    # Runtime state (L13 in full substrate)

    def Xform "Session" {{
        string session_id = "{checksum[:8]}"
        int questions_answered = {len(answers)}
        float completion = 1.0
        string checksum = "{checksum}"
        string active_mode = "calibrated"
    }}

    # === TRAITS LAYER ===
    # Human-readable trait labels (legacy compatibility)

    def Xform "Traits" (
        doc = "Human-readable trait labels from questionnaire"
    )
    {{
        string load = "{traits.get('load', '')}"
        string pace = "{traits.get('pace', '')}"
        string uncertainty = "{traits.get('uncertainty', '')}"
        string feedback = "{traits.get('feedback', '')}"
        string recovery = "{traits.get('recovery', '')}"
        string starting = "{traits.get('starting', '')}"
        string completion = "{traits.get('completion', '')}"
        string essence = "{traits.get('essence', '')}"
    }}

    # === ANSWERS LAYER ===
    # Raw answer data for audit trail

    def Xform "Answers" (
        doc = "Individual question responses"
    )
    {{
{"".join(answer_prims)}
    }}
}}
'''

    # Write file atomically
    fd, tmp = tempfile.mkstemp(dir=str(PROFILE_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(usda_content)
        os.replace(tmp, str(PROFILE_FILE))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return str(PROFILE_FILE), checksum

# ============================================
#  Main Orchestration
# ============================================

def initialize_usd_bridge():
    """Initialize USD bridge if available."""
    global USE_USD_MODE

    if not HAS_USD_BRIDGE:
        print(f"  {Colors.DIM}USD bridge not available, using JSON mode{Colors.RESET}")
        USE_USD_MODE = False
        return False

    try:
        ensure_bridge_directory(BRIDGE_DIR)
        write_ready_usda(
            total_questions=len(QUESTIONS),
            first_scene=QUESTIONS[0]["scene"] if QUESTIONS else "",
            bridge_path=BRIDGE_DIR
        )
        validation = validate_bridge_state(BRIDGE_DIR)
        if validation["valid"]:
            print(f"  {Colors.GREEN}[OK]{Colors.RESET} USD bridge initialized")
            USE_USD_MODE = True
            return True
        else:
            print(f"  {Colors.YELLOW}USD validation failed: {validation['errors']}{Colors.RESET}")
            USE_USD_MODE = False
            return False
    except Exception as e:
        print(f"  {Colors.YELLOW}USD init failed: {e}{Colors.RESET}")
        USE_USD_MODE = False
        return False


def run_questionnaire(force_json: bool = False):
    """Run the full questionnaire flow."""
    global USE_USD_MODE

    print_banner()

    # Setup
    if not ensure_bridge_dir():
        print(f"{Colors.RED}  ERROR: Could not create bridge directory{Colors.RESET}")
        return False

    clear_bridge_files()
    answers = []
    total = len(QUESTIONS)

    # Start heartbeat writer
    heartbeat = HeartbeatWriter()
    heartbeat.start()

    # Initialize USD bridge (unless JSON forced)
    if force_json:
        USE_USD_MODE = False
        print(f"  {Colors.DIM}JSON mode forced{Colors.RESET}")
    else:
        initialize_usd_bridge()

    # Write "ready" state so UE5 knows we're here
    if not USE_USD_MODE:
        ready_state = {
            "$schema": "translators-state-v1",
            "type": "ready",
            "total_questions": total,
            "first_scene": QUESTIONS[0]["scene"] if QUESTIONS else "",
            "timestamp": datetime.now().isoformat(),
            "bridge_version": BRIDGE_VERSION
        }
        _atomic_write_json(STATE_FILE, ready_state)

    mode_str = "USD" if USE_USD_MODE else "JSON"
    print(f"\n  {Colors.GREEN}<={Colors.RESET} Bridge ready at {BRIDGE_DIR}")
    print(f"  {Colors.DIM}Mode: {mode_str} | Press Play in UE5 to begin...{Colors.RESET}\n")

    # Wait for UE5 acknowledgment (adaptive polling)
    print(f"  Waiting for UE5 acknowledgment...")
    ack_received = False
    ack_start = time.time()
    ack_poll = POLL_INTERVAL_MIN
    while time.time() - ack_start < 120:
        if ANSWER_FILE.exists():
            try:
                with open(ANSWER_FILE, 'r', encoding='utf-8') as f:
                    ack = json.load(f)
                if ack.get("type") == "ack":
                    ANSWER_FILE.unlink()
                    ack_received = True
                    print(f"  {Colors.GREEN}<={Colors.RESET} UE5 connected! Starting questionnaire...\n")
                    break
            except (json.JSONDecodeError, IOError):
                pass
        ack_poll = _adaptive_sleep(ack_poll)

    if not ack_received:
        print(f"  {Colors.YELLOW}No ack received, starting anyway...{Colors.RESET}\n")

    time.sleep(1)

    # Run through questions
    for i, question in enumerate(QUESTIONS):
        print_question(question, i, total)

        # Send question to UE5
        write_question(question, i, total)

        # Wait for answer (pass question for USD mode verification)
        answer = wait_for_answer(question=question)

        if answer is None:
            print(f"\n{Colors.YELLOW}  Timeout waiting for answer. Exiting.{Colors.RESET}")
            return False

        answers.append(answer)

        # Log behavioral signals if available (ADHD_MoE routing)
        if "behavioral_signals" in answer:
            signals = answer["behavioral_signals"]
            state = signals.get("detected_state", "focused")
            burnout = signals.get("burnout_level", "GREEN")
            if state != "focused" or burnout != "GREEN":
                print(f"  {Colors.DIM}Behavioral: {state} / {burnout}{Colors.RESET}")

        # Send transition (except for last question)
        if i < total - 1:
            option_idx = answer.get("option_index", 0)
            if "answer" in answer:
                option_idx = answer["answer"].get("option_index", option_idx)
            direction = question["options"][option_idx]["direction"]
            next_scene = QUESTIONS[i + 1]["scene"]
            progress = (i + 1) / total
            write_transition(direction, next_scene, progress, question["id"])
            time.sleep(1)  # Brief pause for transition

    # Generate and export profile
    clear_screen()
    print(f"""
{Colors.CYAN}  +-----------------------------------------------------------+
  |                                                           |
  |   {Colors.BOLD}PROFILE COMPLETE{Colors.RESET}{Colors.CYAN}                                        |
  |                                                           |
  +-----------------------------------------------------------+{Colors.RESET}
""")

    profile = generate_profile(answers)
    profile_path, checksum = export_usda(profile, answers)

    print(f"  {Colors.GREEN}[OK]{Colors.RESET} Profile generated (USD Cognitive Substrate v4.3.0)")
    print(f"  {Colors.GREEN}[OK]{Colors.RESET} Checksum: {Colors.CYAN}{checksum}{Colors.RESET}")
    print(f"  {Colors.GREEN}[OK]{Colors.RESET} Exported: {profile_path}")
    print()

    # Your profile - show dimensions
    print(f"  {Colors.BOLD}Your Cognitive Dimensions:{Colors.RESET}")
    for dim, value in sorted(profile.get("dimensions", {}).items()):
        bar_len = int(value * 20)
        bar = "#" * bar_len + "." * (20 - bar_len)
        print(f"    {dim:24} [{bar}] {value:.1f}")
    print()

    # Show traits
    print(f"  {Colors.BOLD}Your Traits:{Colors.RESET}")
    for qid, trait in sorted(profile.get("traits", {}).items()):
        print(f"    {qid}: {Colors.CYAN}{trait}{Colors.RESET}")
    print()

    # Send finale to UE5
    write_finale(profile_path, checksum, len(answers))

    # Stop heartbeat
    heartbeat.stop()

    print(f"  {Colors.DIM}[TRANSLATORS:{checksum}]{Colors.RESET}")
    print()

    return True

# ============================================
#  Entry Point
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description="Translators Bridge Orchestrator v2.0.0 - USD-native cognitive profiling"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Force JSON mode (disable USD communication)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: write sample question and exit"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate bridge_state.usda and exit"
    )

    args = parser.parse_args()

    if args.validate:
        if not HAS_USD_BRIDGE:
            print("USD bridge module not available")
            sys.exit(1)
        ensure_bridge_dir()
        validation = validate_bridge_state(BRIDGE_DIR)
        print(f"Bridge state: {'VALID' if validation['valid'] else 'INVALID'}")
        print(f"  Sync status: {validation['sync_status']}")
        print(f"  Message type: {validation['message_type']}")
        if validation["errors"]:
            print(f"  Errors: {validation['errors']}")
        sys.exit(0 if validation["valid"] else 1)

    if args.test:
        print("Test mode: Writing sample question...")
        ensure_bridge_dir()
        if HAS_USD_BRIDGE and not args.json:
            write_question_usda(
                question_id="test",
                text="This is a test question from bridge_orchestrator.py",
                options=[
                    {"label": "Option A (low)", "direction": "low", "semantic_tag": "test_a"},
                    {"label": "Option B (mid)", "direction": "mid", "semantic_tag": "test_b"},
                    {"label": "Option C (high)", "direction": "high", "semantic_tag": "test_c"},
                ],
                index=0,
                total=1,
                scene="test_scene",
                bridge_path=BRIDGE_DIR
            )
            print(f"USD question written to: {get_bridge_file_path(BRIDGE_DIR)}")
        else:
            write_question(QUESTIONS[0], 0, 1)
            print(f"JSON question written to: {STATE_FILE}")
        sys.exit(0)

    try:
        success = run_questionnaire(force_json=args.json)
        if success:
            print(f"  {Colors.GREEN}Session complete. Your profile is ready for AI consumption.{Colors.RESET}")
        if sys.stdout.isatty():
            input("\n  Press Enter to exit...")
        else:
            print("\n  Orchestrator finished. Waiting 60s for cleanup...")
            time.sleep(60)
    except KeyboardInterrupt:
        print(f"\n\n  {Colors.YELLOW}Session cancelled.{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n  {Colors.RED}ERROR: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
