"""Tests for ue_mcp/tools/lighting.py — sky/atmosphere & mood-preset tools."""

import ast
import json
import re

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.lighting import _MOOD_PRESETS, _blend, _tod_settings, register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


def _gen_code(mock_ue):
    return mock_ue.execute_python.call_args[0][0]


def _extract_settings(code):
    """Pull the injected `settings = json.loads(<repr>)` dict back out."""
    m = re.search(r"settings = json\.loads\((.*?)\)\n", code, re.DOTALL)
    assert m, "no settings injection found in generated code"
    return json.loads(ast.literal_eval(m.group(1)))


# --------------------------------------------------------------------------- #
# Pure-function unit tests (no editor)
# --------------------------------------------------------------------------- #


class TestTimeOfDayMath:
    def test_noon_is_high(self):
        s = _tod_settings(12.0)
        assert s["sun_elevation"] > 70.0
        assert s["sun_intensity"] > 5.0

    def test_sunrise_near_horizon(self):
        assert abs(_tod_settings(6.0)["sun_elevation"]) < 1.0

    def test_night_is_below_horizon_and_cool(self):
        s = _tod_settings(0.0)
        assert s["sun_elevation"] <= 0.0
        assert s["sun_intensity"] < 0.5
        # cool moonlight: blue channel brighter than red
        assert s["sun_color"][2] > s["sun_color"][0]

    def test_hour_is_clamped(self):
        assert _tod_settings(99.0)["sun_elevation"] == _tod_settings(24.0)["sun_elevation"]


class TestBlend:
    def test_t0_takes_a(self):
        b = _blend(_MOOD_PRESETS["golden_hour"], _MOOD_PRESETS["noir"], 0.0)
        assert b["sun_elevation"] == _MOOD_PRESETS["golden_hour"]["sun_elevation"]

    def test_t1_takes_b(self):
        b = _blend(_MOOD_PRESETS["golden_hour"], _MOOD_PRESETS["noir"], 1.0)
        assert b["sun_elevation"] == _MOOD_PRESETS["noir"]["sun_elevation"]

    def test_midpoint_interpolates(self):
        a = _MOOD_PRESETS["golden_hour"]["sun_elevation"]
        c = _MOOD_PRESETS["noir"]["sun_elevation"]
        b = _blend(_MOOD_PRESETS["golden_hour"], _MOOD_PRESETS["noir"], 0.5)
        assert b["sun_elevation"] == pytest.approx((a + c) / 2.0)

    def test_nested_post_blends(self):
        b = _blend(_MOOD_PRESETS["golden_hour"], _MOOD_PRESETS["noir"], 0.5)
        assert "post" in b and isinstance(b["post"], dict)
        assert "saturation" in b["post"]

    def test_description_dropped(self):
        b = _blend(_MOOD_PRESETS["golden_hour"], _MOOD_PRESETS["noir"], 0.5)
        assert "description" not in b


# --------------------------------------------------------------------------- #
# _RIG_CODE always produces syntactically valid Python
# --------------------------------------------------------------------------- #


class TestRigCodeValidity:
    def test_full_preset_code_parses(self):
        from ue_mcp.tools.lighting import _rig_code
        preset = {k: v for k, v in _MOOD_PRESETS["golden_hour"].items() if k != "description"}
        ast.parse(_rig_code(preset))

    def test_recapture_is_last(self):
        from ue_mcp.tools.lighting import _RIG_CODE
        # recapture must come after the atmosphere is configured
        assert _RIG_CODE.index("SkyAtmosphere") < _RIG_CODE.index("recapture_sky")


# --------------------------------------------------------------------------- #
# ue_setup_sky_atmosphere
# --------------------------------------------------------------------------- #


class TestSetupSkyAtmosphere:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_setup_sky_atmosphere")
        result = await fn(sun_elevation=30.0, sun_azimuth=120.0)
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert "SkyAtmosphere" in code and "recapture_sky" in code
        assert "atmosphere_sun_light" in code
        s = _extract_settings(code)
        assert s["sun_elevation"] == 30.0 and s["sun_azimuth"] == 120.0

    @pytest.mark.asyncio
    async def test_fog_adds_volumetric_settings(self, server, mock_ue):
        fn = _call(server, "ue_setup_sky_atmosphere")
        await fn(fog=True, fog_density=0.05)
        s = _extract_settings(_gen_code(mock_ue))
        assert s["fog_density"] == 0.05
        assert s["volumetric_fog"] is True

    @pytest.mark.asyncio
    async def test_no_fog_by_default(self, server, mock_ue):
        fn = _call(server, "ue_setup_sky_atmosphere")
        await fn()
        s = _extract_settings(_gen_code(mock_ue))
        assert "fog_density" not in s


# --------------------------------------------------------------------------- #
# ue_set_time_of_day
# --------------------------------------------------------------------------- #


class TestSetTimeOfDay:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_set_time_of_day")
        result = await fn(hour=7.0)
        data = json.loads(result)
        assert "error" not in data
        ast.parse(_gen_code(mock_ue))

    @pytest.mark.asyncio
    async def test_noon_vs_dawn_differ(self, server, mock_ue):
        fn = _call(server, "ue_set_time_of_day")
        await fn(hour=12.0)
        noon = _extract_settings(_gen_code(mock_ue))
        await fn(hour=6.0)
        dawn = _extract_settings(_gen_code(mock_ue))
        assert noon["sun_elevation"] > dawn["sun_elevation"]


# --------------------------------------------------------------------------- #
# ue_list_mood_presets
# --------------------------------------------------------------------------- #


class TestListMoodPresets:
    @pytest.mark.asyncio
    async def test_lists_known_presets(self, server, mock_ue):
        fn = _call(server, "ue_list_mood_presets")
        data = json.loads(await fn())
        names = {p["name"] for p in data["presets"]}
        assert {"golden_hour", "noir", "midday_clear"} <= names
        mock_ue.execute_python.assert_not_awaited()  # pure data, no editor round-trip


# --------------------------------------------------------------------------- #
# ue_apply_mood_preset
# --------------------------------------------------------------------------- #


class TestApplyMoodPreset:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_apply_mood_preset")
        result = await fn(name="golden_hour")
        data = json.loads(result)
        assert "error" not in data
        code = _gen_code(mock_ue)
        ast.parse(code)
        assert "auto_exposure_bias" in code  # post-process grade present in rig code
        s = _extract_settings(code)
        assert "post" in s and "saturation" in s["post"]

    @pytest.mark.asyncio
    async def test_rejects_unknown_preset(self, server, mock_ue):
        fn = _call(server, "ue_apply_mood_preset")
        result = await fn(name="cyberpunk_rave")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


# --------------------------------------------------------------------------- #
# ue_blend_mood_presets
# --------------------------------------------------------------------------- #


class TestBlendMoodPresets:
    @pytest.mark.asyncio
    async def test_happy_path_midpoint(self, server, mock_ue):
        fn = _call(server, "ue_blend_mood_presets")
        result = await fn(preset_a="golden_hour", preset_b="noir", t=0.5)
        data = json.loads(result)
        assert "error" not in data
        s = _extract_settings(_gen_code(mock_ue))
        lo = min(_MOOD_PRESETS["golden_hour"]["sun_elevation"], _MOOD_PRESETS["noir"]["sun_elevation"])
        hi = max(_MOOD_PRESETS["golden_hour"]["sun_elevation"], _MOOD_PRESETS["noir"]["sun_elevation"])
        assert lo <= s["sun_elevation"] <= hi

    @pytest.mark.asyncio
    async def test_t_is_clamped(self, server, mock_ue):
        fn = _call(server, "ue_blend_mood_presets")
        await fn(preset_a="golden_hour", preset_b="noir", t=5.0)
        s = _extract_settings(_gen_code(mock_ue))
        assert s["sun_elevation"] == _MOOD_PRESETS["noir"]["sun_elevation"]

    @pytest.mark.asyncio
    async def test_rejects_unknown_preset(self, server, mock_ue):
        fn = _call(server, "ue_blend_mood_presets")
        result = await fn(preset_a="golden_hour", preset_b="nope", t=0.5)
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()
