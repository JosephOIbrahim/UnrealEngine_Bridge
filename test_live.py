"""Simple bridge test - write ready, wait for ack, send questions, wait for answers."""
import json, time, sys
from pathlib import Path
from datetime import datetime

BRIDGE = Path.home() / ".translators"
STATE = BRIDGE / "state.json"
ANSWER = BRIDGE / "answer.json"
BRIDGE.mkdir(exist_ok=True)

QUESTIONS = [
    {"id": "load", "text": "How much can you hold at once\nbefore it starts to blur?", "scene": "forest_edge",
     "options": [{"index": 0, "label": "Not much. One thing at a time.", "direction": "low", "value": 0.2},
                 {"index": 1, "label": "Quite a lot. I can hold complexity.", "direction": "high", "value": 0.8},
                 {"index": 2, "label": "It varies. Some days more than others.", "direction": "mid", "value": 0.5}]},
    {"id": "pace", "text": "When you're working on something\nthat matters to you...", "scene": "forest_path",
     "options": [{"index": 0, "label": "I go deep. Hours disappear.", "direction": "low", "value": 0.2},
                 {"index": 1, "label": "I take breaks. Steady rhythm.", "direction": "high", "value": 0.8},
                 {"index": 2, "label": "Bursts of intensity, then rest.", "direction": "mid", "value": 0.5}]},
    {"id": "uncertainty", "text": "When facing the unknown...", "scene": "misty_clearing",
     "options": [{"index": 0, "label": "I need a plan before I move.", "direction": "low", "value": 0.2},
                 {"index": 1, "label": "I explore. The path reveals itself.", "direction": "high", "value": 0.8},
                 {"index": 2, "label": "I sketch a direction, then adapt.", "direction": "mid", "value": 0.5}]},
]

def write_state(data):
    with open(STATE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def wait_answer(timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        if ANSWER.exists():
            try:
                with open(ANSWER, 'r', encoding='utf-8') as f:
                    ans = json.load(f)
                ANSWER.unlink()
                return ans
            except: pass
        time.sleep(0.25)
    return None

print("[test_live] Writing ready state...")
write_state({"$schema": "translators-state-v1", "type": "ready", "total_questions": len(QUESTIONS),
             "first_scene": "forest_edge", "timestamp": datetime.now().isoformat(), "bridge_version": "2.0.0"})

print("[test_live] Waiting for UE5 ack (hit Play in editor)...")
ack = wait_answer(timeout=300)
if ack:
    print(f"[test_live] Got ack: {ack.get('type', '?')}")
else:
    print("[test_live] No ack, proceeding anyway...")

for i, q in enumerate(QUESTIONS):
    state = {"type": "question", "index": i, "total": len(QUESTIONS), "id": q["id"],
             "text": q["text"], "scene": q["scene"], "options": q["options"],
             "timestamp": datetime.now().isoformat(), "bridge_version": "2.0.0"}
    write_state(state)
    print(f"[test_live] Sent question {i+1}/{len(QUESTIONS)}: {q['id']}")

    ans = wait_answer()
    if ans:
        oi = ans.get("option_index", ans.get("answer", {}).get("option_index", "?"))
        print(f"[test_live] Answer: option {oi}")
    else:
        print("[test_live] Timeout waiting for answer")
        break

print("[test_live] Done!")
