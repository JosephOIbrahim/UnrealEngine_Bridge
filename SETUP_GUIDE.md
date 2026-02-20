# Claude Code → UE5.7 Bridge: Complete Setup Guide

## Overview

This guide walks through setting up the bidirectional bridge between Claude Code and Unreal Engine 5.7 for "The Translators" cognitive profiling game.

**What You'll Have When Done:**
- Claude Code sends questions → UE5 displays them
- User selects answer in UE5 → Claude Code receives it
- Claude Code generates USD cognitive profile → UE5 loads it

---

## Prerequisites

- Windows 10/11
- Unreal Engine 5.7 installed (via Epic Games Launcher)
- Python 3.10+ with pip
- Claude Code installed and configured

---

## Step 1: Create the Bridge Directory

```powershell
# PowerShell
mkdir $HOME\.translators

# Or Command Prompt
mkdir %USERPROFILE%\.translators
```

This directory is where all communication happens:
- `state.json` - Claude Code writes, UE5 reads
- `answer.json` - UE5 writes, Claude Code reads
- `cognitive_substrate.usda` - Generated profile

---

## Step 2: Set Up Claude Code Side

The Python bridge is already at `~/.claude/bridges/ue5_translators_bridge.py`.

### Verify it works:

```bash
python ~/.claude/bridges/ue5_translators_bridge.py
```

You should see:
```
[HH:MM:SS] ============================================================
[HH:MM:SS] TRANSLATORS BRIDGE STARTED
[HH:MM:SS] Waiting for UE5 to connect...
```

The bridge waits for UE5 to acknowledge before sending questions.

---

## Step 3: Create UE5 Project

### Option A: Copy to Existing Project

1. Copy `Source/UnrealEngineBridge/` to your UE5 project's `Source/` folder
2. Copy `Config/*.ini` to your project's `Config/` folder
3. Add to your `.uproject`:
```json
{
  "Plugins": [
    { "Name": "USDImporter", "Enabled": true },
    { "Name": "PythonScriptPlugin", "Enabled": true }
  ]
}
```
4. Regenerate project files (right-click .uproject → Generate Visual Studio project files)
5. Build

### Option B: Use This Project Directly

1. Open `UnrealEngineBridge.uproject` in UE5.7
2. When prompted to build, click Yes
3. Wait for compilation

---

## Step 4: Set Up the Level

1. **Create a new Level** (File → New Level → Empty Level)

2. **Add USD Stage Actor**:
   - Place Actors → USD → USD Stage Actor
   - In Details panel, set Root Layer:
     - Path: `C:/Users/[YourName]/.translators/cognitive_substrate.usda`
   - This file won't exist yet - that's OK

3. **Add Bridge Controller**:
   - Create new Blueprint: Content Browser → Right-click → Blueprint Class → Actor
   - Name it: `BP_BridgeController`
   - Open it, add component: "Bridge Component" (from C++ class)
   - In component details, assign the USD Stage Actor reference

4. **Set Up Events** (see Blueprint example in `Content/Blueprints/`)

5. **Add UI Widgets** for question display

---

## Step 5: Test the Connection

### Terminal 1 (Claude Code side):
```bash
python ~/.claude/bridges/ue5_translators_bridge.py
```

### Terminal 2 (UE5 simulator - for testing without engine):
```bash
cd ue-bridge
python test_bridge_roundtrip.py
```

You should see:
- Claude Code outputs "Waiting for UE5..."
- Simulator sends acknowledgment
- Questions flow back and forth
- USD file generated at the end

### With Actual UE5:
1. Play in Editor (PIE)
2. BridgeComponent detects `state.json` and fires `OnBridgeReady`
3. Your Blueprint calls `SendAcknowledge()`
4. Questions start flowing

---

## Step 6: Blueprint Wiring (Quick Reference)

```
BeginPlay
    └─► BridgeComponent.OnBridgeReady.AddDynamic → SendAcknowledge()
    └─► BridgeComponent.OnQuestionReceived.AddDynamic → UpdateUI()
    └─► BridgeComponent.OnFinaleReceived.AddDynamic → ShowResults()

OnOptionClicked(Index)
    └─► BridgeComponent.SendAnswer(QuestionId, Index, ResponseTimeMs)
```

---

## Troubleshooting

### "Could not get DirectoryWatcher module"
- This only works in Editor builds
- For packaged games, implement custom file polling

### "USD Stage doesn't update"
- USD Stage Actor does NOT auto-reload
- BridgeComponent handles this by calling SetRootLayer twice

### "state.json not found"
- Ensure `~/.translators/` directory exists
- Check Python bridge is running

### Questions not appearing
- Verify OnQuestionReceived event is bound
- Check Output Log for "[UEBridge]" messages
- Ensure SendAcknowledge() was called after OnBridgeReady

### USD attributes not accessible in Blueprint
- Install UsdAttributeTool plugin: https://github.com/jack3761/UE-UsdAttributeTool
- Or use Python scripting for attribute access

---

## Architecture Reference

```
                    File-Based Bridge (~/.translators/)
                    ================================

  Claude Code (Python)                    Unreal Engine 5.7 (C++)
  ──────────────────                      ──────────────────────

  UEBridge                       BridgeComponent
       │                                       │
       │  ┌──────────────────────────────┐     │
       ├──┤ state.json (questions)       ├────►│ OnDirectoryChanged()
       │  └──────────────────────────────┘     │      │
       │                                       │      ▼
       │  ┌──────────────────────────────┐     │ ProcessStateFile()
       │◄─┤ answer.json (user responses) ├─────┤      │
       │  └──────────────────────────────┘     │      ▼
       │                                       │ OnQuestionReceived.Broadcast()
       │  ┌──────────────────────────────┐     │
       ├──┤ cognitive_substrate.usda     ├────►│ UsdStageActor.SetRootLayer()
       │  └──────────────────────────────┘     │
       ▼                                       ▼
  generate_usd_substrate()                OnUsdUpdated.Broadcast()
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `~/.claude/bridges/ue5_translators_bridge.py` | Claude Code orchestrator |
| `~/.translators/state.json` | Current state (questions, transitions) |
| `~/.translators/answer.json` | User responses |
| `~/.translators/cognitive_substrate.usda` | Generated profile |
| `Source/UnrealEngineBridge/BridgeComponent.*` | UE5 file watcher component |
| `Config/DefaultEngine.ini` | Engine settings |
| `test_bridge_roundtrip.py` | Test without UE5 |

---

## Next Steps

1. Build the 8-bit visual aesthetic (Paper2D or simple 3D)
2. Add chiptune audio
3. Implement scene transitions between questions
4. Add CRT post-process effect (optional)
5. Test full flow with actual user input
