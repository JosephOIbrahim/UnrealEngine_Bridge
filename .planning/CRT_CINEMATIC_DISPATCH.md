# UnrealEngine_Bridge — CRT Cinematic Display System
# Sprint: CRT-CINE
# Date: 2026-03-10
# Status: EXECUTING

---

## PRE-FLIGHT: Scene Baseline

Before ANY scene modification, verify via MCP tools:

1. `ue_health_check` — Bridge connected, circuit breaker CLOSED
2. `ue_list_actors` — Confirm 568 actors, find all CRT_* actors
3. `ue_get_actor_details` on CRT_Typography_Hero — Confirm WorldSize=250, M_CRT_Typography
4. `ue_find_assets` with "CRT" — Catalog existing materials
5. `ue_find_assets` with "Niagara" — Confirm NS_CRT_DotGrid and NS_DotGrid exist as unused assets

Do NOT proceed until you confirm the CRT installation geometry:
- Screen area: X -2155 to +2155, Z 625 to 2375
- Screen backing: Y=275
- CRT_Camera: (0, -4500, 1500), facing +Y, FOV 59.1

---

## STATUS REPORTING PROTOCOL

**MANDATORY:** After completing each task, print the status bar in this EXACT format.

```
╔══════════════════════════════════════════════════════════════╗
║  UE_Bridge — CRT-CINE STATUS                                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: BUILD FOUNDATION   [░░░░░░░░░░] 0%                ║
║    PHOSPHOR ◆ P1 ○  P2 ○  P3 ○                              ║
║    SHADER   ⟡ S1 ○  S2 ○  S3 ○  S4 ○                       ║
║                                                              ║
║  Phase 2: INTERACTIVE UI     [░░░░░░░░░░] 0%                ║
║    INTERACT ◈ I1 ○  I2 ○  I3 ○  I4 ○                        ║
║    COMPOSE  ⬡ C1 ○  C2 ○  C3 ○                              ║
║                                                              ║
║  Phase 3: INTEGRATE & SHIP   [░░░░░░░░░░] 0%                ║
║    COMPOSE  ⬡ C4 ○  C5 ○  C6 ○                              ║
║                                                              ║
║  Overall: [░░░░░░░░░░░░░░░░░░░░] 0%  (0/17 tasks)          ║
║  Legend: ✓ done  ▶ active  ○ pending  ✗ failed              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## ARCHITECTURE DECISIONS (NON-NEGOTIABLE)

### 1. Motion Design Cloner for Dot Grid (NOT Niagara)
Niagara is broken in this project (activation bugs, FPS death at scale). Use ClonerEffector
with Grid layout for deterministic phosphor dot placement. GPU-instanced, reliable.

```
ClonerEffector (CRT_PhosphorGrid)
├── Mesh: /Engine/BasicShapes/Sphere (scaled to phosphor dot size)
├── Layout: Grid
├── Count: ~100 x 60 = 6000 dots
├── Spacing: 43 x 29 units (fills 4310 x 1750 screen area)
├── Position: (0, 250, 1500) — in front of screen backing
├── Material: M_PhosphorDot (Unlit, emissive)
└── RGB Pattern: Effector or material drives R/G/B sub-pixel triplet color
```

### 2. 3D World-Space Typography (NOT UMG Widgets)
Questions rendered as TextRenderActors directly on the CRT screen surface.
All text uses M_CRT_Typography material, WorldSize=40, emissive=0.15.

```
CRT Screen Surface (Y=245, in front of dots at Y=250)
├── CRT_Question_Text (TextRenderActor)
│   ├── WorldSize: 40
│   ├── Alignment: Center/Center
│   └── Material: M_CRT_Typography
├── CRT_Option_A / B / C (TextRenderActor x3)
│   ├── WorldSize: 30
│   ├── Stacked vertically below question
│   └── Material: M_CRT_Typography (highlight variant for selected)
└── CRT_Progress (TextRenderActor)
    ├── WorldSize: 20
    ├── Bottom-right of screen area
    └── Shows "3/8"
```

### 3. Cinematic CRT Post-Process Stack
Full cinematic CRT authenticity via CRT_PostProcess volume:

```
CRT_PostProcess (Infinite Extent, Blend Weight 1.0)
├── Bloom: Intensity 1.5, Threshold 0.2 (phosphor glow)
├── Vignette: 0.7 (CRT edge darkening)
├── Film Grain: 0.12 intensity, 0.3 jitter
├── Color Grading:
│   ├── Scene Color Tint: (1.0, 0.88, 0.92) warm phosphor
│   ├── Saturation: (1.3, 0.95, 1.05, 1.0) boost red
│   └── Gain: (1.15, 0.90, 0.95) warm shift
├── Chromatic Aberration: 0.8 (RGB separation at edges)
└── Lens Distortion (barrel): material-based or PP setting
```

### 4. Communication Stack
All agents operate via MCP tools → HTTP localhost:30010 → UE5 Remote Control API.
Heavy lifting done via `ue_execute_python` for operations not covered by dedicated tools.

---

## FILE OWNERSHIP TABLE

**Every UE5 actor/asset has exactly ONE owner. No agent touches another's actors.**

| Agent | Role (MOE) | Exclusive Write (Actors/Assets) | Read Only |
|-------|------------|--------------------------------|-----------|
| PHOSPHOR ◆ | Motion Design Cloner Expert | CRT_PhosphorGrid (Cloner), M_PhosphorDot, MI_PhosphorDot_* | CRT screen geometry, camera |
| SHADER ⟡ | CRT Material/VFX Expert | M_CRT_Typography, M_CRT_Screen, M_CRT_Frame, MI_CRT_*, M_CRT_Scanline | PostProcess (read only) |
| INTERACT ◈ | 3D UI/Gameplay Expert | CRT_Question_Text, CRT_Option_A/B/C, CRT_Progress, CRT_Selector | All CRT materials (read), bridge state |
| COMPOSE ⬡ | Cinematography/Integration | CRT_Camera, CRT_KeyLight, CRT_FillLight, CRT_PostProcess | All other CRT actors (read) |

**Patch protocol:** If Agent A needs a change in Agent B's actor:
1. Agent A describes the needed change in task output
2. Orchestrator applies the change after Agent B's current task completes

---

## PHASE 1: BUILD FOUNDATION

**Build the CRT phosphor dot grid and material stack. These are the physical substrates
that all other phases layer onto.**

Run PHOSPHOR and SHADER in PARALLEL via Task tool.

### ═══ Agent PHOSPHOR ◆ — Motion Design Cloner Expert ═══

**MOE Expertise:** ClonerEffector instancing, grid layouts, GPU-instanced geometry, procedural placement patterns. Thinks in terms of instance counts, spacing ratios, and LOD thresholds.

**You OWN:** CRT_PhosphorGrid (Cloner actor), any phosphor dot mesh/material instances
**DO NOT TOUCH:** CRT_Typography_Hero, CRT_Camera, CRT_PostProcess, any M_CRT_* materials (SHADER owns those)

**Task P1: Clean up failed Niagara attempts**

Search for any Niagara actors in the scene (CRT_Install_DotGrid, DotGrid_*, etc.) and delete them.
Do NOT delete the Niagara assets from Content Browser — only remove spawned actors.

```
Steps:
1. ue_list_actors — filter for "Niagara" or "DotGrid" type actors
2. For each found: ue_delete_actor
3. Verify: ue_list_actors again, confirm zero Niagara actors remain
```

**Task P2: Create CRT Phosphor Dot Grid Cloner**

Create a ClonerEffector with Grid layout covering the full CRT screen area.

```
Steps:
1. ue_create_cloner with parameters:
   - mesh_path: "/Engine/BasicShapes/Sphere"
   - layout: "Grid"
   - count_x: 100  (horizontal phosphor columns)
   - count_y: 1    (single depth layer)
   - count_z: 60   (vertical phosphor rows)
   - spacing: 43.0 (4310 / 100 = 43.1 unit horizontal spacing)
   - location: (0, 250, 1500) — centered on screen, slightly in front of backing
   - label: "CRT_PhosphorGrid"

2. If ue_create_cloner doesn't support count_z or vertical grid:
   Use ue_execute_python to create the cloner manually:

   import unreal
   eas = unreal.EditorAssetSubsystem()
   ess = unreal.EditorLevelLibrary()
   # Spawn ClonerEffector actor
   cloner = ess.spawn_actor_from_class(
       unreal.ClonerEffector if hasattr(unreal, 'ClonerEffector') else None,
       unreal.Vector(0, 250, 1500)
   )

   FALLBACK: If ClonerEffector plugin is not available, use ue_execute_python to spawn
   a Hierarchical Instanced Static Mesh (HISM) component with 6000 instances:

   import unreal
   # Create an actor with HISM component
   world = unreal.EditorLevelLibrary.get_editor_world()
   actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
       unreal.StaticMeshActor, unreal.Vector(0, 250, 1500))
   actor.set_actor_label('CRT_PhosphorGrid')
   # Add instances in a grid pattern via Python loop

3. Scale each sphere instance to (0.15, 0.15, 0.15) for tiny phosphor dots
4. Verify: ue_get_actor_details on CRT_PhosphorGrid
```

**Task P3: Apply RGB Sub-Pixel Pattern**

Drive the phosphor dots with an RGB color pattern (repeating R, G, B columns).

```
Steps:
1. Via ue_execute_python, apply per-instance color data:
   - Column % 3 == 0: Red tint (1.0, 0.1, 0.1)
   - Column % 3 == 1: Green tint (0.1, 1.0, 0.1)
   - Column % 3 == 2: Blue tint (0.1, 0.1, 1.0)

2. If per-instance color isn't supported on the cloner:
   Create 3 material instances (MI_Phosphor_R, MI_Phosphor_G, MI_Phosphor_B)
   each with different emissive color, and apply them in alternating columns

3. Alternative: Use a single material with world-position-based UV mapping
   that creates the RGB triplet pattern procedurally in the shader

4. Verify: ue_viewport_percept from CRT_Camera position to confirm dot pattern visible
```

---

### ═══ Agent SHADER ⟡ — CRT Material/VFX Expert ═══

**MOE Expertise:** Material graphs, shader parameters, emissive surfaces, post-process materials, CRT display physics (phosphor emission, scanline interference, barrel distortion). Thinks in terms of blend modes, UV coordinates, and physically-based emission.

**You OWN:** M_CRT_Typography, M_CRT_Screen, M_CRT_Frame, M_CRT_Scanline (new), all MI_CRT_* instances
**DO NOT TOUCH:** CRT_PhosphorGrid (PHOSPHOR owns), CRT_PostProcess (COMPOSE owns), question/option TextRenderActors (INTERACT owns)

**Task S1: Fix CRT Typography Material**

The current M_CRT_Typography makes text unreadable (WorldSize=250, emissive too high).

```
Steps:
1. ue_get_material_parameters on M_CRT_Typography — catalog current state
2. Via ue_execute_python, rebuild the material for readable CRT text:

   import unreal
   mel = unreal.MaterialEditingLibrary
   mat = unreal.EditorAssetLibrary.load_asset('/Game/Materials/M_CRT_Typography')

   # Clear and rebuild
   mel.delete_all_material_expressions(mat)

   # Create emissive color node: warm phosphor green (0.0, 1.0, 0.4) * 0.15
   color_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
   color_node.constant = unreal.LinearColor(0.0, 1.0, 0.4, 1.0)  # phosphor green

   multiply = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, 0)
   intensity = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 200)
   intensity.r = 0.15  # readable, not blown out

   mel.connect_material_expressions(color_node, '', multiply, 'A')
   mel.connect_material_expressions(intensity, '', multiply, 'B')
   mel.connect_material_property(multiply, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)

   # Set Unlit, two-sided
   mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
   mat.set_editor_property('two_sided', True)

   mel.recompile_material(mat)

3. Verify: ue_get_material_parameters on M_CRT_Typography confirms new state
```

**Task S2: Enhance CRT Screen Material**

Make M_CRT_Screen glow with subtle phosphor emission (dark background with faint warmth).

```
Steps:
1. ue_get_material_parameters on M_CRT_Screen
2. Via ue_execute_python, rebuild:
   - Base color: near-black (0.02, 0.02, 0.03)
   - Emissive: very dim warm glow (0.01, 0.008, 0.005)
   - Shading model: Unlit
3. Recompile
4. Verify via ue_get_material_parameters
```

**Task S3: Create CRT Scanline Overlay Material**

Create a new material that produces horizontal scanline effect when applied as a decal or screen overlay.

```
Steps:
1. ue_create_material with name "M_CRT_Scanline" at path "/Game/Materials/"
2. Via ue_execute_python, build the scanline shader:

   - Use world-position Z coordinate to create repeating horizontal bands
   - Sine wave on Z position creates alternating bright/dark lines
   - Frequency: ~120 scanlines across 1750 unit height = 14.6 units per line
   - Opacity oscillates: 0.05 (barely visible) to 0.15 (subtle darkening)
   - Blend mode: Translucent
   - Apply as a thin plane actor slightly in front of the dot grid (Y=240)

3. Spawn a plane actor "CRT_ScanlineOverlay" at (0, 240, 1500):
   - Scale to cover full screen area: (43.1, 0.01, 17.5)
   - Assign M_CRT_Scanline material
4. Verify: ue_viewport_percept to confirm scanlines visible
```

**Task S4: Create Material Instances for Typography Variants**

Create instances for question text, option text (normal + highlight), and progress counter.

```
Steps:
1. ue_create_material_instance:
   - MI_CRT_Question: parent M_CRT_Typography, emissive_color=(0.0, 1.0, 0.4), intensity=0.15
   - MI_CRT_Option: parent M_CRT_Typography, emissive_color=(0.0, 0.7, 0.3), intensity=0.10
   - MI_CRT_Option_Highlight: parent M_CRT_Typography, emissive_color=(0.2, 1.0, 0.6), intensity=0.25
   - MI_CRT_Progress: parent M_CRT_Typography, emissive_color=(0.5, 0.5, 0.5), intensity=0.08

2. If M_CRT_Typography doesn't support instance parameters, create separate materials
   with baked-in values for each variant

3. Verify: ue_find_assets with "MI_CRT" confirms all 4 instances exist
```

---

### ═══ PHASE 1 GATE ═══

**Run BEFORE starting Phase 2. Gate is HARD — no skip.**

```
Verification via MCP tools:
1. ue_list_actors — Confirm CRT_PhosphorGrid exists, no Niagara actors remain
2. ue_get_actor_details on CRT_PhosphorGrid — Confirm position (0, 250, 1500)
3. ue_find_assets with "M_CRT" — Confirm M_CRT_Typography, M_CRT_Screen, M_CRT_Scanline exist
4. ue_find_assets with "MI_CRT" — Confirm MI_CRT_Question, MI_CRT_Option, MI_CRT_Option_Highlight, MI_CRT_Progress exist
5. ue_viewport_percept — Capture frame from CRT_Camera, verify dots and screen visible
```

**ALL checks must pass. If ANY fail, fix before proceeding.**

---

## PHASE 2: INTERACTIVE UI

**Build the 3D world-space question system and configure cinematic camera/lighting.**

Run INTERACT and COMPOSE in PARALLEL via Task tool.

### ═══ Agent INTERACT ◈ — 3D UI/Gameplay Expert ═══

**MOE Expertise:** World-space UI, TextRenderActor placement, interactive 3D elements, game flow state machines, bridge protocol integration. Thinks in terms of user experience, readability distance, and interaction feedback loops.

**You OWN:** CRT_Question_Text, CRT_Option_A, CRT_Option_B, CRT_Option_C, CRT_Progress, CRT_Selector
**DO NOT TOUCH:** CRT_PhosphorGrid (PHOSPHOR), materials (SHADER), camera/lights (COMPOSE)
**DEPENDS ON:** Phase 1 materials (MI_CRT_Question, MI_CRT_Option, MI_CRT_Progress)

**Task I1: Spawn 3D Question Text Display**

Replace the oversized CRT_Typography_Hero with a properly configured question TextRenderActor.

```
Steps:
1. ue_set_property on CRT_Typography_Hero:
   - Set visibility to False (hide, don't delete — preserve as backup)

2. ue_spawn_actor: TextRenderActor at (0, 245, 1700)
   - label: "CRT_Question_Text"

3. Via ue_execute_python, configure the text render:
   import unreal
   actor = unreal.EditorLevelLibrary.get_actor_reference('/Game/MainLevel.MainLevel:PersistentLevel.CRT_Question_Text')
   # If actor reference doesn't work, find by label
   actors = unreal.EditorLevelLibrary.get_all_level_actors()
   actor = [a for a in actors if a.get_actor_label() == 'CRT_Question_Text'][0]

   comp = actor.get_component_by_class(unreal.TextRenderComponent)
   comp.set_text('How much can you\nhold at once?')
   comp.set_world_size(40.0)
   comp.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
   comp.set_vertical_alignment(unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)

   # Face camera (rotation: pitch=-90 means lying flat, we want facing -Y toward camera)
   actor.set_actor_rotation(unreal.Rotator(0, -90, 0), False)

4. Assign MI_CRT_Question material (or M_CRT_Typography)
5. Verify: ue_get_actor_details on CRT_Question_Text
```

**Task I2: Spawn Option Buttons (3 TextRenderActors)**

Create three answer options stacked below the question.

```
Steps:
1. Spawn 3 TextRenderActors:
   - CRT_Option_A at (0, 245, 1450) — "A) One deep stream"
   - CRT_Option_B at (0, 245, 1350) — "B) Several parallel currents"
   - CRT_Option_C at (0, 245, 1250) — "C) A vast interconnected web"

   Each with:
   - WorldSize: 30
   - HorizontalAlignment: Center
   - Rotation: (0, -90, 0) facing camera
   - Material: MI_CRT_Option (dim green)

2. Via ue_execute_python, configure each option text render component

3. Verify: ue_list_actors confirms all 3 option actors exist with correct positions
```

**Task I3: Spawn Progress Counter**

Show question progress "1/8" in bottom-right of CRT screen.

```
Steps:
1. ue_spawn_actor: TextRenderActor at (1800, 245, 750)
   - label: "CRT_Progress"
   - Text: "1 / 8"
   - WorldSize: 20
   - Material: MI_CRT_Progress
   - Rotation: (0, -90, 0)

2. Verify position is inside screen bounds (X < 2155, Z > 625)
```

**Task I4: Create Question Cycling Script**

Write a Python script that can be executed via ue_execute_python to cycle through questions.
This bridges the file-based protocol to the 3D world-space UI.

```
Steps:
1. Via ue_execute_python, create a question management script:

   import unreal, json, os

   QUESTIONS = [
       {"text": "How much can you\\nhold at once?", "options": ["One deep stream", "Several parallel currents", "A vast interconnected web"]},
       {"text": "When you're working\\non something...", "options": ["Steady measured progress", "Rhythmic bursts of intensity", "Sustained hyperfocus marathons"]},
       {"text": "When facing\\nthe unknown...", "options": ["Map it systematically", "Dive in and adjust", "Find patterns in the chaos"]},
       {"text": "How do you know you're\\non the right track?", "options": ["External validation", "Internal compass", "Both in balance"]},
       {"text": "After intense effort,\\nwhat restores you?", "options": ["Complete disconnection", "Gentle related activity", "Different intense activity"]},
       {"text": "Beginning\\nsomething new...", "options": ["Follow proven methods", "Adapt existing frameworks", "Invent from scratch"]},
       {"text": "When something\\nis 'done'...", "options": ["When it meets the spec", "When it feels right", "It's never truly done"]},
       {"text": "At your core, you are\\nsomeone who...", "options": ["Builds systems", "Finds connections", "Creates experiences"]}
   ]

   def set_question(index):
       q = QUESTIONS[index]
       actors = unreal.EditorLevelLibrary.get_all_level_actors()

       for a in actors:
           label = a.get_actor_label()
           comp = a.get_component_by_class(unreal.TextRenderComponent)
           if not comp:
               continue
           if label == 'CRT_Question_Text':
               comp.set_text(q['text'])
           elif label == 'CRT_Option_A':
               comp.set_text('A)  ' + q['options'][0])
           elif label == 'CRT_Option_B':
               comp.set_text('B)  ' + q['options'][1])
           elif label == 'CRT_Option_C':
               comp.set_text('C)  ' + q['options'][2])
           elif label == 'CRT_Progress':
               comp.set_text(f'{index + 1} / 8')

   set_question(0)  # Show first question
   print('Question 1 loaded')

2. Test: Run the script, then ue_viewport_percept to verify question displays correctly
3. Test: Run set_question(1) to verify cycling works
```

---

### ═══ Agent COMPOSE ⬡ — Cinematography/Integration Expert ═══

**MOE Expertise:** Camera framing, three-point lighting, post-process color grading, cinematic composition rules (rule of thirds, leading lines), CRT display aesthetics. Thinks in terms of exposure stops, color temperature, and visual hierarchy.

**You OWN:** CRT_Camera, CRT_KeyLight, CRT_FillLight, CRT_PostProcess
**DO NOT TOUCH:** CRT_PhosphorGrid (PHOSPHOR), materials (SHADER), question actors (INTERACT)

**Task C1: Configure CRT Camera Framing**

Optimize camera position and settings for cinematic CRT framing.

```
Steps:
1. ue_get_actor_details on CRT_Camera — baseline
2. ue_set_transform on CRT_Camera:
   - Position: (0, -4500, 1500) — keep current
   - Rotation: (0, 90, 0) — face +Y toward screen

3. Via ue_execute_python, fine-tune CineCameraActor settings:
   import unreal
   actors = unreal.EditorLevelLibrary.get_all_level_actors()
   cam = [a for a in actors if a.get_actor_label() == 'CRT_Camera'][0]

   cine = cam.get_cine_camera_component()
   # Filmback: Super 35 (23.8 x 13.4mm) — cinematic standard
   cine.filmback.sensor_width = 23.8
   cine.filmback.sensor_height = 13.4
   # Focus: Manual, set to screen distance
   cine.focus_settings.focus_method = unreal.CameraFocusMethod.MANUAL
   cine.focus_settings.manual_focus_distance = 4775.0  # distance to screen backing
   # Aperture: f/2.8 for shallow DOF (background softened)
   cine.current_aperture = 2.8

4. Verify: ue_viewport_percept to confirm framing covers full CRT screen
```

**Task C2: Set Cinematic CRT Lighting**

Configure key/fill lights for dramatic CRT-in-dark-room look.

```
Steps:
1. ue_set_property on CRT_KeyLight:
   - Intensity: 0.5 (low — CRT screen IS the key light source)
   - LightColor: (200, 220, 255) — cool blue ambient bounce
   - Set as subtle ambient, NOT dominant light

2. ue_set_property on CRT_FillLight:
   - Intensity: 0.2 (very dim fill)
   - LightColor: (180, 200, 180) — faint green CRT spill
   - AttenuationRadius: 3000

3. IMPORTANT: The CRT screen and phosphor dots are EMISSIVE (Unlit materials).
   They provide their own light. Scene lights should only simulate ambient bounce,
   not illuminate the screen directly.

4. Verify: ue_viewport_percept — screen should glow, room should be dim
```

**Task C3: Configure CRT Post-Process Effects**

Apply cinematic CRT effects to the PostProcess volume.

```
Steps:
1. ue_get_actor_details on CRT_PostProcess — baseline

2. Via ue_execute_python, set all CRT post-process properties:
   import unreal
   actors = unreal.EditorLevelLibrary.get_all_level_actors()
   pp = [a for a in actors if a.get_actor_label() == 'CRT_PostProcess'][0]

   settings = pp.get_editor_property('settings')  # PostProcessSettings

   # Bloom — phosphor glow
   settings.set_editor_property('bloom_intensity', 1.5)
   settings.set_editor_property('bloom_threshold', 0.2)
   settings.set_editor_property('override_bloom_intensity', True)
   settings.set_editor_property('override_bloom_threshold', True)

   # Vignette — CRT edge darkening
   settings.set_editor_property('vignette_intensity', 0.7)
   settings.set_editor_property('override_vignette_intensity', True)

   # Film Grain — analog noise
   settings.set_editor_property('film_grain_intensity', 0.12)
   settings.set_editor_property('override_film_grain_intensity', True)

   # Color Grading — warm CRT phosphor tint
   settings.set_editor_property('scene_color_tint', unreal.LinearColor(1.0, 0.88, 0.92, 1.0))
   settings.set_editor_property('override_scene_color_tint', True)

   # Chromatic Aberration — RGB separation at edges
   settings.set_editor_property('scene_fringe_intensity', 0.8)
   settings.set_editor_property('override_scene_fringe_intensity', True)

   # Auto Exposure — lock to prevent flickering
   settings.set_editor_property('auto_exposure_method', unreal.AutoExposureMethod.AEM_MANUAL)
   settings.set_editor_property('override_auto_exposure_method', True)
   settings.set_editor_property('auto_exposure_bias', 0.0)
   settings.set_editor_property('override_auto_exposure_bias', True)

   print('PostProcess CRT effects applied')

3. Verify: ue_viewport_percept — confirm bloom, vignette, grain visible
```

---

### ═══ PHASE 2 GATE ═══

**Run BEFORE starting Phase 3. Gate is HARD — no skip.**

```
Verification via MCP tools:
1. ue_list_actors — Confirm CRT_Question_Text, CRT_Option_A/B/C, CRT_Progress exist
2. ue_get_actor_details on CRT_Question_Text — Confirm WorldSize=40, position correct
3. ue_get_actor_details on CRT_PostProcess — Confirm bloom, vignette, grain applied
4. ue_viewport_percept — Full frame capture from CRT_Camera:
   - Question text is READABLE (not blown out)
   - Option buttons visible below question
   - Phosphor dot grid visible behind text
   - CRT post-process effects (bloom, vignette, grain) present
   - Overall composition is cinematic
5. Run question cycling test via ue_execute_python: set_question(2) — verify text updates
```

**ALL checks must pass. If ANY fail, fix before proceeding.**

---

## PHASE 3: INTEGRATE & SHIP

**Final integration, beauty capture, and level save.**

Run COMPOSE only (sequential integration tasks).

### ═══ Agent COMPOSE ⬡ — Cinematography/Integration (continued) ═══

**Task C4: Integration Test — Full Question Flow**

Verify the complete CRT display pipeline works end-to-end.

```
Steps:
1. Via ue_execute_python, cycle through ALL 8 questions:
   for i in range(8):
       set_question(i)
   Verify no crashes, all text renders correctly

2. Verify viewport capture at questions 1, 4, and 8 — take 3 screenshots
   via ue_viewport_percept

3. Check actor count hasn't exploded: ue_list_actors — should be ~580 (568 + ~12 new CRT actors)

4. If any question text overflows the screen bounds:
   - Reduce WorldSize
   - Add line breaks to long questions
   - Adjust vertical spacing of options
```

**Task C5: Beauty Capture**

Take the hero screenshot of the CRT display.

```
Steps:
1. Set question to the most visually interesting one (question 8: "At your core...")
   via ue_execute_python: set_question(7)

2. ue_viewport_percept with width=1920, height=1080, format="png"
   — This is the hero capture

3. Also capture via SceneCapture2D for highest quality:
   Via ue_execute_python:
   import unreal
   actors = unreal.EditorLevelLibrary.get_all_level_actors()
   cam = [a for a in actors if a.get_actor_label() == 'CRT_Camera'][0]

   # Spawn SceneCapture2D at camera position
   cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
       unreal.SceneCapture2D, cam.get_actor_location())
   cap.set_actor_rotation(cam.get_actor_rotation(), False)
   cap.get_capture_component2d().capture_scene()

   # Export to file
   rt = cap.get_capture_component2d().texture_target
   unreal.KismetRenderingLibrary.export_render_target(
       unreal.EditorLevelLibrary.get_editor_world(),
       rt,
       'C:/Users/User/AppData/Local/Temp/',
       'crt_beauty_capture')

   # Clean up
   cap.destroy_actor()
   print('Beauty capture saved to C:/Users/User/AppData/Local/Temp/crt_beauty_capture')

4. Report the file path for user review
```

**Task C6: Save Level**

```
Steps:
1. ue_save_level — Save all changes to MainLevel
2. Final ue_list_actors — Report final actor count
3. Final ue_viewport_percept — One last verification capture
```

---

### ═══ PHASE 3 GATE (FINAL) ═══

```
Final verification via MCP tools:
1. ue_list_actors — All CRT actors present, no orphaned Niagara actors
2. ue_viewport_percept — Hero frame is cinematic, readable, CRT-styled
3. Level saved successfully
4. Beauty capture file exists at temp path
```

---

## FINAL STATUS BAR

```
╔══════════════════════════════════════════════════════════════╗
║  UE_Bridge — CRT-CINE — COMPLETE                            ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: BUILD FOUNDATION   [██████████] 100% ✓            ║
║    PHOSPHOR ◆ P1 ✓  P2 ✓  P3 ✓                              ║
║    SHADER   ⟡ S1 ✓  S2 ✓  S3 ✓  S4 ✓                       ║
║                                                              ║
║  Phase 2: INTERACTIVE UI     [██████████] 100% ✓            ║
║    INTERACT ◈ I1 ✓  I2 ✓  I3 ✓  I4 ✓                        ║
║    COMPOSE  ⬡ C1 ✓  C2 ✓  C3 ✓                              ║
║                                                              ║
║  Phase 3: INTEGRATE & SHIP   [██████████] 100% ✓            ║
║    COMPOSE  ⬡ C4 ✓  C5 ✓  C6 ✓                              ║
║                                                              ║
║  Overall: [████████████████████] 100%  (17/17 tasks)         ║
║                                                              ║
║  New actors:    ~12 (PhosphorGrid, ScanlineOverlay,          ║
║                      Question, Options, Progress)            ║
║  Modified:      CRT_Typography_Hero (hidden),                ║
║                 CRT_PostProcess, CRT_KeyLight, CRT_FillLight ║
║  Materials:     M_CRT_Typography (rebuilt),                  ║
║                 M_CRT_Screen (enhanced), M_CRT_Scanline (new)║
║                 MI_CRT_Question/Option/Highlight/Progress    ║
║  Regressions:  0                                             ║
╚══════════════════════════════════════════════════════════════╝
```

---

## SAFETY RULES (ALL AGENTS — NON-NEGOTIABLE)

1. **No Niagara**: Do NOT spawn any Niagara systems. Use ClonerEffector or HISM fallback only.
2. **Emissive ceiling**: Typography emissive NEVER exceeds 0.25. Default is 0.15. Blown-out text = failed task.
3. **Actor budget**: Total scene actors must stay under 650. If approaching limit, reduce cloner instance count.
4. **Read before write**: Always ue_get_actor_details or ue_get_material_parameters before modifying anything.
5. **File ownership**: NEVER modify another agent's actors or materials.
6. **Verify after every change**: Use ue_viewport_percept or ue_get_actor_details after every modification.
7. **Typography is HERO**: If any change makes text less readable, revert immediately.
8. **Natural lighting**: The apartment has natural window lighting. CRT lights provide AMBIENT BOUNCE only, not direct illumination.
9. **Status reporting**: Print status bar after EVERY task completion.
10. **Preserve backups**: Hide actors (visibility=False) instead of deleting when replacing. Original CRT_Typography_Hero stays hidden as fallback.
