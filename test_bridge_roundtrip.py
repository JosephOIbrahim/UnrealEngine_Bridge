#!/usr/bin/env python3
"""
test_bridge_roundtrip.py

Integration test for Claude Code → UE5 Bridge v2.0.0
Simulates UE5 side to test the Python bridge without running Unreal Engine.

Supports both:
- USD-native mode (v2.0.0): bridge_state.usda
- JSON fallback mode (v1.0.0): state.json

Usage:
    Terminal 1: python bridge_orchestrator.py
    Terminal 2: python test_bridge_roundtrip.py [--json]

This script:
1. Watches for bridge_state.usda or state.json from Claude Code
2. Responds with acknowledgment
3. Simulates user answers to each question
4. Verifies USD profile output at the end
"""

import argparse
import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Configuration - must match the bridge
BRIDGE_DIR = Path.home() / ".translators"
STATE_FILE = BRIDGE_DIR / "state.json"
ANSWER_FILE = BRIDGE_DIR / "answer.json"
USD_STATE_FILE = BRIDGE_DIR / "bridge_state.usda"
USD_PROFILE_OUTPUT = BRIDGE_DIR / "cognitive_profile.usda"

# Test configuration
SIMULATED_RESPONSE_TIME_MS = 2500.0  # Simulate 2.5s decision time
AUTO_ANSWER_INDEX = 2  # Always pick option 2 (middle option)


class UE5Simulator:
    """Simulates UE5 side of the bridge for testing"""

    def __init__(self, use_usd_mode: bool = True):
        self.questions_received = 0
        self.last_state_mtime = 0
        self.last_usd_mtime = 0
        self.use_usd_mode = use_usd_mode
        self.current_question_id = ""
        self.current_options = []

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        mode = "USD" if self.use_usd_mode else "JSON"
        print(f"[{timestamp}] [UE5-SIM:{mode}] {message}")

    # === JSON MODE (v1.0.0) ===

    def write_answer_json(self, data: Dict[str, Any]):
        """Write answer.json for Claude Code to read"""
        data["timestamp"] = datetime.now().isoformat()
        data["$schema"] = "translators-answer-v1"
        ANSWER_FILE.write_text(json.dumps(data, indent=2))
        self.log(f"Wrote JSON answer: {data.get('type', 'unknown')}")

    def read_state_json(self) -> Optional[Dict[str, Any]]:
        """Read state.json if it changed"""
        if not STATE_FILE.exists():
            return None

        mtime = STATE_FILE.stat().st_mtime
        if mtime <= self.last_state_mtime:
            return None

        self.last_state_mtime = mtime
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return None

    # === USD MODE (v2.0.0) ===

    def parse_usda_variant(self, content: str, variant_name: str) -> str:
        """Parse variant selection from USDA content."""
        match = re.search(rf'string {variant_name} = "([^"]*)"', content)
        return match.group(1) if match else ""

    def parse_usda_attr(self, content: str, attr_name: str, attr_type: str = "string") -> str:
        """Parse attribute value from USDA content."""
        if attr_type == "string":
            match = re.search(rf'{attr_type} {attr_name} = "([^"]*)"', content)
        else:
            match = re.search(rf'{attr_type} {attr_name} = ([^\s\n]+)', content)
        return match.group(1) if match else ""

    def read_state_usd(self) -> Optional[Dict[str, Any]]:
        """Read bridge_state.usda if it changed."""
        if not USD_STATE_FILE.exists():
            return None

        mtime = USD_STATE_FILE.stat().st_mtime
        if mtime <= self.last_usd_mtime:
            return None

        self.last_usd_mtime = mtime
        try:
            content = USD_STATE_FILE.read_text()

            sync_status = self.parse_usda_variant(content, "sync_status")
            message_type = self.parse_usda_variant(content, "message_type")

            if message_type == "ready":
                return {
                    "type": "ready",
                    "total_questions": int(self.parse_usda_attr(content, "total_questions", "int") or "8"),
                    "first_scene": self.parse_usda_attr(content, "first_scene"),
                }

            elif message_type == "question" and sync_status == "question_pending":
                # Parse options
                options = []
                for i in range(3):
                    label = self.parse_usda_attr(content, "label")
                    direction = self.parse_usda_attr(content, "direction")
                    # More specific parsing for options
                    opt_match = re.search(
                        rf'def Xform "Option_{i}"[^{{]*\{{[^}}]*string label = "([^"]*)"[^}}]*string direction = "([^"]*)"',
                        content, re.DOTALL
                    )
                    if opt_match:
                        options.append({
                            "index": i,
                            "label": opt_match.group(1),
                            "direction": opt_match.group(2),
                        })

                self.current_options = options
                return {
                    "type": "question",
                    "index": int(self.parse_usda_attr(content, "index", "int") or "0"),
                    "total": int(self.parse_usda_attr(content, "total", "int") or "8"),
                    "id": self.parse_usda_attr(content, "question_id"),
                    "text": self.parse_usda_attr(content, "text"),
                    "scene": self.parse_usda_attr(content, "scene"),
                    "options": options,
                }

            elif message_type == "transition":
                return {
                    "type": "transition",
                    "direction": self.parse_usda_attr(content, "direction"),
                    "next_scene": self.parse_usda_attr(content, "next_scene"),
                    "progress": float(self.parse_usda_attr(content, "progress", "float") or "0"),
                }

            elif message_type == "finale" or sync_status == "complete":
                return {
                    "type": "finale",
                    "message": self.parse_usda_attr(content, "message"),
                    "usd_path": self.parse_usda_attr(content, "usd_path"),
                    "checksum": self.parse_usda_attr(content, "checksum"),
                }

            return None

        except Exception as e:
            self.log(f"USD parse error: {e}")
            return None

    def write_answer_usd(self, question_id: str, option_index: int):
        """Write answer to bridge_state.usda."""
        if not USD_STATE_FILE.exists():
            self.log("ERROR: bridge_state.usda not found")
            return

        content = USD_STATE_FILE.read_text()
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Get selected option details
        selected_label = ""
        selected_direction = ""
        if 0 <= option_index < len(self.current_options):
            selected_label = self.current_options[option_index].get("label", "")
            selected_direction = self.current_options[option_index].get("direction", "")

        # Update variants
        content = re.sub(
            r'(string sync_status = ")[^"]*(")',
            r'\g<1>answer_received\g<2>',
            content
        )
        content = re.sub(
            r'(string message_type = ")[^"]*(")',
            r'\g<1>answer\g<2>',
            content
        )

        # Update Answer prim attributes
        def update_attr(c: str, name: str, value: str, is_string: bool = True) -> str:
            if is_string:
                return re.sub(
                    rf'(string {name} = ")[^"]*(")',
                    rf'\g<1>{value}\g<2>',
                    c
                )
            else:
                return re.sub(
                    rf'({name} = )[^\n]+',
                    rf'\g<1>{value}',
                    c
                )

        content = update_attr(content, "question_id", question_id)
        content = re.sub(r'(int option_index = )-?\d+', rf'\g<1>{option_index}', content)
        content = re.sub(r'(double response_time_ms = )[\d.]+', rf'\g<1>{SIMULATED_RESPONSE_TIME_MS}', content)
        content = update_attr(content, "selected_label", selected_label)
        content = update_attr(content, "selected_direction", selected_direction)
        content = update_attr(content, "timestamp", timestamp)

        USD_STATE_FILE.write_text(content)
        self.log(f"Wrote USD answer: {question_id} = option {option_index}")

    def write_ack_usd(self):
        """Write acknowledgment to bridge_state.usda."""
        if not USD_STATE_FILE.exists():
            self.log("ERROR: bridge_state.usda not found for ack")
            return

        content = USD_STATE_FILE.read_text()
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Update message_type to ack
        content = re.sub(
            r'(string message_type = ")[^"]*(")',
            r'\g<1>ack\g<2>',
            content
        )

        # Update Ack prim
        content = re.sub(r'(bool ready = )(?:true|false)', r'\g<1>true', content)
        content = re.sub(r'(string ue_version = ")[^"]*(")', r'\g<1>5.7.2-SIMULATOR\g<2>', content)
        content = re.sub(r'(string project = ")[^"]*(")', r'\g<1>UnrealEngineBridge-TEST\g<2>', content)

        USD_STATE_FILE.write_text(content)
        self.log("Wrote USD acknowledgment")

    # === UNIFIED INTERFACE ===

    def send_ack(self):
        """Send acknowledgment that UE5 is ready."""
        if self.use_usd_mode:
            self.write_ack_usd()
        else:
            self.write_answer_json({
                "type": "ack",
                "ack": {
                    "ready": True,
                    "ue_version": "5.7.2-SIMULATOR"
                }
            })

    def send_answer(self, question_id: str, option_index: int):
        """Send a simulated user answer."""
        if self.use_usd_mode:
            self.write_answer_usd(question_id, option_index)
        else:
            self.write_answer_json({
                "type": "answer",
                "answer": {
                    "question_id": question_id,
                    "option_index": option_index,
                    "response_time_ms": SIMULATED_RESPONSE_TIME_MS
                }
            })

    def read_state(self) -> Optional[Dict[str, Any]]:
        """Read state from USD or JSON."""
        if self.use_usd_mode:
            state = self.read_state_usd()
            if state:
                return state
            # Fall back to JSON if USD not found
            return self.read_state_json()
        else:
            return self.read_state_json()

    def handle_state(self, state: Dict[str, Any]):
        """Process incoming state from Claude Code"""
        state_type = state.get("type", "")

        if state_type == "ready":
            total = state.get("total_questions", 0)
            self.log(f"Claude Code ready! {total} questions total")
            self.log("Sending acknowledgment...")
            time.sleep(0.5)  # Simulate startup delay
            self.send_ack()

        elif state_type == "question":
            index = state.get("index", 0)
            total = state.get("total", 0)
            question_id = state.get("id", "")
            text = state.get("text", "").replace("\n", " ")
            self.questions_received += 1
            self.current_question_id = question_id

            # Store options for USD answer
            if "options" in state:
                self.current_options = state["options"]

            self.log(f"Question {index + 1}/{total}: {question_id}")
            self.log(f"  Text: {text[:50]}...")

            # Simulate "thinking time"
            self.log(f"  [Simulating {SIMULATED_RESPONSE_TIME_MS/1000:.1f}s response time...]")
            time.sleep(1.0)  # Don't actually wait full time in test

            # Send answer
            self.send_answer(question_id, AUTO_ANSWER_INDEX)
            self.log(f"  Answered: option {AUTO_ANSWER_INDEX}")

        elif state_type == "transition":
            direction = state.get("direction", "")
            next_scene = state.get("next_scene", "")
            progress = state.get("progress", 0)
            self.log(f"Transition: {direction} -> {next_scene} ({progress*100:.0f}% complete)")

        elif state_type == "finale":
            self.log("=" * 50)
            self.log("FINALE RECEIVED!")
            self.log(f"  Message: {state.get('message', '')}")
            self.log(f"  USD Path: {state.get('usd_path', '')}")
            if state.get('checksum'):
                self.log(f"  Checksum: {state.get('checksum')}")
            return True  # Signal completion

        return False

    def verify_usd(self):
        """Verify the generated USD cognitive profile"""
        # Check both possible output locations
        output_file = None
        for path in [USD_PROFILE_OUTPUT, BRIDGE_DIR / "cognitive_substrate.usda"]:
            if path.exists():
                output_file = path
                break

        if not output_file:
            self.log("ERROR: USD profile file not found!")
            self.log(f"  Checked: {USD_PROFILE_OUTPUT}")
            return False

        content = output_file.read_text()
        self.log("=" * 50)
        self.log("USD PROFILE VERIFICATION")
        self.log(f"File: {output_file.name}")
        self.log("=" * 50)

        # Check for key elements (USD Cognitive Substrate v4.3.0 format)
        checks = [
            ("defaultPrim", "CognitiveSubstrate" in content),
            ("Profile Xform", '"Profile"' in content),
            ("Session Xform", '"Session"' in content),
            ("Answers Xform", '"Answers"' in content),
            ("checksum", 'checksum = "' in content),
            ("cognitive_density", "cognitive_density" in content),
            ("home_altitude", "home_altitude" in content),
            ("Traits Xform", '"Traits"' in content),
        ]

        all_passed = True
        for name, passed in checks:
            status = "PASS" if passed else "FAIL"
            self.log(f"  [{status}] {name}")
            if not passed:
                all_passed = False

        # Extract and display checksum
        match = re.search(r'checksum = "([a-f0-9]+)"', content)
        if match:
            self.log(f"  Profile Checksum: {match.group(1)}")

        # Extract dimensions
        self.log("")
        self.log("  Cognitive Dimensions:")
        dims = [
            "cognitive_density", "home_altitude", "guidance_frequency",
            "default_paradigm", "feedback_style", "uncertainty_tolerance",
            "processing_pace", "tangent_tolerance"
        ]
        for dim in dims:
            dim_match = re.search(rf'float {dim} = ([\d.]+)', content)
            if dim_match:
                value = float(dim_match.group(1))
                bar = "█" * int(value * 10) + "░" * (10 - int(value * 10))
                self.log(f"    {dim:24} [{bar}] {value:.1f}")

        return all_passed

    def run(self, timeout: float = 120.0):
        """Main test loop"""
        mode_str = "USD-native" if self.use_usd_mode else "JSON"
        self.log("=" * 50)
        self.log(f"UE5 BRIDGE SIMULATOR v2.0.0 ({mode_str})")
        self.log("=" * 50)

        watch_file = USD_STATE_FILE if self.use_usd_mode else STATE_FILE
        self.log(f"Watching: {watch_file}")
        self.log(f"Will auto-answer with option {AUTO_ANSWER_INDEX}")
        self.log("")
        self.log("Start the Claude Code bridge in another terminal:")
        self.log("  python bridge_orchestrator.py")
        self.log("")

        BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
        start_time = time.time()
        completed = False

        while time.time() - start_time < timeout:
            state = self.read_state()
            if state:
                completed = self.handle_state(state)
                if completed:
                    break
            time.sleep(0.1)

        if completed:
            self.log("")
            time.sleep(0.5)  # Wait for USD to be written
            success = self.verify_usd()
            self.log("")
            if success:
                self.log("TEST PASSED!")
            else:
                self.log("TEST FAILED - USD verification errors")
        else:
            self.log("TIMEOUT - no finale received")

        self.log(f"Total questions handled: {self.questions_received}")


def main():
    parser = argparse.ArgumentParser(
        description="UE5 Bridge Simulator v2.0.0 - Test CC↔UE5 communication"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Force JSON mode (disable USD communication)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Timeout in seconds (default: 120)"
    )
    parser.add_argument(
        "--answer",
        type=int,
        default=AUTO_ANSWER_INDEX,
        help=f"Auto-answer option index (default: {AUTO_ANSWER_INDEX})"
    )

    args = parser.parse_args()

    # Override global if specified
    global AUTO_ANSWER_INDEX
    AUTO_ANSWER_INDEX = args.answer

    use_usd = not args.json
    simulator = UE5Simulator(use_usd_mode=use_usd)

    try:
        simulator.run(timeout=args.timeout)
    except KeyboardInterrupt:
        simulator.log("Test interrupted by user")


if __name__ == "__main__":
    main()
