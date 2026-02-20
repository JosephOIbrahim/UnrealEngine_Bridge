# Translators Bridge

**An Unreal Engine plugin that connects your game to The Translators -- a cognitive profiling experience where personality emerges from play, not questionnaires.**

Players answer eight questions. Their choices, timing, and hesitation patterns generate a deterministic cognitive profile exportable as USD. The same answers always produce the same profile.

---

## What's In the Box

| Component | What It Does |
|-----------|-------------|
| **UEBridge plugin** | Drop-in UE plugin with Runtime + Editor modules |
| **Question delivery system** | Presents questions, collects answers, tracks behavioral signals |
| **Profile engine** | Generates deterministic cognitive profiles from player responses |
| **USD export** | Profiles export as `.usda` files for pipeline integration |
| **Full UI kit** | Title screen, question display, option buttons, progress indicator, finale screen |

---

## Quick Start

### 1. Enable the Plugin

1. Copy `Plugins/UEBridge/` into your project's `Plugins/` folder
2. Open your project in Unreal Editor
3. Go to **Edit > Plugins**, search for "Translators Bridge", and enable it
4. Restart the editor when prompted

### 2. Add the Bridge to Your Level

**Option A: Blueprint (recommended)**

1. Create a new Actor Blueprint
2. Add a **Bridge Component** to it
3. Place the actor in your level
4. In the Details panel, bind the events you need:

| Event | When It Fires |
|-------|--------------|
| `On Bridge Ready` | Connection established, ready to start |
| `On Question Received` | A new question is ready to display |
| `On Transition Received` | Moving between questions |
| `On Finale Received` | All questions answered, profile ready |

**Option B: C++ Subsystem (advanced)**

The plugin provides `UUEBridgeSubsystem` -- a GameInstance subsystem you can access from anywhere:

```cpp
#include "UEBridgeSubsystem.h"

UUEBridgeSubsystem* Bridge = GetGameInstance()->GetSubsystem<UUEBridgeSubsystem>();
Bridge->StartGame();
```

### 3. Start the Python Backend

In a terminal, from the project root:

```bash
python bridge_orchestrator.py
```

The bridge communicates through files in `~/.translators/`. No network configuration needed.

---

## How It Works

```
  Python Backend                    Unreal Engine
  ──────────────                    ──────────────
  bridge_orchestrator.py     ←→     UEBridge Plugin
         │                                  │
    Writes questions           Reads questions, shows UI
    to ~/.translators/         Writes answers back
         │                                  │
    Reads answers              Tracks response time,
    Generates profile          hesitation, click patterns
         │                                  │
    Exports .usda              Displays cognitive profile
```

The bridge uses plain files -- no sockets, no ports, no network setup. It just works.

---

## The UI Widgets

All widgets are fully programmatic -- no Blueprint assets required. They build themselves in C++ and render with The Translators' signature dark-cyan aesthetic.

| Widget | Purpose |
|--------|---------|
| `W_TitleScreen` | "The Translators" title with pulsing "Press ENTER to begin" prompt |
| `W_ConnectingScreen` | "Connecting to Claude Code..." status display |
| `W_QuestionDisplay` | Question text + answer buttons + depth tier label + progress |
| `W_OptionButton` | Individual answer button with hover/press states |
| `W_ProgressIndicator` | 8-dot progress bar (cyan = done, gold = current, gray = remaining) |
| `W_FinaleScreen` | Full cognitive profile display with traits, scores, and insights |

### Customizing the Look

Every color and font comes from `FTranslatorsStyle` -- a registered Slate style set. To override colors without touching code:

**In Blueprint:** Each widget exposes style properties (Background Color, Text Color, etc.) in the Details panel under **Translators | Style**.

**In C++:** Override the style set:

```cpp
#include "TranslatorsStyle.h"

// Get any named color
FLinearColor Cyan = FTranslatorsStyle::GetColor("Color.Cyan");

// Get any named font
FSlateFontInfo TitleFont = FTranslatorsStyle::GetFont("Font.Title");
```

### Color Palette

| Token | Color | Used For |
|-------|-------|----------|
| `Color.Cyan` | ![#5cffdb](https://via.placeholder.com/12/5cffdb/5cffdb.png) `#5cffdb` | Titles, accents, completed progress |
| `Color.Gold` | ![#ffcc33](https://via.placeholder.com/12/ffcc33/ffcc33.png) `#ffcc33` | Current progress indicator |
| `Color.Background` | Near-black | All screen backgrounds |
| `Color.TextPrimary` | Off-white | Body text |
| `Color.TextDim` | Mid-gray | Subtitles, secondary info |

### Font Scale

| Token | Size | Used For |
|-------|------|----------|
| `Font.Title` | 56 | Title screen heading |
| `Font.Heading` | 36 | Finale screen heading |
| `Font.Question` | 24 | Question text |
| `Font.Subtitle` | 18 | Subtitles |
| `Font.Body` | 16 | General text |
| `Font.Caption` | 12 | Labels, headers |

All fonts use `FCoreStyle` defaults -- DPI-aware, no hardcoded font files.

---

## Input

The title screen accepts **Enter** or **Space** to start. It also supports **Enhanced Input** -- assign a `UInputAction` to the `StartInputAction` property in the Details panel if your project uses the Enhanced Input system.

Answer buttons are mouse/touch clickable with hover and press feedback.

---

## The Cognitive Profile

After eight questions, the engine generates a profile like this:

```
DIMENSIONS
───────────────────────────────
cognitive_load       Synthesizer    72%
  Prefers to integrate multiple perspectives

decision_making      Adaptive       65%
  Shifts approach based on context

communication        Direct         80%
  Values clarity and conciseness

INSIGHTS
───────────────────────────────
  Gravitates toward systematic decomposition
  Responds well to structured frameworks
  Shows high tolerance for ambiguity

[TRANSLATORS:101bfab5]
```

The checksum at the bottom is deterministic -- same answers always produce the same hash. This is how you verify profile integrity.

---

## Project Structure

```
Plugins/UEBridge/
├── UEBridge.uplugin          # Plugin descriptor
├── Resources/Icon128.png              # Plugin icon
├── Content/Widgets/                   # Widget assets
└── Source/
    ├── UEBridgeRuntime/      # Ships in packaged builds
    │   ├── Public/
    │   │   ├── BridgeTypes.h          # Shared types (questions, profiles, signals)
    │   │   ├── UEBridgeSubsystem.h  # Main game flow subsystem
    │   │   └── TranslatorsStyle.h     # Slate style system
    │   └── Private/
    │       ├── UEBridgeSubsystem.cpp
    │       └── TranslatorsStyle.cpp
    └── UEBridgeEditor/       # Editor-only (file watching, process management)
        ├── Public/
        │   └── BridgeEditorSubsystem.h
        └── Private/
            └── BridgeEditorSubsystem.cpp

Source/UnrealEngineBridge/                # Game module (thin relay to plugin)
├── BridgeComponent.h/cpp             # Legacy component (forwards to subsystem)
└── UI/
    ├── W_TitleScreen.h/cpp
    ├── W_ConnectingScreen.h/cpp
    ├── W_QuestionDisplay.h/cpp
    ├── W_OptionButton.h/cpp
    ├── W_ProgressIndicator.h/cpp
    ├── W_FinaleScreen.h/cpp
    └── TranslatorsHUD.h/cpp
```

---

## Blueprint API Reference

### Bridge Component

| Function | Description |
|----------|-------------|
| `SendAnswer(QuestionId, OptionIndex, ResponseTimeMs)` | Submit the player's answer |
| `SendAcknowledge()` | Tell the backend you're ready for the next question |
| `IsBridgeConnected()` | Check if the Python backend is running |
| `GetCurrentQuestion()` | Get the current question data |

### Bridge Subsystem

| Function | Description |
|----------|-------------|
| `StartGame()` | Begin the bridge connection and game session |
| `StopGame()` | End the session and clean up |
| `SubmitAnswer(Answer)` | Submit a structured answer |
| `GetBridgeState()` | Current state (Idle, Connected, QuestionActive, etc.) |
| `GetBehavioralSignals()` | Response timing, hesitation count, detected state |

### Question Data (`FTranslatorsQuestion`)

| Property | Type | Description |
|----------|------|-------------|
| `QuestionId` | String | Unique identifier |
| `Text` | String | Question text (supports `\n` for line breaks) |
| `OptionLabels` | String Array | Answer option display text |
| `OptionDirections` | String Array | Semantic direction per option |
| `Index` | Int | Current question number (0-based) |
| `Total` | Int | Total questions in session |
| `DepthLabel` | String | Tier: SURFACE, PATTERNS, FEELINGS, or CORE |

---

## Requirements

- Unreal Engine 5.4+
- Windows (Win64)
- Python 3.x (for the backend orchestrator)

## License

MIT

## Author

[Joseph Ibrahim](https://github.com/JosephOIbrahim)
