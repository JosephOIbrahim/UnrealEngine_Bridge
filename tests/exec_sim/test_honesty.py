"""Scripted-failure honesty contracts for the historical liars.

Each test forces a failure the real editor can produce (level fails to load,
focus API absent, no image captured, ...) and asserts the generated code does
not claim success anyway. Complements test_codegen_exec, which only checks the
all-success world.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile

import pytest

from tests.exec_sim.registry import (
    REGISTRY,
    SENTINEL_ACTOR_PATH,
    SENTINEL_LABEL,
    SENTINEL_MAP_PATH,
    SENTINEL_MAT_PATH,
    SENTINEL_PROP,
)
from tests.exec_sim.unreal_stub import exec_generated, make_unreal_stub, parse_result


def _single_code(toolbox, tool_name, **kwargs) -> str:
    codes = toolbox.invoke(tool_name, **kwargs) if kwargs else toolbox.codes_for(tool_name)
    assert codes, f"{tool_name}: no generated code captured"
    return codes[-1]


# --------------------------------------------------------------------------
# level.py -- ue_load_level must not report loaded:true when the load failed
# --------------------------------------------------------------------------


def test_load_level_failure_is_not_reported_as_loaded(toolbox):
    code = _single_code(toolbox, "ue_load_level", level_path=SENTINEL_MAP_PATH)
    stub = make_unreal_stub(load_level=False)  # EditorLevelLibrary.load_level -> False
    result = parse_result(exec_generated(code, stub, name="<ue_load_level:fail>"))["result"]
    assert isinstance(result, dict), f"expected dict RESULT, got {result!r}"
    assert not result.get("loaded"), (
        f"load_level() returned False but the generated code claimed success: {result!r}"
    )


# --------------------------------------------------------------------------
# editor.py -- ue_focus_actor must not claim focused when the focus path is absent
# --------------------------------------------------------------------------


def test_focus_actor_claims_focus_only_with_an_executed_route(toolbox):
    """Without LevelEditorSubsystem (the 5.7 reality), focus must go through the
    CAMERA ALIGN console route and SAY SO — a focus claim must always carry the
    route that actually executed."""
    code = _single_code(toolbox, "ue_focus_actor", actor_label=SENTINEL_LABEL)
    stub = make_unreal_stub(level_editor_subsystem=False)  # no LevelEditorSubsystem at all
    result = parse_result(exec_generated(code, stub, name="<ue_focus_actor:no-subsystem>"))["result"]
    assert isinstance(result, dict), f"expected dict RESULT, got {result!r}"
    if result.get("focused"):
        assert result.get("via") == "camera_align_console", (
            f"focus claimed without naming the executed route: {result!r}"
        )
    else:
        assert result.get("error"), f"neither an honest focus nor an honest error: {result!r}"


# --------------------------------------------------------------------------
# editor.py -- undo/redo are honest not-implemented stubs
# (no editor-transaction route exists in the UE Python API — verified 5.7, and
#  Epic's 5.8 MCP surface ships none either; the tools must say so up front
#  instead of probing phantom APIs or claiming success)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ["ue_undo", "ue_redo"])
def test_undo_redo_report_not_implemented(toolbox, tool_name):
    fn, _annotations = toolbox.server.tools[tool_name]
    toolbox.ue.captured = []
    result = json.loads(asyncio.run(fn()))
    assert not toolbox.ue.captured, (
        f"{tool_name}: sent code to the editor despite having no real API route"
    )
    assert isinstance(result, dict) and "not implemented" in str(result.get("error", "")).lower(), (
        f"{tool_name}: expected an explicit not-implemented error, got {result!r}"
    )


# --------------------------------------------------------------------------
# blueprints.py -- set_component_property's success dict must be valid Python
# --------------------------------------------------------------------------


def test_set_component_property_success_branch_is_valid_python(toolbox):
    code = _single_code(
        toolbox, "ue_set_component_property",
        actor_label=SENTINEL_LABEL, component_class="StaticMeshComponent",
        property_name=SENTINEL_PROP, value="7317.25",
    )
    stub = make_unreal_stub()
    result = parse_result(exec_generated(code, stub, name="<ue_set_component_property>"))["result"]
    assert isinstance(result, dict) and result.get("set") is True, (
        f"the set succeeded but the success dict did not evaluate cleanly "
        f"(bare JSON `true` instead of Python True?): RESULT={result!r}"
    )


# --------------------------------------------------------------------------
# blueprints.py -- spawn_blueprint with a label must still compile
# --------------------------------------------------------------------------


def test_spawn_blueprint_with_label_compiles(toolbox):
    code = _single_code(toolbox, "ue_spawn_blueprint", **REGISTRY["ue_spawn_blueprint"].kwargs)
    try:
        compile(code, "<ue_spawn_blueprint:label>", "exec")
    except SyntaxError as e:
        pytest.fail(
            f"spawn_blueprint with label generates non-compiling Python "
            f"(label_line indentation): {e}\n--- generated source ---\n{code}"
        )


# --------------------------------------------------------------------------
# mograph.py -- cloner arguments must reach the generated code
# --------------------------------------------------------------------------


def test_cloner_arguments_are_not_discarded(toolbox):
    entry = REGISTRY["ue_create_cloner"]
    code = "\n".join(toolbox.codes_for("ue_create_cloner"))
    missing = [
        k for k in ("layout", "mesh_path", "count_x", "count_y", "count_z", "spacing")
        if str(entry.kwargs[k]) not in code
    ]
    assert not missing, (
        f"ue_create_cloner validates these args, then generates code that ignores them: "
        f"{missing} (a cloner with no layout/counts/spacing/mesh is set dressing theater)"
    )


# --------------------------------------------------------------------------
# assets.py -- find_assets must survive quotes and backslashes in the pattern
# --------------------------------------------------------------------------


def test_find_assets_pattern_with_quote_and_backslash_still_compiles(toolbox):
    hostile = 'SENT"INEL\\9Q'
    code = _single_code(toolbox, "ue_find_assets", search_pattern=hostile)
    try:
        compile(code, "<ue_find_assets:hostile-pattern>", "exec")
    except SyntaxError as e:
        pytest.fail(
            f"a search pattern containing a quote/backslash breaks the generated "
            f"script (unescaped f-string interpolation): {e}\n"
            f"--- generated source ---\n{code}"
        )


# --------------------------------------------------------------------------
# remote_control/codegen.py -- level actors are not assets
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tool_name", "kwargs"),
    [
        ("ue_delete_actor", dict(actor_path=SENTINEL_ACTOR_PATH)),
        ("ue_set_transform", dict(actor_path=SENTINEL_ACTOR_PATH, x=1.25, y=2.25, z=3.25)),
    ],
)
def test_level_actor_resolution_does_not_use_the_asset_api(toolbox, tool_name, kwargs):
    code = _single_code(toolbox, tool_name, **kwargs)
    assert "EditorAssetLibrary.load_asset" not in code, (
        f"{tool_name}: resolves a LEVEL actor via unreal.EditorAssetLibrary.load_asset -- "
        "that loads content-browser assets and returns garbage-or-None for actor object "
        "paths, so the tool silently no-ops in the real editor. Resolve through the level "
        "(e.g. EditorActorSubsystem.get_all_level_actors + path match)."
    )
    assert SENTINEL_ACTOR_PATH in code, f"{tool_name}: actor_path vanished from the generated code"


# --------------------------------------------------------------------------
# materials.py -- get_material_parameters must not blow up on json.dumps
# --------------------------------------------------------------------------


def test_get_material_parameters_output_is_json_serializable(toolbox):
    code = _single_code(toolbox, "ue_get_material_parameters", material_path=SENTINEL_MAT_PATH)
    stub = make_unreal_stub()  # parameter names are unreal.Name objects, as in the editor
    try:
        stdout = exec_generated(code, stub, name="<ue_get_material_parameters>")
    except TypeError as e:
        pytest.fail(
            f"generated code crashed serializing its own result "
            f"(unreal.Name dict keys passed straight to json.dumps?): {e}"
        )
    result = parse_result(stdout)["result"]
    assert isinstance(result, dict) and "parameters" in result, f"unexpected RESULT: {result!r}"


# --------------------------------------------------------------------------
# scene.py -- get_actor_details is covered by the generic exec gate
# (phantom actor.is_hidden(); the strict actor stub exposes `hidden` instead),
# but pin the contract here so the fix is visible in the honesty suite too.
# --------------------------------------------------------------------------


def test_get_actor_details_does_not_call_phantom_is_hidden(toolbox):
    code = _single_code(toolbox, "ue_get_actor_details", actor_label=SENTINEL_LABEL)
    stub = make_unreal_stub()
    try:
        stdout = exec_generated(code, stub, name="<ue_get_actor_details>")
    except AttributeError as e:
        pytest.fail(
            f"generated code calls an API that does not exist on actors: {e} "
            "(UE actors expose the `hidden` attribute, not an is_hidden() method)"
        )
    result = parse_result(stdout)["result"]
    assert isinstance(result, dict) and not result.get("error"), f"unexpected RESULT: {result!r}"


# --------------------------------------------------------------------------
# perception.py -- the Python fallback must not report success with no image
# --------------------------------------------------------------------------


def test_viewport_fallback_does_not_claim_success_with_empty_image(monkeypatch):
    """The primary ue_viewport_percept path is HTTP (DIRECT in the registry).
    The Python fallback is trigger -> poll -> read across SEPARATE editor
    executions (take_high_res_screenshot completes on a later frame). Simulate
    an editor where the screenshot never lands by exec-ing every script the
    tool sends, and assert the final payload flags the miss instead of
    claiming a capture."""
    from ue_mcp.tools import perception

    monkeypatch.setattr(perception, "FALLBACK_POLL_ATTEMPTS", 3)
    monkeypatch.setattr(perception, "FALLBACK_POLL_INTERVAL_S", 0.0)

    # Nothing writes a screenshot in this world; clear any stale capture file.
    out_path = os.path.join(tempfile.gettempdir(), "ue_perception_capture.jpeg")
    if os.path.exists(out_path):
        os.remove(out_path)

    stub = make_unreal_stub(screenshot_writes_file=False)

    class EditorSim:
        """Executes every script the tool sends, like the real editor would."""

        def __init__(self):
            self.scripts: list[str] = []

        async def execute_python(self, code: str) -> dict:
            self.scripts.append(code)
            return parse_result(exec_generated(code, stub, name=f"<fallback:{len(self.scripts)}>"))

    ue = EditorSim()
    final = asyncio.run(perception._fallback_capture(ue, 320, 200, "jpeg"))

    assert len(ue.scripts) >= 2, (
        "fallback regressed to a single editor execution — the screenshot file "
        "can never exist in the same exec that triggered it"
    )
    assert result_is_honest_miss(final)


def result_is_honest_miss(final: dict) -> bool:
    result = final.get("result")
    return (
        isinstance(result, dict)
        and result.get("image") == ""
        and result.get("capture_status") in {"timeout", "trigger_failed"}
    )


def test_viewport_fallback_does_not_return_a_stale_frame_as_ok(monkeypatch):
    """A stranded screenshot from a PREVIOUS capture (timeout/read-failure) must
    not be returned as this capture's frame — the trigger pass removes it before
    triggering. (Empirically reproduced regression from the verify wave.)"""
    from ue_mcp.tools import perception

    monkeypatch.setattr(perception, "FALLBACK_POLL_ATTEMPTS", 3)
    monkeypatch.setattr(perception, "FALLBACK_POLL_INTERVAL_S", 0.0)

    out_path = os.path.join(tempfile.gettempdir(), "ue_perception_capture.jpeg")
    with open(out_path, "wb") as f:
        f.write(b"STALE-FRAME-FROM-PREVIOUS-SESSION")
    try:
        stub = make_unreal_stub(screenshot_writes_file=False)  # this capture never lands

        class EditorSim:
            def __init__(self):
                self.scripts: list[str] = []

            async def execute_python(self, code: str) -> dict:
                self.scripts.append(code)
                return parse_result(exec_generated(code, stub, name=f"<stale:{len(self.scripts)}>"))

        final = asyncio.run(perception._fallback_capture(EditorSim(), 320, 200, "jpeg"))
        result = final.get("result")
        assert isinstance(result, dict), f"expected dict result, got {final!r}"
        assert result.get("capture_status") != "ok", (
            f"a stale pre-existing file was returned as this capture's frame: "
            f"{({k: v for k, v in result.items() if k != 'image'})!r}"
        )
        assert "STALE" not in (result.get("image") or ""), "stale bytes leaked into the payload"
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)
