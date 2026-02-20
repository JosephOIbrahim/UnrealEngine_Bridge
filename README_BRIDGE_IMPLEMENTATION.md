# Claude Code → Unreal Engine 5.7 Bridge Implementation

> **Note:** This document describes the v1.0.0 JSON-based protocol. For the current USD-native v2.0.0 implementation with ThinkingMachines compliance, see **[README.md](./README.md)**.

**Status**: Superseded by v2.0.0
**Date**: January 2026

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FILE-BASED BRIDGE                              │
│                                                                          │
│   ~/.translators/                                                        │
│   ├── state.json          ← Claude writes, UE5 reads (questions)        │
│   ├── answer.json         ← UE5 writes, Claude reads (user input)       │
│   └── cognitive_substrate.usda  ← Claude writes, UE5 USD Stage reads    │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   CLAUDE CODE                        UNREAL ENGINE 5.7                   │
│   ───────────                        ────────────────                    │
│   ue5_translators_bridge.py          BridgeComponent.cpp                 │
│   - Writes state.json                - FDirectoryWatcher                 │
│   - Waits for answer.json            - Parses state.json                 │
│   - Generates .usda                  - Displays question UI              │
│                                      - Writes answer.json                │
│                                      - USD Stage Actor reload            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Files Created

### Python Side (Claude Code)
- `~/.claude/bridges/ue5_translators_bridge.py` - Main orchestrator

### UE5 Side (C++ Plugin)
- `Source/UnrealEngineBridge/BridgeComponent.h` - Component header
- `Source/UnrealEngineBridge/BridgeComponent.cpp` - Implementation
- `Source/UnrealEngineBridge/UnrealEngineBridge.Build.cs` - Module build config
- `Source/UnrealEngineBridge/UnrealEngineBridge.h` - Module header
- `Source/UnrealEngineBridge/UnrealEngineBridge.cpp` - Module implementation
- `Source/UnrealEngineBridge.Target.cs` - Game target
- `Source/UnrealEngineBridgeEditor.Target.cs` - Editor target

### USD Templates
- `USD/cognitive_substrate_template.usda` - Template with documentation

### Testing
- `test_bridge_roundtrip.py` - UE5 simulator for testing without engine

---

## ThinkingMachines Compliance (Batch-Invariance)

Per [thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/):

1. **FIXED Evaluation Order**: 5-phase execution (DETECT → CASCADE → LOCK → EXECUTE → UPDATE)
2. **FIXED Signal Priority**: emotional > mode > domain > task
3. **FIXED Expert Priority**: Validator > Scaffolder > ... > Direct
4. **Checksum Anchoring**: Same answers → same checksum → deterministic profile
5. **LOCKED Parameters**: Parameters lock before generation, no runtime variation

### Determinism in the Bridge

```python
# Checksum generation (deterministic)
sorted_dims = sorted(dimensions.items())
checksum_input = "TRL_v1|" + "|".join(f"{k}:{v}" for k, v in sorted_dims)
checksum = hashlib.md5(checksum_input.encode()).hexdigest()[:8]
```

Same answers ALWAYS produce the same checksum. This is the "anchor" that UE5 can use to verify profile consistency.

---

## Critical Gotchas

| Issue | Impact | Solution |
|-------|--------|----------|
| USD Stage Actor does NOT auto-reload | File changes won't be visible | Implement `SetRootLayer("")` then `SetRootLayer(path)` |
| FDirectoryWatcher is editor-only | Won't work in packaged builds | Custom polling or editor-only feature |
| Runtime USD needs flag | USD fails to load | Add `FORCE_ANSI_ALLOCATOR=1` to Target.cs |
| File locking | Write failures | Retry with 100ms delay (up to 3x) |

---

## Quick Start

### 1. Test Without UE5

Terminal 1:
```bash
python ~/.claude/bridges/ue5_translators_bridge.py
```

Terminal 2:
```bash
cd ue-bridge
python test_bridge_roundtrip.py
```

### 2. UE5 Integration

1. Copy `Source/` to your UE5.7 project
2. Enable USD Importer plugin
3. Add BridgeComponent to an Actor
4. Bind Blueprint events to OnQuestionReceived, etc.
5. Call SendAcknowledge() when ready
6. Call SendAnswer() when user selects option

---

## Protocol Reference

### state.json (Claude → UE5)

```json
{
  "$schema": "translators-state-v1",
  "type": "question",
  "index": 0,
  "total": 8,
  "id": "load",
  "text": "How much can you hold...",
  "scene": "forest_edge",
  "options": [
    {"index": 0, "label": "Not much.", "direction": "left"},
    {"index": 1, "label": "Quite a lot.", "direction": "right"},
    {"index": 2, "label": "It varies.", "direction": "forward"}
  ]
}
```

### answer.json (UE5 → Claude)

```json
{
  "$schema": "translators-answer-v1",
  "type": "answer",
  "answer": {
    "question_id": "load",
    "option_index": 2,
    "response_time_ms": 3500
  }
}
```

---

## Next Steps

1. **UE5 Project Setup**: Create Paper2D project with USD Stage Actor
2. **Blueprint Wiring**: Connect BridgeComponent events to UI
3. **Visual Design**: 8-bit NES aesthetic for question display
4. **Audio**: Chiptune background, select sounds
5. **Polish**: Scene transitions, CRT effects

---

## References

- Research: `docs/CLAUDE_UE5_BRIDGE_RESEARCH.md`
- Handoff: `docs/HANDOFF_UE5_BRIDGE.md`
- ThinkingMachines: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- UsdAttributeTool: https://github.com/jack3761/UE-UsdAttributeTool
