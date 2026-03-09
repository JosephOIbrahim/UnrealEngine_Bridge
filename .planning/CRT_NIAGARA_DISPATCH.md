# UnrealEngine_Bridge — CRT Niagara Overlay Grid Dispatch
# Sprint: CRT-B Cinematic Dot Grid
# Date: 2026-03-09
# Status: READY TO EXECUTE

---

## PRE-FLIGHT: Read Before Anything

Before ANY implementation, read these files and internalize their conventions:

```bash
# Understand the CRT installation layout
cat CLAUDE.md
```

Also execute these in UE5 to gather live state:

```python
# PRE-FLIGHT SCRIPT — run via ue_execute_python
import unreal

actors = unreal.EditorLevelLibrary.get_all_level_actors()
crt_actors = [a for a in actors if a.get_actor_label().startswith('CRT_')]
for a in crt_actors:
    loc = a.get_actor_location()
    print(f"{a.get_actor_label()} | {a.get_class().get_name()} | ({loc.x:.0f}, {loc.y:.0f}, {loc.z:.0f})")
```

Report what you find. Do NOT proceed until you understand:
- The CRT installation geometry (frame spans X:-2155 to +2155, Z:625 to 2375)
- CRT_Camera position (0, -6764, 1510) facing +Y, FOV 59.1
- Screen backing at Y=275, frame back at Y=300
- All communication with UE5 is via `ue_execute_python` MCP tool
- Niagara systems: NS_CRT_DotGrid (/Game/Niagara/NS_CRT_DotGrid), NS_DotGrid (/Game/Niagara/NS_DotGrid)
- Materials: M_CRT_Dot (353 px instructions), M_CRT_Dot_Off (365), M_CRT_Pink (365), M_CRT_Screen, M_CRT_Frame

---

## STATUS REPORTING PROTOCOL

**MANDATORY:** After completing each task, print the status bar in this EXACT format.

```
╔══════════════════════════════════════════════════════════════╗
║  UE_Bridge — CRT-B Cinematic Dot Grid STATUS                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: Investigate & Prepare    [░░░░░░░░░░░░░░░░░░░░] 0%║
║    NIAGARA  ◆ N1 ○  N2 ○  N3 ○                              ║
║    MATERIAL ⟡ M1 ○  M2 ○  M3 ○                              ║
║                                                              ║
║  Phase 2: Build & Place            [░░░░░░░░░░░░░░░░░░░░] 0%║
║    NIAGARA  ◆ N4 ○  N5 ○                                    ║
║    MATERIAL ⟡ M4 ○  M5 ○                                    ║
║    COMPOSE  ◈ C1 ○  C2 ○  C3 ○                              ║
║                                                              ║
║  Phase 3: Polish & Capture         [░░░░░░░░░░░░░░░░░░░░] 0%║
║    COMPOSE  ◈ C4 ○  C5 ○  C6 ○                              ║
║                                                              ║
║  Overall: [░░░░░░░░░░░░░░░░░░░░] 0%  (0/16 tasks)          ║
║                                                              ║
║  Legend: ✓ done  ▶ active  ○ pending  ✗ failed              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## ARCHITECTURE DECISIONS (NON-NEGOTIABLE)

### 1. All Work Via Python Execution
Every change to the UE5 scene is done through the `ue_execute_python` MCP tool. No C++ recompilation, no manual editor actions. Python scripts execute inside the UE5 editor process with full access to the `unreal` module.

### 2. Niagara Grid-Based Spawning
The dot grid must use a **grid spawn** pattern (not random scatter). CRT phosphor dots are in perfect rows and columns. The grid must fill the screen area visible from CRT_Camera (X:-2155 to +2155, Z:625 to 2375) at the screen plane (Y~250).

### 3. Scene Capture Verification
After each major visual change, use `SceneCapture2D` from CRT_Camera's position to render a verification image. Export as PNG to `C:/Users/User/AppData/Local/Temp/crt_verify_*.png`. This is how we confirm visual correctness without relying on viewport refresh.

```
CRT_Camera (0, -6764, 1510)  ──────►  Niagara Dot Grid (Y~250)  ──────►  Apartment Scene (Y~350-600)
    FOV 59.1, yaw=90                   RGB phosphor dots                    Retro desk environment
                                       4310 x 1750 units
                                       Grid pattern spacing
```

---

## FILE OWNERSHIP TABLE

| Agent | Role (MOE) | Exclusive Write | Read Only |
|-------|------------|-----------------|-----------|
| NIAGARA ◆ | Niagara particle systems specialist | NS_CRT_DotGrid system (via Python API), CRT_Install_DotGrid actor | M_CRT_Dot, M_CRT_Dot_Off, scene actors |
| MATERIAL ⟡ | Material & shader parameter specialist | M_CRT_Dot, M_CRT_Dot_Off, M_CRT_Pink, M_CRT_Screen materials (via Python API) | Niagara systems, scene actors |
| COMPOSE ◈ | Scene composition & cinematography | CRT_Camera, CRT_KeyLight, CRT_FillLight, CRT_PostProcess actors (via Python API) | Niagara actors, materials |

**Patch protocol:** If Agent A needs a change in Agent B's domain:
1. Agent A describes the needed change in their task output
2. Orchestrator communicates the request to Agent B
3. Agent B applies the change in their next task

---

## PHASE 1: Investigate & Prepare

Deep inspection of existing assets. No scene modifications yet.

Run these agents **in parallel** via Task tool.

### ═══ Agent NIAGARA ◆ — Particle Systems Specialist ═══

**MOE Expertise:** Niagara emitter architecture, spawn modules, GPU simulation, fixed bounds, renderer configuration.
**You OWN:** NS_CRT_DotGrid Niagara system, CRT_Install_DotGrid actor
**DO NOT TOUCH:** Materials, cameras, lights, post-process

**Task N1: Inspect NS_CRT_DotGrid Emitter Architecture**

```python
import unreal

# Load both Niagara systems and compare
for sys_name in ['NS_CRT_DotGrid', 'NS_DotGrid']:
    ns = unreal.load_asset(f"/Game/Niagara/{sys_name}")
    print(f"\n=== {sys_name} ===")
    print(f"Class: {ns.get_class().get_name()}")

    # Check fixed bounds
    try:
        fb = ns.get_editor_property('fixed_bounds')
        print(f"Fixed bounds: min=({fb.min.x:.0f},{fb.min.y:.0f},{fb.min.z:.0f}) max=({fb.max.x:.0f},{fb.max.y:.0f},{fb.max.z:.0f})")
    except: pass

    # Check all accessible properties
    for prop in ['warmup_time', 'warmup_tick_count', 'warmup_tick_delta',
                 'fixed_tick_delta', 'max_pool_size', 'auto_deactivate',
                 'needs_gpu', 'support_large_world_coordinates']:
        try:
            val = ns.get_editor_property(prop)
            print(f"  {prop}: {val}")
        except: pass
```

Report: emitter count, GPU vs CPU sim, fixed bounds size, auto-deactivate state.

**Task N2: Test Niagara Spawn Methods**

Try multiple approaches to expand the dot grid coverage:

```python
import unreal

# Approach 1: Override fixed bounds on the system asset
ns = unreal.load_asset("/Game/Niagara/NS_CRT_DotGrid")
new_bounds = unreal.Box()
new_bounds.min = unreal.Vector(x=-2200, y=-200, z=-900)
new_bounds.max = unreal.Vector(x=2200, y=200, z=900)
try:
    ns.set_editor_property('fixed_bounds', new_bounds)
    print("Fixed bounds expanded")
except Exception as e:
    print(f"Bounds override failed: {e}")

# Approach 2: Set Niagara user parameters for spawn area
actors = unreal.EditorLevelLibrary.get_all_level_actors()
ns_actor = [a for a in actors if a.get_actor_label() == 'CRT_Install_DotGrid']
if ns_actor:
    nc = ns_actor[0].get_component_by_class(unreal.NiagaraComponent)
    # Try common parameter names
    for param in ['User.GridWidth', 'User.GridHeight', 'User.SpawnArea',
                  'User.BoxSize', 'User.Scale', 'User.Extent']:
        try:
            nc.set_niagara_variable_float(param, 4000.0)
            print(f"Set {param} = 4000")
        except: pass
        try:
            nc.set_niagara_variable_vec3(param, unreal.Vector(4310, 400, 1750))
            print(f"Set {param} = (4310, 400, 1750)")
        except: pass
```

Report: which approach works, what parameters are exposed.

**Task N3: Prototype Grid Spawn via Python**

If Niagara parameters don't expand coverage, prototype a pure-Python grid spawn:

```python
import unreal

# Calculate grid dimensions visible from CRT_Camera
# Screen area: X -2155 to +2155 (4310), Z 625 to 2375 (1750)
# Dot spacing for CRT look: ~20-30 units between dots at this scale
screen_width = 4310
screen_height = 1750
dot_spacing = 25  # units

cols = int(screen_width / dot_spacing)
rows = int(screen_height / dot_spacing)
total_dots = cols * rows

print(f"Grid: {cols} cols x {rows} rows = {total_dots} dots")
print(f"Spacing: {dot_spacing} units")
print(f"This many actors may cause performance issues if spawned individually")
print(f"Niagara grid emitter is the better path — need to expand its spawn volume")

# Alternative: create multiple Niagara instances tiled across the screen
tile_size = 200  # units per Niagara tile
tiles_x = int(screen_width / tile_size) + 1
tiles_z = int(screen_height / tile_size) + 1
print(f"\nTiled approach: {tiles_x} x {tiles_z} = {tiles_x * tiles_z} Niagara instances")
print(f"Each tile covers {tile_size}x{tile_size} units")
```

Report: recommended approach (expanded Niagara bounds vs tiled instances vs Python grid).

After completing all tasks, print the status bar.

---

### ═══ Agent MATERIAL ⟡ — Shader Parameter Specialist ═══

**MOE Expertise:** Material expression graphs, parameter tuning, emissive output, blend modes, Niagara sprite material requirements.
**You OWN:** M_CRT_Dot, M_CRT_Dot_Off, M_CRT_Pink, M_CRT_Screen materials
**DO NOT TOUCH:** Niagara systems, cameras, lights, scene actors

**Task M1: Deep Material Inspection**

```python
import unreal

mel = unreal.MaterialEditingLibrary

for mat_name in ['M_CRT_Dot', 'M_CRT_Dot_Off', 'M_CRT_Pink', 'M_CRT_Screen', 'M_CRT_Frame']:
    mat = unreal.load_asset(f"/Game/Materials/{mat_name}")
    print(f"\n=== {mat_name} ===")

    # Full property dump
    stats = mel.get_statistics(mat)
    print(f"  VS instructions: {stats.num_vertex_shader_instructions}")
    print(f"  PS instructions: {stats.num_pixel_shader_instructions}")
    print(f"  Samplers: {stats.num_samplers}")
    print(f"  Pixel tex samples: {stats.num_pixel_texture_samples}")

    # Material properties
    for prop in ['shading_model', 'blend_mode', 'two_sided', 'is_masked',
                 'opacity_mask_clip_value', 'translucency_lighting_mode',
                 'used_with_particle_sprites', 'used_with_niagara_sprites',
                 'used_with_niagara_mesh_particles', 'used_with_beam_trails']:
        try:
            val = mat.get_editor_property(prop)
            print(f"  {prop}: {val}")
        except: pass

    # Parameters
    scalars = mel.get_scalar_parameter_names(mat)
    vectors = mel.get_vector_parameter_names(mat)
    textures = mel.get_texture_parameter_names(mat)
    print(f"  Scalar params: {list(scalars)}")
    print(f"  Vector params: {list(vectors)}")
    print(f"  Texture params: {list(textures)}")
```

Report: which materials are Niagara-compatible (used_with_niagara_sprites), blend modes, and available parameters.

**Task M2: Check Material Niagara Compatibility**

```python
import unreal

# M_CRT_Dot MUST have used_with_niagara_sprites=True to render on Niagara particles
# If not, we need to enable it
mel = unreal.MaterialEditingLibrary

for mat_name in ['M_CRT_Dot', 'M_CRT_Dot_Off', 'M_CRT_Pink']:
    mat = unreal.load_asset(f"/Game/Materials/{mat_name}")

    niagara_sprite = False
    try:
        niagara_sprite = mat.get_editor_property('used_with_niagara_sprites')
    except: pass

    print(f"{mat_name}: used_with_niagara_sprites = {niagara_sprite}")

    if not niagara_sprite:
        try:
            mat.set_editor_property('used_with_niagara_sprites', True)
            print(f"  -> Enabled Niagara sprite usage")
        except Exception as e:
            print(f"  -> Failed to enable: {e}")
```

Report: which materials needed Niagara compatibility enabled.

**Task M3: Inspect Material Visual Output**

```python
import unreal

# Create material instances to test parameter variations
# Render small test captures with each material on a test plane

for mat_name in ['M_CRT_Dot', 'M_CRT_Dot_Off', 'M_CRT_Pink']:
    mat = unreal.load_asset(f"/Game/Materials/{mat_name}")

    # Spawn a test plane with this material
    test_loc = unreal.Vector(x=0, y=-500, z=1500)
    test_plane = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor, test_loc, unreal.Rotator(0, 0, 0)
    )
    test_plane.set_actor_label(f"TEST_{mat_name}")
    smc = test_plane.get_component_by_class(unreal.StaticMeshComponent)
    plane_mesh = unreal.load_asset("/Engine/BasicShapes/Plane")
    smc.set_editor_property('static_mesh', plane_mesh)
    smc.set_material(0, mat)
    test_plane.set_actor_scale3d(unreal.Vector(x=2, y=2, z=1))

    # Capture from above
    rt = unreal.RenderingLibrary.create_render_target2d(
        unreal.EditorLevelLibrary.get_editor_world(), 512, 512,
        unreal.TextureRenderTargetFormat.RTF_RGBA8
    )
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D,
        unreal.Vector(x=0, y=-500, z=1700),
        unreal.Rotator(pitch=-90, yaw=0, roll=0)
    )
    cc = cap.get_component_by_class(unreal.SceneCaptureComponent2D)
    cc.set_editor_property('texture_target', rt)
    cc.set_editor_property('fov_angle', 40)
    cc.capture_scene()

    unreal.RenderingLibrary.export_render_target(
        unreal.EditorLevelLibrary.get_editor_world(), rt,
        "C:/Users/User/AppData/Local/Temp", f"crt_mat_{mat_name}"
    )

    # Cleanup test objects
    unreal.EditorLevelLibrary.destroy_actor(cap)
    unreal.EditorLevelLibrary.destroy_actor(test_plane)

    print(f"Captured {mat_name} preview")

print("Check C:/Users/User/AppData/Local/Temp/crt_mat_*.png")
```

Report: visual appearance of each dot material, recommended material for Niagara sprites.

After completing all tasks, print the status bar.

---

### ═══ PHASE 1 GATE ═══

**Run BEFORE starting Phase 2. Gate is HARD — no skip.**

```python
import unreal

# GATE CHECK: Verify all investigation complete
gate_pass = True
issues = []

# Check 1: Niagara systems loaded
for sys in ['NS_CRT_DotGrid', 'NS_DotGrid']:
    ns = unreal.load_asset(f"/Game/Niagara/{sys}")
    if not ns:
        issues.append(f"{sys} not found")
        gate_pass = False

# Check 2: Materials accessible
for mat in ['M_CRT_Dot', 'M_CRT_Dot_Off', 'M_CRT_Pink']:
    m = unreal.load_asset(f"/Game/Materials/{mat}")
    if not m:
        issues.append(f"{mat} not found")
        gate_pass = False

# Check 3: CRT_Camera correctly oriented
actors = unreal.EditorLevelLibrary.get_all_level_actors()
cam = [a for a in actors if a.get_actor_label() == 'CRT_Camera']
if cam:
    fwd = cam[0].get_actor_forward_vector()
    if abs(fwd.y) < 0.9:
        issues.append(f"CRT_Camera not facing +Y (forward={fwd})")
        gate_pass = False
else:
    issues.append("CRT_Camera not found")
    gate_pass = False

# Check 4: No leftover test actors
test_actors = [a for a in actors if 'TEST_' in a.get_actor_label()]
for a in test_actors:
    unreal.EditorLevelLibrary.destroy_actor(a)

print(f"GATE: {'PASS' if gate_pass else 'FAIL'}")
for issue in issues:
    print(f"  ISSUE: {issue}")
```

**ALL checks must pass. If ANY fail, fix before proceeding.**

Print status bar after gate check.

---

## PHASE 2: Build & Place

Construct the full CRT dot grid and position it. Scene modifications begin.

Run NIAGARA and MATERIAL agents **in parallel**, then COMPOSE **after both complete**.

### ═══ Agent NIAGARA ◆ — Particle Systems Specialist ═══

**Task N4: Deploy Full-Coverage Dot Grid**

Based on Phase 1 findings, deploy the dot grid using the best approach identified (expanded bounds, tiled instances, or Python-spawned grid). The grid must:
- Cover the full screen area (X:-2155 to +2155, Z:625 to 2375)
- Be positioned at Y~240-250 (in front of screen backing at Y=275)
- Have consistent spacing for the CRT phosphor look
- Use RGB sub-pixel pattern (red, green, blue dots in repeating triplets)

If using tiled Niagara instances:
```python
import unreal

ns_system = unreal.load_asset("/Game/Niagara/NS_CRT_DotGrid")
tile_size = 200  # Adjust based on N3 findings

screen_x_min, screen_x_max = -2155, 2155
screen_z_min, screen_z_max = 625, 2375
y_pos = 245  # In front of screen backing

count = 0
for x in range(screen_x_min, screen_x_max, tile_size):
    for z in range(screen_z_min, screen_z_max, tile_size):
        loc = unreal.Vector(x=x + tile_size/2, y=y_pos, z=z + tile_size/2)
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.NiagaraActor, loc, unreal.Rotator(0, 0, 0)
        )
        actor.set_actor_label(f"CRT_Dot_{count}")
        nc = actor.get_component_by_class(unreal.NiagaraComponent)
        nc.set_editor_property('auto_activate', False)
        nc.set_asset(ns_system)
        nc.set_editor_property('auto_activate', True)
        nc.reset_system()
        nc.activate(True)
        count += 1

print(f"Deployed {count} Niagara dot grid tiles")
```

Adapt based on Phase 1 investigation results.

**Task N5: Verify Dot Grid Coverage**

```python
import unreal

# Verify all dot grid actors are active and covering the screen
actors = unreal.EditorLevelLibrary.get_all_level_actors()
dot_actors = [a for a in actors if 'CRT_Dot' in a.get_actor_label() or 'CRT_Install_DotGrid' in a.get_actor_label()]

active_count = 0
total_count = len(dot_actors)
min_x, max_x, min_z, max_z = 9999, -9999, 9999, -9999

for a in dot_actors:
    loc = a.get_actor_location()
    min_x = min(min_x, loc.x)
    max_x = max(max_x, loc.x)
    min_z = min(min_z, loc.z)
    max_z = max(max_z, loc.z)

    nc = a.get_component_by_class(unreal.NiagaraComponent)
    if nc and nc.is_active():
        active_count += 1

print(f"Dot grid actors: {total_count} total, {active_count} active")
print(f"Coverage X: {min_x:.0f} to {max_x:.0f} (target: -2155 to 2155)")
print(f"Coverage Z: {min_z:.0f} to {max_z:.0f} (target: 625 to 2375)")
coverage_x = (max_x - min_x) / 4310 * 100
coverage_z = (max_z - min_z) / 1750 * 100
print(f"Coverage: {coverage_x:.0f}% X, {coverage_z:.0f}% Z")
```

After completing all tasks, print the status bar.

---

### ═══ Agent MATERIAL ⟡ — Shader Parameter Specialist ═══

**Task M4: Configure Dot Materials for Cinematic CRT**

Based on Phase 1 material inspection, tune M_CRT_Dot for optimal cinematic look:

```python
import unreal

mel = unreal.MaterialEditingLibrary

# Ensure Niagara compatibility on all dot materials
for mat_name in ['M_CRT_Dot', 'M_CRT_Dot_Off', 'M_CRT_Pink']:
    mat = unreal.load_asset(f"/Game/Materials/{mat_name}")

    # Enable Niagara sprite rendering
    try:
        mat.set_editor_property('used_with_niagara_sprites', True)
    except: pass

    # For cinematic CRT: dots should be emissive, translucent would allow
    # the scene to show through gaps
    # Check if blend mode allows transparency
    blend = mat.get_editor_property('blend_mode')
    print(f"{mat_name}: blend={blend}")

    # If opaque, the dots will fully block the scene behind them
    # For CRT look, we may want Additive or Translucent blend
    # Only change if currently Opaque and dots need to glow
```

**Task M5: Boost M_CRT_Screen Emissive**

```python
import unreal

# M_CRT_Screen is the backdrop — needs to be visible but not overwhelming
# Check if we can adjust its output via material instance
mat = unreal.load_asset("/Game/Materials/M_CRT_Screen")
mel = unreal.MaterialEditingLibrary

# Create a material instance for tunability
mi_path = "/Game/Materials/MI_CRT_Screen_Tuned"
try:
    mi = unreal.MaterialInstanceConstantFactoryNew().factory_create_new(
        unreal.MaterialInstanceConstant,
        "/Game/Materials",
        "MI_CRT_Screen_Tuned",
        None
    )
    if mi:
        mi.set_editor_property('parent', mat)
        print(f"Created MI: {mi.get_full_name()}")
except Exception as e:
    print(f"MI creation: {e}")
    # Alternative: adjust the base material parameters if any exist
```

After completing all tasks, print the status bar.

---

### ═══ Agent COMPOSE ◈ — Scene Composition & Cinematography ═══

**MOE Expertise:** Camera framing, lighting ratios, post-process grading, visual storytelling.
**You OWN:** CRT_Camera, CRT_KeyLight, CRT_FillLight, CRT_PostProcess
**DO NOT TOUCH:** Niagara systems, materials
**DEPENDS ON:** NIAGARA N4-N5 and MATERIAL M4-M5 must be complete

**Task C1: Optimize CRT_Camera Framing**

```python
import unreal
import math

# Frame the CRT screen perfectly — the dot grid should fill the frame
# with minimal wasted space
actors = unreal.EditorLevelLibrary.get_all_level_actors()
cam = [a for a in actors if a.get_actor_label() == 'CRT_Camera'][0]

# Current: (0, -6764, 1510), FOV 59.1
# Calculate ideal distance for the screen to fill the frame
screen_width = 4310  # units
screen_height = 1750
fov = 59.1

# For horizontal fill: distance = (width/2) / tan(hfov/2)
# Need to account for aspect ratio (16:9)
aspect = 16/9
hfov_rad = math.radians(fov)  # This is actually the vertical FOV for CineCamera
vfov_rad = hfov_rad
hfov_actual = 2 * math.atan(math.tan(vfov_rad/2) * aspect)

dist_for_width = (screen_width / 2) / math.tan(hfov_actual / 2)
dist_for_height = (screen_height / 2) / math.tan(vfov_rad / 2)
ideal_dist = max(dist_for_width, dist_for_height) * 1.05  # 5% margin

screen_center_y = 275
ideal_cam_y = screen_center_y - ideal_dist
screen_center_z = (625 + 2375) / 2  # 1500

print(f"Ideal camera distance: {ideal_dist:.0f} units")
print(f"Ideal camera Y: {ideal_cam_y:.0f}")
print(f"Current camera Y: -6764")

# Update camera position for tighter framing
cam.set_actor_location(
    unreal.Vector(x=0, y=ideal_cam_y, z=screen_center_z), False, False
)
print(f"Camera repositioned to (0, {ideal_cam_y:.0f}, {screen_center_z:.0f})")
```

**Task C2: Tune Lighting for Cinematic CRT**

```python
import unreal

actors = unreal.EditorLevelLibrary.get_all_level_actors()

# CRT_KeyLight — should create dramatic side/top lighting on the frame
key = [a for a in actors if a.get_actor_label() == 'CRT_KeyLight'][0]
key_comp = key.get_component_by_class(unreal.SpotLightComponent)
# Reduce intensity for more dramatic look (key:fill should be ~3:1 or 4:1)
key_comp.set_editor_property('intensity', 1200.0)
# Warm the key slightly
key_comp.set_editor_property('light_color', unreal.Color(r=255, g=240, b=220))
print("Key light: 1200 intensity, warm white")

# CRT_FillLight — subtle fill to prevent crushed blacks
fill = [a for a in actors if a.get_actor_label() == 'CRT_FillLight'][0]
fill_comp = fill.get_component_by_class(unreal.PointLightComponent)
fill_comp.set_editor_property('intensity', 80.0)
# Cool fill for contrast
fill_comp.set_editor_property('light_color', unreal.Color(r=200, g=210, b=255))
print("Fill light: 80 intensity, cool blue")

print(f"Key:Fill ratio = 1200:80 = {1200/80:.0f}:1")
```

**Task C3: Enhance CRT_PostProcess for Cinematic Look**

```python
import unreal

actors = unreal.EditorLevelLibrary.get_all_level_actors()
pp = [a for a in actors if a.get_actor_label() == 'CRT_PostProcess'][0]
settings = pp.get_editor_property('settings')

# Boost bloom for CRT glow
settings.set_editor_property('bloom_intensity', 2.0)
settings.set_editor_property('bloom_threshold', 0.3)

# Stronger vignette for CRT edge darkening
settings.set_editor_property('vignette_intensity', 0.6)

# CRT color grading — warm pinkish phosphor tint
settings.set_editor_property('scene_color_tint',
    unreal.LinearColor(r=1.0, g=0.85, b=0.88, a=1.0))

# Boost saturation on reds (CRT phosphor characteristic)
settings.set_editor_property('color_saturation',
    unreal.Vector4(x=1.5, y=0.95, z=1.05, w=1.0))

# Cinematic tone curve
settings.set_editor_property('film_slope', 0.85)
settings.set_editor_property('film_toe', 0.6)
settings.set_editor_property('film_shoulder', 0.22)

# Slight grain for analog feel
settings.set_editor_property('grain_intensity', 0.15)
settings.set_editor_property('grain_jitter', 0.4)

print("Post-process enhanced for cinematic CRT look")
```

After completing all tasks, print the status bar.

---

### ═══ PHASE 2 GATE ═══

**Run BEFORE starting Phase 3. Gate is HARD — no skip.**

```python
import unreal

gate_pass = True
issues = []

# Check 1: Dot grid coverage > 80%
actors = unreal.EditorLevelLibrary.get_all_level_actors()
dot_actors = [a for a in actors if 'CRT_Dot' in a.get_actor_label() or 'CRT_Install' in a.get_actor_label()]
active = sum(1 for a in dot_actors if a.get_component_by_class(unreal.NiagaraComponent) and a.get_component_by_class(unreal.NiagaraComponent).is_active())

if active == 0:
    issues.append(f"No active Niagara dot grid actors")
    gate_pass = False
else:
    print(f"Active dot grid actors: {active}")

# Check 2: CRT_Camera facing screen
cam = [a for a in actors if a.get_actor_label() == 'CRT_Camera']
if cam:
    fwd = cam[0].get_actor_forward_vector()
    if abs(fwd.y) < 0.9:
        issues.append("CRT_Camera not facing screen")
        gate_pass = False

# Check 3: Verification capture
rt = unreal.RenderingLibrary.create_render_target2d(
    unreal.EditorLevelLibrary.get_editor_world(), 1920, 1080,
    unreal.TextureRenderTargetFormat.RTF_RGBA8
)
cam_actor = cam[0] if cam else None
if cam_actor:
    loc = cam_actor.get_actor_location()
    rot = cam_actor.get_actor_rotation()
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D, loc, rot
    )
    cc = cap.get_component_by_class(unreal.SceneCaptureComponent2D)
    cc.set_editor_property('texture_target', rt)
    cc.set_editor_property('fov_angle', 59.1)
    cc.capture_scene()
    unreal.RenderingLibrary.export_render_target(
        unreal.EditorLevelLibrary.get_editor_world(), rt,
        "C:/Users/User/AppData/Local/Temp", "crt_gate2_verify"
    )
    unreal.EditorLevelLibrary.destroy_actor(cap)
    print("Gate 2 verification image: C:/Users/User/AppData/Local/Temp/crt_gate2_verify")

print(f"\nGATE: {'PASS' if gate_pass else 'FAIL'}")
for issue in issues:
    print(f"  ISSUE: {issue}")
```

Print status bar after gate check.

---

## PHASE 3: Polish & Capture

Final cinematic polish and beauty captures.

Run COMPOSE agent **sequentially** (each task depends on previous).

### ═══ Agent COMPOSE ◈ — Scene Composition & Cinematography ═══

**Task C4: Fine-Tune Dot Grid Density from Camera View**

Review the gate 2 verification image and adjust:
- If dots are too sparse: request NIAGARA to add more tiles or increase spawn rate
- If dots are too dense: request NIAGARA to reduce count or increase spacing
- Adjust Niagara Y position if dots clip through frame elements

**Task C5: Cinematic Beauty Captures**

```python
import unreal

# Take final beauty captures from multiple angles
def beauty_capture(name, loc, rot, fov):
    rt = unreal.RenderingLibrary.create_render_target2d(
        unreal.EditorLevelLibrary.get_editor_world(), 1920, 1080,
        unreal.TextureRenderTargetFormat.RTF_RGBA8
    )
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D, loc, rot
    )
    cc = cap.get_component_by_class(unreal.SceneCaptureComponent2D)
    cc.set_editor_property('texture_target', rt)
    cc.set_editor_property('capture_source', unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    cc.set_editor_property('fov_angle', fov)
    cc.capture_scene()
    unreal.RenderingLibrary.export_render_target(
        unreal.EditorLevelLibrary.get_editor_world(), rt,
        "C:/Users/User/AppData/Local/Temp", name
    )
    unreal.EditorLevelLibrary.destroy_actor(cap)
    print(f"Beauty capture: {name}")

actors = unreal.EditorLevelLibrary.get_all_level_actors()
cam = [a for a in actors if a.get_actor_label() == 'CRT_Camera'][0]
cam_loc = cam.get_actor_location()

# Shot 1: Hero — CRT_Camera main view
beauty_capture("crt_hero",
    cam_loc, cam.get_actor_rotation(), 59.1)

# Shot 2: Detail — close-up on dot grid showing RGB sub-pixels
beauty_capture("crt_detail",
    unreal.Vector(x=0, y=100, z=1500),
    unreal.Rotator(pitch=0, yaw=-90, roll=0), 30)

# Shot 3: Wide — environmental context
beauty_capture("crt_wide",
    unreal.Vector(x=-3000, y=-4000, z=2500),
    unreal.Rotator(pitch=-15, yaw=50, roll=0), 70)

# Shot 4: Low angle — dramatic upshot
beauty_capture("crt_low",
    unreal.Vector(x=0, y=-5000, z=800),
    unreal.Rotator(pitch=10, yaw=90, roll=0), 50)

print("\nAll beauty captures saved to C:/Users/User/AppData/Local/Temp/crt_*.png")
```

**Task C6: Save Level and Final Verification**

```python
import unreal

# Save the level with all changes
unreal.EditorLevelLibrary.save_current_level()
print("Level saved")

# Final actor count
actors = unreal.EditorLevelLibrary.get_all_level_actors()
crt_actors = [a for a in actors if a.get_actor_label().startswith('CRT_')]
niagara_actors = [a for a in actors if a.get_class().get_name() == 'NiagaraActor']

print(f"\nFinal CRT system:")
print(f"  CRT-labeled actors: {len(crt_actors)}")
print(f"  Niagara actors: {len(niagara_actors)}")

for a in crt_actors:
    loc = a.get_actor_location()
    cls = a.get_class().get_name()
    print(f"  {a.get_actor_label()} | {cls} | ({loc.x:.0f}, {loc.y:.0f}, {loc.z:.0f})")
```

After completing all tasks, print the status bar.

---

### ═══ PHASE 3 GATE ═══

**Final gate — sprint complete.**

```python
import unreal
import os

gate_pass = True
issues = []

# Check 1: Beauty captures exist
for name in ['crt_hero', 'crt_detail', 'crt_wide', 'crt_low']:
    path = f"C:/Users/User/AppData/Local/Temp/{name}"
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        print(f"  {name}: OK ({os.path.getsize(path)} bytes)")
    else:
        issues.append(f"Missing or empty: {name}")
        gate_pass = False

# Check 2: Level saved
print(f"\nGATE: {'PASS' if gate_pass else 'FAIL'}")
for issue in issues:
    print(f"  ISSUE: {issue}")
```

Print status bar after gate check.

---

## FINAL STATUS BAR

Print after the last phase gate passes:

```
╔══════════════════════════════════════════════════════════════╗
║  UE_Bridge — CRT-B Cinematic Dot Grid — COMPLETE            ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: Investigate & Prepare    [████████████████████] 100% ✓ ║
║    NIAGARA  ◆ N1 ✓  N2 ✓  N3 ✓                              ║
║    MATERIAL ⟡ M1 ✓  M2 ✓  M3 ✓                              ║
║                                                              ║
║  Phase 2: Build & Place            [████████████████████] 100% ✓ ║
║    NIAGARA  ◆ N4 ✓  N5 ✓                                    ║
║    MATERIAL ⟡ M4 ✓  M5 ✓                                    ║
║    COMPOSE  ◈ C1 ✓  C2 ✓  C3 ✓                              ║
║                                                              ║
║  Phase 3: Polish & Capture         [████████████████████] 100% ✓ ║
║    COMPOSE  ◈ C4 ✓  C5 ✓  C6 ✓                              ║
║                                                              ║
║  Overall: [████████████████████] 100%  (16/16 tasks)         ║
║                                                              ║
║  Beauty captures:  4 (hero, detail, wide, low)               ║
║  Niagara tiles:    TBD (filled at runtime)                   ║
║  Level saved:      Yes                                       ║
║  Regressions:      0                                         ║
╚══════════════════════════════════════════════════════════════╝
```

---

## SAFETY RULES (ALL AGENTS — NON-NEGOTIABLE)

1. **All changes via Python:** Every UE5 modification uses `ue_execute_python` MCP tool. No file edits to .uasset or .umap files directly.
2. **Scene Capture verification:** After visual changes, render a SceneCapture2D from CRT_Camera position to verify. Export to temp directory.
3. **Cleanup test actors:** Any test/temporary actors created during investigation must be destroyed before phase gates.
4. **Preserve existing scene:** Do NOT delete or modify non-CRT actors. The apartment environment must remain intact.
5. **Niagara performance:** Monitor particle counts. If total particles exceed 100,000, optimize spacing or reduce coverage.
6. **Read before write:** Always read existing state and match conventions.
7. **File ownership:** NEVER modify another agent's assets.
8. **Status reporting:** Print status bar after EVERY task completion.
