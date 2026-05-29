"""Lighting, sky & atmosphere tools for UE5 world-building.

Collapses the 6-actor sky rig (DirectionalLight, SkyAtmosphere, SkyLight,
ExponentialHeightFog, VolumetricCloud, PostProcessVolume) and its inter-
dependencies into single coherent verbs: build a sky, set a time of day, or
apply/blend a named cinematic mood.

All five tools resolve their inputs into one `settings` dict and run the SAME
idempotent rig routine (`_RIG_CODE`) in the editor — find-or-spawn each actor,
apply only the settings provided, and recapture the sky LAST (after the
atmosphere is configured, or ambient bounce won't match). Every property write
is best-effort and reported as applied/skipped, so a name that differs across
engine versions degrades gracefully instead of aborting the rig.

Tools:
- ue_setup_sky_atmosphere : build/update the sky rig (sun angle, intensity, fog, clouds)
- ue_set_time_of_day      : hour 0-24 -> sun elevation/azimuth/colour/intensity
- ue_list_mood_presets    : list the built-in cinematic mood presets
- ue_apply_mood_preset    : apply a coordinated sun + fog + clouds + colour-grade package
- ue_blend_mood_presets   : interpolate between two presets (t in 0..1) and apply
"""

from __future__ import annotations

import json
import logging
import math

from ._types import MCPServer, UEBridge
from ._validation import make_error

logger = logging.getLogger("ue5-mcp.tools.lighting")


# --------------------------------------------------------------------------- #
# Mood presets — server-side data. Values are a tasteful starting point a
# look-dev artist will tweak; they never reach the codegen sanitizer (only the
# preset NAME is validated, by dict membership).
# --------------------------------------------------------------------------- #

_MOOD_PRESETS: dict[str, dict] = {
    "golden_hour": {
        "description": "Warm low sun, light haze, soft bloom — the magic hour.",
        "sun_elevation": 8.0, "sun_azimuth": 100.0, "sun_intensity": 6.0,
        "sun_color": [1.0, 0.74, 0.45], "fog_density": 0.015, "fog_color": [0.9, 0.6, 0.4],
        "volumetric_fog": True, "clouds": True,
        "post": {"exposure_bias": 0.0, "white_temp": 7200.0, "saturation": 1.12,
                 "contrast": 1.05, "bloom": 0.8, "vignette": 0.4, "film_grain": 0.04},
    },
    "noir": {
        "description": "Cold low key, heavy fog, crushed contrast, deep vignette.",
        "sun_elevation": 12.0, "sun_azimuth": 220.0, "sun_intensity": 2.5,
        "sun_color": [0.7, 0.78, 1.0], "fog_density": 0.05, "fog_color": [0.15, 0.18, 0.25],
        "volumetric_fog": True, "clouds": True,
        "post": {"exposure_bias": -0.5, "white_temp": 5200.0, "saturation": 0.45,
                 "contrast": 1.3, "bloom": 0.3, "vignette": 0.7, "film_grain": 0.16},
    },
    "horror_morning": {
        "description": "Pale cold sun, thick volumetric mist, sickly desaturation, grain.",
        "sun_elevation": 6.0, "sun_azimuth": 80.0, "sun_intensity": 1.8,
        "sun_color": [0.8, 0.9, 0.85], "fog_density": 0.09, "fog_color": [0.5, 0.55, 0.5],
        "volumetric_fog": True, "clouds": True,
        "post": {"exposure_bias": -0.3, "white_temp": 6000.0, "saturation": 0.6,
                 "contrast": 1.15, "bloom": 0.4, "vignette": 0.6, "film_grain": 0.2},
    },
    "overcast": {
        "description": "Flat diffuse grey daylight, low contrast, full cloud cover.",
        "sun_elevation": 40.0, "sun_azimuth": 160.0, "sun_intensity": 4.0,
        "sun_color": [0.9, 0.92, 0.95], "fog_density": 0.01, "fog_color": [0.6, 0.62, 0.65],
        "volumetric_fog": False, "clouds": True,
        "post": {"exposure_bias": 0.0, "white_temp": 6800.0, "saturation": 0.85,
                 "contrast": 0.95, "bloom": 0.4, "vignette": 0.3, "film_grain": 0.03},
    },
    "midday_clear": {
        "description": "High neutral sun, crisp clear sky, slight punch.",
        "sun_elevation": 75.0, "sun_azimuth": 180.0, "sun_intensity": 10.0,
        "sun_color": [1.0, 0.98, 0.95], "fog_density": 0.002, "fog_color": [0.7, 0.8, 1.0],
        "volumetric_fog": False, "clouds": True,
        "post": {"exposure_bias": 0.0, "white_temp": 6500.0, "saturation": 1.05,
                 "contrast": 1.05, "bloom": 0.6, "vignette": 0.2, "film_grain": 0.0},
    },
    "moonlit_night": {
        "description": "Dim cool moon below-horizon ambient, fog, dark cool grade.",
        "sun_elevation": -8.0, "sun_azimuth": 30.0, "sun_intensity": 0.08,
        "sun_color": [0.5, 0.6, 0.95], "fog_density": 0.03, "fog_color": [0.05, 0.08, 0.18],
        "volumetric_fog": True, "clouds": True,
        "post": {"exposure_bias": 0.4, "white_temp": 5000.0, "saturation": 0.7,
                 "contrast": 1.1, "bloom": 0.5, "vignette": 0.6, "film_grain": 0.12},
    },
    "product_shot": {
        "description": "Clean high-key neutral studio light, no fog, minimal grade.",
        "sun_elevation": 55.0, "sun_azimuth": 200.0, "sun_intensity": 8.0,
        "sun_color": [1.0, 1.0, 1.0], "fog_density": 0.0, "fog_color": [0.8, 0.8, 0.8],
        "volumetric_fog": False, "clouds": False,
        "post": {"exposure_bias": 0.0, "white_temp": 6500.0, "saturation": 1.0,
                 "contrast": 1.0, "bloom": 0.5, "vignette": 0.1, "film_grain": 0.0},
    },
}


# --------------------------------------------------------------------------- #
# The shared editor-Python rig routine. PLAIN string (not an f-string): normal
# braces, no escaping. Reads a module-global `settings` dict injected ahead of it.
# --------------------------------------------------------------------------- #

_RIG_CODE = '''
applied = []
skipped = []

def _safe_set(obj, prop, value):
    try:
        obj.set_editor_property(prop, value)
        applied.append(prop)
        return True
    except Exception:
        skipped.append(prop)
        return False

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
all_actors = eas.get_all_level_actors()

def _find(cls):
    for a in all_actors:
        if isinstance(a, cls):
            return a
    return None

def _get_or_spawn(cls):
    a = _find(cls)
    if a is None:
        a = eas.spawn_actor_from_class(cls, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    return a

report = {}

# ---- Sun (DirectionalLight) ----
sun = _get_or_spawn(unreal.DirectionalLight)
elev = settings.get("sun_elevation")
azim = settings.get("sun_azimuth")
if elev is not None or azim is not None:
    cur = sun.get_actor_rotation()
    pitch = -float(elev) if elev is not None else cur.pitch
    yaw = float(azim) if azim is not None else cur.yaw
    sun.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), False)
sun_comp = sun.get_component_by_class(unreal.DirectionalLightComponent)
if sun_comp:
    _safe_set(sun_comp, "atmosphere_sun_light", True)
    if settings.get("sun_intensity") is not None:
        _safe_set(sun_comp, "intensity", float(settings["sun_intensity"]))
    if settings.get("sun_color") is not None:
        c = settings["sun_color"]
        lc = unreal.LinearColor(float(c[0]), float(c[1]), float(c[2]), 1.0)
        try:
            sun_comp.set_light_color(lc)
            applied.append("light_color")
        except Exception:
            _safe_set(sun_comp, "light_color",
                      unreal.Color(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255), 255))
report["sun"] = sun.get_actor_label()

# ---- SkyAtmosphere (defaults are fine; presence is what matters) ----
atmo = _get_or_spawn(unreal.SkyAtmosphere)
report["atmosphere"] = atmo.get_actor_label()

# ---- ExponentialHeightFog ----
if (settings.get("fog_density") is not None or settings.get("fog_color") is not None
        or settings.get("volumetric_fog") is not None):
    fog = _get_or_spawn(unreal.ExponentialHeightFog)
    fog_comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    if fog_comp:
        if settings.get("fog_density") is not None:
            _safe_set(fog_comp, "fog_density", float(settings["fog_density"]))
        if settings.get("fog_color") is not None:
            c = settings["fog_color"]
            _safe_set(fog_comp, "fog_inscattering_color",
                      unreal.LinearColor(float(c[0]), float(c[1]), float(c[2]), 1.0))
        if settings.get("volumetric_fog") is not None:
            _safe_set(fog_comp, "volumetric_fog", bool(settings["volumetric_fog"]))
    report["fog"] = fog.get_actor_label()

# ---- Volumetric clouds (presence toggle) ----
if settings.get("clouds") is not None:
    cloud = _find(unreal.VolumetricCloud)
    if settings["clouds"] and cloud is None:
        eas.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
        report["clouds"] = "added"
    elif (not settings["clouds"]) and cloud is not None:
        eas.destroy_actor(cloud)
        report["clouds"] = "removed"
    else:
        report["clouds"] = "unchanged"

# ---- Post-process colour grade (global PostProcessVolume) ----
post = settings.get("post")
if post:
    ppv = _find(unreal.PostProcessVolume)
    if ppv is None:
        ppv = eas.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    _safe_set(ppv, "unbound", True)
    ps = ppv.get_editor_property("settings")

    def _ps(flag, prop, value):
        try:
            ps.set_editor_property(flag, True)
            ps.set_editor_property(prop, value)
            applied.append(prop)
        except Exception:
            skipped.append(prop)

    if post.get("exposure_bias") is not None:
        _ps("override_auto_exposure_bias", "auto_exposure_bias", float(post["exposure_bias"]))
    if post.get("white_temp") is not None:
        _ps("override_white_temp", "white_temp", float(post["white_temp"]))
    if post.get("white_tint") is not None:
        _ps("override_white_tint", "white_tint", float(post["white_tint"]))
    if post.get("saturation") is not None:
        s = float(post["saturation"])
        _ps("override_color_saturation", "color_saturation", unreal.Vector4(s, s, s, 1.0))
    if post.get("contrast") is not None:
        s = float(post["contrast"])
        _ps("override_color_contrast", "color_contrast", unreal.Vector4(s, s, s, 1.0))
    if post.get("gamma") is not None:
        s = float(post["gamma"])
        _ps("override_color_gamma", "color_gamma", unreal.Vector4(s, s, s, 1.0))
    if post.get("gain") is not None:
        s = float(post["gain"])
        _ps("override_color_gain", "color_gain", unreal.Vector4(s, s, s, 1.0))
    if post.get("bloom") is not None:
        _ps("override_bloom_intensity", "bloom_intensity", float(post["bloom"]))
    if post.get("vignette") is not None:
        _ps("override_vignette_intensity", "vignette_intensity", float(post["vignette"]))
    if post.get("film_grain") is not None:
        _ps("override_film_grain_intensity", "film_grain_intensity", float(post["film_grain"]))
    ppv.set_editor_property("settings", ps)
    report["post_process"] = ppv.get_actor_label()

# ---- SkyLight LAST: recapture AFTER the atmosphere is configured ----
sky = _get_or_spawn(unreal.SkyLight)
sky_comp = sky.get_component_by_class(unreal.SkyLightComponent)
if sky_comp:
    _safe_set(sky_comp, "real_time_capture", True)
    if settings.get("recapture", True):
        try:
            sky_comp.recapture_sky()
            applied.append("recapture_sky")
        except Exception:
            try:
                sky_comp.recapture()
                applied.append("recapture")
            except Exception:
                skipped.append("recapture_sky")
report["sky_light"] = sky.get_actor_label()

report["sun_elevation"] = settings.get("sun_elevation")
report["sun_azimuth"] = settings.get("sun_azimuth")
report["applied"] = applied
report["skipped"] = skipped
print("RESULT:" + json.dumps(report))
'''


def _rig_code(settings: dict) -> str:
    """Prepend the injected settings to the shared rig routine.

    Uses repr() of the JSON string for safe quoting; cannot use an f-string here
    because _RIG_CODE is full of literal braces.
    """
    injected = repr(json.dumps(settings))
    return "import unreal, json\nsettings = json.loads(" + injected + ")\n" + _RIG_CODE


def _tod_settings(hour: float) -> dict:
    """Map an hour (0-24) to a coherent sun + colour + intensity setting.

    Daytime ~6..18; sun peaks near noon. Intensity is in the editor's relative
    range (~0.08 moonlight .. ~10 noon) and is easy to override.
    """
    hour = max(0.0, min(24.0, hour))
    elevation = 80.0 * math.sin(math.pi * (hour - 6.0) / 12.0)
    azimuth = (hour / 24.0 * 360.0 + 90.0) % 360.0
    e = max(0.0, elevation)
    if elevation <= 0.0:
        intensity = 0.08
        sun_color = [0.5, 0.6, 0.95]  # cool moonlight
    else:
        intensity = 1.0 + 9.0 * (e / 80.0)
        warmth = max(0.0, 1.0 - e / 30.0)  # warm near the horizon, neutral up high
        sun_color = [1.0, 1.0 - 0.32 * warmth, 1.0 - 0.58 * warmth]
    return {
        "sun_elevation": round(elevation, 2),
        "sun_azimuth": round(azimuth, 2),
        "sun_intensity": round(intensity, 3),
        "sun_color": [round(c, 3) for c in sun_color],
        "clouds": True,
        "recapture": True,
    }


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _blend(pa: dict, pb: dict, t: float) -> dict:
    """Interpolate two preset dicts. Numbers/colours lerp; bools snap at t=0.5."""
    out: dict = {}
    for k in set(pa) | set(pb):
        va, vb = pa.get(k), pb.get(k)
        if k == "description":
            continue
        if isinstance(va, bool) or isinstance(vb, bool):
            out[k] = vb if t >= 0.5 else va
        elif isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            out[k] = round(_lerp(va, vb, t), 4)
        elif isinstance(va, list) and isinstance(vb, list) and len(va) == len(vb):
            out[k] = [round(_lerp(x, y, t), 4) for x, y in zip(va, vb, strict=False)]
        elif isinstance(va, dict) and isinstance(vb, dict):
            out[k] = _blend(va, vb, t)
        else:
            out[k] = vb if t >= 0.5 else va
    return out


def register(server: MCPServer, ue: UEBridge) -> None:
    @server.tool(
        name="ue_setup_sky_atmosphere",
        description=(
            "Build or update the sky/atmosphere rig in one call: find-or-spawn the "
            "DirectionalLight (sun), SkyAtmosphere, SkyLight, fog, and clouds, then "
            "recapture the sky. sun_elevation is degrees above the horizon, sun_azimuth "
            "is the compass heading. Idempotent — reuses existing rig actors."
        ),
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    )
    async def setup_sky_atmosphere(
        sun_elevation: float = 45.0,
        sun_azimuth: float = 135.0,
        sun_intensity: float | None = None,
        fog: bool = False,
        fog_density: float = 0.02,
        clouds: bool = True,
    ) -> str:
        """Create/update the atmosphere rig."""
        settings: dict = {
            "sun_elevation": sun_elevation,
            "sun_azimuth": sun_azimuth,
            "clouds": clouds,
            "recapture": True,
        }
        if sun_intensity is not None:
            settings["sun_intensity"] = sun_intensity
        if fog:
            settings["fog_density"] = fog_density
            settings["volumetric_fog"] = True
        result = await ue.execute_python(_rig_code(settings))
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_time_of_day",
        description=(
            "Set the time of day (hour 0-24) — drives sun elevation, compass azimuth, "
            "colour temperature (warm near the horizon, neutral high, cool moonlight at "
            "night), and intensity. Builds/reuses the sky rig and recaptures."
        ),
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    )
    async def set_time_of_day(hour: float = 12.0) -> str:
        """Map an hour to a sky setting and apply it."""
        settings = _tod_settings(hour)
        settings["_hour"] = round(max(0.0, min(24.0, hour)), 2)
        result = await ue.execute_python(_rig_code(settings))
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_list_mood_presets",
        description="List the built-in cinematic mood/look-dev presets and their descriptions.",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    )
    async def list_mood_presets() -> str:
        """Return the preset catalog (no editor round-trip)."""
        presets = [{"name": n, "description": p["description"]} for n, p in _MOOD_PRESETS.items()]
        return json.dumps({"count": len(presets), "presets": presets}, indent=2)

    @server.tool(
        name="ue_apply_mood_preset",
        description=(
            "Apply a named cinematic mood as a coordinated package — sun angle/colour, "
            "fog, clouds, and a full post-process colour grade. Call ue_list_mood_presets "
            "for available names (e.g. golden_hour, noir, overcast, midday_clear)."
        ),
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    )
    async def apply_mood_preset(name: str) -> str:
        """Apply a coordinated mood preset."""
        if name not in _MOOD_PRESETS:
            return make_error(f"Unknown preset '{name}'. Available: {', '.join(sorted(_MOOD_PRESETS))}")
        preset = {k: v for k, v in _MOOD_PRESETS[name].items() if k != "description"}
        preset["recapture"] = True
        result = await ue.execute_python(_rig_code(preset))
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_blend_mood_presets",
        description=(
            "Blend two mood presets and apply the result. t=0 is preset_a, t=1 is "
            "preset_b; numeric/colour values interpolate, toggles snap at t>=0.5. "
            "Great for dialing a look between two references."
        ),
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    )
    async def blend_mood_presets(preset_a: str, preset_b: str, t: float = 0.5) -> str:
        """Interpolate between two presets and apply."""
        for n in (preset_a, preset_b):
            if n not in _MOOD_PRESETS:
                return make_error(f"Unknown preset '{n}'. Available: {', '.join(sorted(_MOOD_PRESETS))}")
        t = max(0.0, min(1.0, t))
        blended = _blend(_MOOD_PRESETS[preset_a], _MOOD_PRESETS[preset_b], t)
        blended["recapture"] = True
        result = await ue.execute_python(_rig_code(blended))
        return json.dumps(result, indent=2)
