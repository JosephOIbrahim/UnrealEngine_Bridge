# UnrealEngine_Bridge — CRT Visual Fix Sprint
# Sprint: Fix Screen/Phosphor/Text Layering
# Date: 2026-03-10
# Status: READY TO EXECUTE

---

## PRE-FLIGHT: Read Before Anything

Before ANY implementation, read the project CLAUDE.md:

```bash
cat C:/Users/User/UnrealEngine_Bridge/CLAUDE.md
```

Key context you need:
- This is a UE5.7 project with MCP tools for controlling the editor
- All scene manipulation uses `ue_execute_python` to run Python inside UE5 editor
- The `unreal` Python module is available inside `ue_execute_python`
- `MaterialEditingLibrary` (mel) is accessed via `unreal.MaterialEditingLibrary`
- Materials are at `/Game/Materials/`
- The CRT screen area: X -2155 to +2155, Z 625 to 2375, screen surface at Y=250-275
- Camera (CRT_Camera) at (0, -1800, 1500) facing +Y (yaw=90)

---

## STATUS REPORTING PROTOCOL

**MANDATORY:** After completing each task, print the status bar in this EXACT format.

```
╔══════════════════════════════════════════════════════════════╗
║  CRT-CINE — Visual Fix Sprint STATUS                        ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: Parallel Fixes   [░░░░░░░░░░░░░░░░░░░░] 0%       ║
║    SCREEN  ◆ S1 ○  S2 ○                                     ║
║    PHOSPHOR ⟡ P1 ○  P2 ○                                    ║
║    TEXT     ◈ T1 ○  T2 ○  T3 ○                              ║
║                                                              ║
║  Phase 2: Verify           [░░░░░░░░░░░░░░░░░░░░] 0%       ║
║    VERIFY  ▣ V1 ○                                            ║
║                                                              ║
║  Overall: [░░░░░░░░░░░░░░░░░░░░] 0%  (0/8 tasks)           ║
║                                                              ║
║  Legend: ✓ done  ▶ active  ○ pending  ✗ failed              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## ARCHITECTURE DECISIONS (NON-NEGOTIABLE)

### CRT Screen Layer Stack (front to back from camera)
The camera faces +Y. Lower Y = closer to camera. Layer order:

```
Camera (Y=-1800) ---> Text (Y=200) ---> Scanline (Y=240) ---> Phosphor (Y=250) ---> Screen Backing (Y=275)
```

### Material Approach
- M_CRT_Screen: UNLIT, OPAQUE, near-black emissive (the dark background)
- M_Phosphor_Pink: Should be translucent/masked, very subtle overlay
- MI_CRT_Question/Option/Progress/Typography_Hero: UNLIT with hot pink EmissiveColor, EmissiveIntensity cranked

### UE5 Python Pattern
All modifications use `ue_execute_python` tool with `import unreal` at the top.
Access MaterialEditingLibrary: `mel = unreal.MaterialEditingLibrary`
Load assets: `unreal.load_asset('/Game/Materials/MaterialName')`
Get actors: `unreal.EditorLevelLibrary.get_all_level_actors()`

---

## FILE OWNERSHIP TABLE

| Agent | Role (MOE) | Exclusive Write | Read Only |
|-------|------------|-----------------|-----------|
| SCREEN ◆ | Material/Shader Specialist | M_CRT_Screen, CRT_Screen_Backing actor | All other CRT actors |
| PHOSPHOR ⟡ | VFX/Overlay Specialist | M_Phosphor_Pink, CRT_PhosphorGrid actor | Screen backing, text actors |
| TEXT ◈ | Typography/Layout Specialist | All CRT text actors, MI_CRT_* material instances, MI_CRT_Typography_Hero | Phosphor grid, screen backing |

---

## PHASE 1: Parallel Fixes

Fix the three visual problems simultaneously. Each agent owns distinct actors and materials.

Run these agents **IN PARALLEL** via Task tool.

### ═══ Agent SCREEN ◆ — Material/Shader Specialist ═══

**MOE Expertise:** Deep knowledge of UE5 material graphs, shading models, blend modes. Ensures the screen backing is a solid dark surface that blocks the apartment environment.
**You OWN:** M_CRT_Screen material, CRT_Screen_Backing actor properties
**DO NOT TOUCH:** Any text actors, phosphor grid, or their materials

**Task S1: Inspect M_CRT_Screen current state**

```python
# Run via ue_execute_python
import unreal
mel = unreal.MaterialEditingLibrary

mat = unreal.load_asset('/Game/Materials/M_CRT_Screen')
if mat:
    # Check current properties
    shading = mat.get_editor_property('shading_model')
    blend = mat.get_editor_property('blend_mode')
    scalars = mel.get_scalar_parameter_names(mat)
    vectors = mel.get_vector_parameter_names(mat)
    textures = mel.get_texture_parameter_names(mat)

    # Check emissive connection
    emissive_node = mel.get_material_property_input_node(mat, unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    print(f"Shading: {shading}, Blend: {blend}")
    print(f"Scalars: {[str(n) for n in scalars]}")
    print(f"Vectors: {[str(n) for n in vectors]}")
    print(f"Textures: {[str(n) for n in textures]}")
    print(f"Emissive connected: {emissive_node is not None}")
    if emissive_node:
        print(f"  Node: {emissive_node.get_class().get_name()}")

    num_expr = mel.get_num_material_expressions(mat)
    print(f"Total expressions: {num_expr}")
```

Report what you find. Then proceed to S2.

**Task S2: Make screen backing opaque dark**

Based on S1 findings, make the screen solid dark. The goal is to BLOCK the apartment from showing through.

Strategy:
1. Ensure material is OPAQUE blend mode and UNLIT shading model
2. If it has EmissiveColor/EmissiveIntensity params, set to near-black (very dark blue-black)
3. If the material is transparent/translucent, change blend mode to opaque
4. If the material graph is too complex, rebuild it: delete all expressions, create a single VectorParameter named "ScreenColor" with default (0.01, 0.005, 0.02), connect to emissive

```python
import unreal
mel = unreal.MaterialEditingLibrary

mat = unreal.load_asset('/Game/Materials/M_CRT_Screen')
if mat:
    # Force opaque and unlit
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)

    # Check if it has vector params we can set
    vectors = mel.get_vector_parameter_names(mat)
    scalars = mel.get_scalar_parameter_names(mat)

    # If no emissive connected, rebuild
    emissive_node = mel.get_material_property_input_node(mat, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if not emissive_node:
        mel.delete_all_material_expressions(mat)
        # Create a vector param for screen color
        param = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -300, 0)
        param.set_editor_property('parameter_name', 'ScreenColor')
        param.set_editor_property('default_value', unreal.LinearColor(0.01, 0.005, 0.02, 1.0))
        mel.connect_material_property(param, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    mel.recompile_material(mat)
    print("M_CRT_Screen: set to OPAQUE UNLIT dark emissive")
```

After completing S2, print the status bar.

---

### ═══ Agent PHOSPHOR ⟡ — VFX/Overlay Specialist ═══

**MOE Expertise:** Particle systems, overlay effects, translucent materials. Knows how to make subtle visual layers that add texture without dominating.
**You OWN:** M_Phosphor_Pink material, CRT_PhosphorGrid actor
**DO NOT TOUCH:** Screen backing, text actors, or their materials

**Task P1: Inspect M_Phosphor_Pink and determine fix approach**

```python
import unreal
mel = unreal.MaterialEditingLibrary

mat = unreal.load_asset('/Game/Materials/M_Phosphor_Pink')
if mat:
    shading = mat.get_editor_property('shading_model')
    blend = mat.get_editor_property('blend_mode')
    scalars = mel.get_scalar_parameter_names(mat)
    vectors = mel.get_vector_parameter_names(mat)
    textures = mel.get_texture_parameter_names(mat)

    print(f"Shading: {shading}, Blend: {blend}")
    print(f"Scalars: {[str(n) for n in scalars]}")
    print(f"Vectors: {[str(n) for n in vectors]}")
    print(f"Textures: {[str(n) for n in textures]}")

    num_expr = mel.get_num_material_expressions(mat)
    print(f"Total expressions: {num_expr}")

# Also check actor scale
actors = unreal.EditorLevelLibrary.get_all_level_actors()
for a in actors:
    if a.get_actor_label() == 'CRT_PhosphorGrid':
        scale = a.get_actor_scale3d()
        loc = a.get_actor_location()
        print(f"PhosphorGrid: loc=({loc.x},{loc.y},{loc.z}), scale=({scale.x},{scale.y},{scale.z})")
        comp = a.static_mesh_component
        if comp:
            mesh = comp.get_editor_property('static_mesh')
            print(f"  Mesh: {mesh.get_name() if mesh else 'None'}")
```

Report findings. Then determine approach for P2.

**Task P2: Make phosphor grid subtle**

Based on P1 findings, apply the best fix. Try in this order:

**Approach A — Make translucent + low opacity** (preferred):
- Change blend mode to BLEND_TRANSLUCENT
- Set opacity to 0.08-0.12
- This makes the dot pattern a very subtle overlay

**Approach B — Increase UV tiling** (if material has tiling param):
- Multiply tiling by 15-20x for much finer dots

**Approach C — Fallback: Hide the actor**
- If the material can't be made subtle enough, set actor visibility to false

```python
import unreal
mel = unreal.MaterialEditingLibrary

mat = unreal.load_asset('/Game/Materials/M_Phosphor_Pink')
if mat:
    # Approach A: Make translucent with very low opacity
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)

    # Rebuild with low opacity
    mel.delete_all_material_expressions(mat)

    # Emissive color param
    color_param = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -400, 0)
    color_param.set_editor_property('parameter_name', 'PhosphorColor')
    color_param.set_editor_property('default_value', unreal.LinearColor(1.0, 0.08, 0.52, 1.0))

    # Intensity param
    intensity_param = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -400, 200)
    intensity_param.set_editor_property('parameter_name', 'Intensity')
    intensity_param.set_editor_property('default_value', 2.0)

    # Multiply color * intensity for emissive
    multiply = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, 100)
    mel.connect_material_expressions(color_param, '', multiply, 'A')
    mel.connect_material_expressions(intensity_param, '', multiply, 'B')
    mel.connect_material_property(multiply, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    # Opacity param - very low
    opacity_param = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -400, 400)
    opacity_param.set_editor_property('parameter_name', 'Opacity')
    opacity_param.set_editor_property('default_value', 0.08)
    mel.connect_material_property(opacity_param, '', unreal.MaterialProperty.MP_OPACITY)

    mel.recompile_material(mat)
    print("M_Phosphor_Pink: rebuilt as TRANSLUCENT UNLIT, opacity=0.08")
```

After completing P2, print the status bar.

---

### ═══ Agent TEXT ◈ — Typography/Layout Specialist ═══

**MOE Expertise:** Text rendering, spatial layout, emissive materials for readable screen content. Ensures text is the HERO visual element.
**You OWN:** All CRT text actors (CRT_Typography_Hero, CRT_Question_Text, CRT_Option_A/B/C, CRT_Progress), MI_CRT_* material instances, MI_CRT_Typography_Hero
**DO NOT TOUCH:** Screen backing, phosphor grid, or their materials

**Task T1: Move all text actors forward (lower Y)**

Move all text actors to Y=200 so they're in front of the phosphor grid (Y=250) and scanline overlay (Y=240).

```python
import unreal

text_actors = [
    'CRT_Typography_Hero',
    'CRT_Question_Text',
    'CRT_Option_A',
    'CRT_Option_B',
    'CRT_Option_C',
    'CRT_Progress'
]

actors = unreal.EditorLevelLibrary.get_all_level_actors()
for a in actors:
    label = a.get_actor_label()
    if label in text_actors:
        loc = a.get_actor_location()
        old_y = loc.y
        loc.y = 200.0  # In front of phosphor (250) and scanline (240)
        a.set_actor_location(loc, False, False)
        print(f"{label}: Y {old_y:.0f} -> 200")
```

**Task T2: Verify and boost EmissiveIntensity on all text materials**

Check current EmissiveIntensity values and boost to target levels.
- MI_CRT_Typography_Hero: target 20.0
- MI_CRT_Question: target 10.0
- MI_CRT_Option: target 8.0
- MI_CRT_Option_Highlight: target 15.0
- MI_CRT_Progress: target 5.0

```python
import unreal
mel = unreal.MaterialEditingLibrary

mi_targets = {
    'MI_CRT_Typography_Hero': 20.0,
    'MI_CRT_Question': 10.0,
    'MI_CRT_Option': 8.0,
    'MI_CRT_Option_Highlight': 15.0,
    'MI_CRT_Progress': 5.0,
}

for name, target_intensity in mi_targets.items():
    mi = unreal.load_asset(f'/Game/Materials/{name}')
    if mi:
        current = mel.get_material_instance_scalar_parameter_value(mi, 'EmissiveIntensity')
        mel.set_material_instance_scalar_parameter_value(mi, 'EmissiveIntensity', target_intensity)
        mel.update_material_instance(mi)
        new_val = mel.get_material_instance_scalar_parameter_value(mi, 'EmissiveIntensity')
        print(f"{name}: EmissiveIntensity {current:.1f} -> {new_val:.1f}")
    else:
        print(f"WARN: Could not load {name}")
```

**Task T3: Verify text is facing camera correctly**

Ensure all text actors face the camera (toward -Y direction). TextRenderActors need their forward vector pointing toward the camera.

```python
import unreal

text_actors = [
    'CRT_Typography_Hero',
    'CRT_Question_Text',
    'CRT_Option_A',
    'CRT_Option_B',
    'CRT_Option_C',
    'CRT_Progress'
]

actors = unreal.EditorLevelLibrary.get_all_level_actors()
for a in actors:
    label = a.get_actor_label()
    if label in text_actors:
        rot = a.get_actor_rotation()
        loc = a.get_actor_location()
        # Text should face -Y (toward camera at Y=-1800)
        # For TextRenderActor facing -Y, yaw should be 180 (or -180)
        # Check current and report
        print(f"{label}: loc=({loc.x:.0f},{loc.y:.0f},{loc.z:.0f}), rot=({rot.pitch:.1f},{rot.yaw:.1f},{rot.roll:.1f})")

        # If text isn't facing camera, fix rotation
        # TextRenderActor default faces +X. To face -Y (toward camera), yaw should be -90 or 270
        # Actually, to face the camera at -Y, the text forward should point -Y
        # This depends on the current setup - report first, fix if needed
```

After completing T3, print the status bar.

---

### ═══ PHASE 1 GATE ═══

**Run BEFORE starting Phase 2. Gate is HARD — no skip.**

Use `ue_viewport_percept` to capture the viewport and verify:
1. The screen backing is dark (no apartment objects showing through)
2. The phosphor grid is subtle (not dominating the frame)
3. Text elements are visible as pink glowing content

```python
# Gate check via ue_execute_python
import unreal

# Verify actors exist and are configured
actors = unreal.EditorLevelLibrary.get_all_level_actors()
checks = {
    'screen_dark': False,
    'phosphor_subtle': False,
    'text_forward': False,
}

for a in actors:
    label = a.get_actor_label()
    if label == 'CRT_Screen_Backing':
        mat = a.static_mesh_component.get_material(0)
        if mat and mat.get_name() == 'M_CRT_Screen':
            blend = unreal.load_asset('/Game/Materials/M_CRT_Screen').get_editor_property('blend_mode')
            checks['screen_dark'] = (blend == unreal.BlendMode.BLEND_OPAQUE)
    elif label == 'CRT_PhosphorGrid':
        checks['phosphor_subtle'] = True  # Will be verified visually
    elif label == 'CRT_Question_Text':
        loc = a.get_actor_location()
        checks['text_forward'] = (loc.y < 240)  # In front of overlays

for check, passed in checks.items():
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {check}")
```

Also capture viewport with `ue_viewport_percept` format=jpeg width=1920 height=1080 and visually confirm.

**ALL checks must pass. If ANY fail, fix before proceeding.**

Print status bar after gate check.

---

## PHASE 2: Verify

Capture a beauty frame and report results.

### ═══ Agent VERIFY ▣ — Quality Assurance ═══

**Task V1: Capture and report**

Take a viewport capture via `ue_viewport_percept` with format=jpeg, width=1920, height=1080.
Describe what you see:
- Is the screen dark?
- Are text elements visible and pink?
- Is the phosphor grid subtle?
- Does it look closer to the CRT reference aesthetic?

Print final status bar.

---

### ═══ PHASE 2 GATE ═══

Visual confirmation from the viewport capture. Report findings.

---

## FINAL STATUS BAR

Print after the last phase gate passes:

```
╔══════════════════════════════════════════════════════════════╗
║  CRT-CINE — Visual Fix Sprint — COMPLETE                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: Parallel Fixes   [████████████████████] 100% ✓    ║
║    SCREEN  ◆ S1 ✓  S2 ✓                                     ║
║    PHOSPHOR ⟡ P1 ✓  P2 ✓                                    ║
║    TEXT     ◈ T1 ✓  T2 ✓  T3 ✓                              ║
║                                                              ║
║  Phase 2: Verify           [████████████████████] 100% ✓    ║
║    VERIFY  ▣ V1 ✓                                            ║
║                                                              ║
║  Overall: [████████████████████] 100%  (8/8 tasks)           ║
║                                                              ║
║  Modified:     M_CRT_Screen, M_Phosphor_Pink, MI_CRT_*      ║
║  Actors moved: 6 text actors to Y=200                        ║
║  Regressions:  0                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## SAFETY RULES (ALL AGENTS — NON-NEGOTIABLE)

1. **UE5 Python only:** All modifications go through `ue_execute_python` — no file system edits to .uasset files
2. **Read before write:** Always inspect material/actor state before modifying
3. **File ownership:** NEVER modify another agent's materials or actors
4. **Recompile after material changes:** Always call `mel.recompile_material(mat)` after modifying base materials
5. **Update after MI changes:** Always call `mel.update_material_instance(mi)` after modifying material instances
6. **Status reporting:** Print status bar after EVERY task completion
7. **No destructive actor operations:** Don't delete actors — only modify properties, materials, transforms
