"""Exec-simulation gates for every CODEGEN tool.

Gate 0 (registry):  REGISTRY keys == registered tool names, exactly.
Gate 1 (compile):   generated Python must compile.
Gate 2 (exec):      generated Python must run to completion against the strict
                    ``unreal`` stub in its default all-success world, print a
                    RESULT: line the product parser understands, and that
                    RESULT must not report failure (unless the registry entry
                    declares an honest error is expected).
Gate 3 (sentinel):  every ``sentinel_checkable`` kwarg value must appear
                    literally (raw or f-string-escaped) in the generated
                    source -- catching args that are validated then discarded.

The 415-test mock suite asserts on code *strings*; these gates assert on code
*behavior*, which is what the historical liar/phantom/discard bugs slip past.
"""

from __future__ import annotations

import pytest

from tests.exec_sim.registry import CODEGEN_TOOLS, DIRECT, REGISTRY
from tests.exec_sim.unreal_stub import (
    exec_generated,
    has_result_line,
    is_failure,
    make_unreal_stub,
    parse_result,
)
from ue_mcp.tools._validation import escape_for_fstring

# --------------------------------------------------------------------------
# Gate 0: completeness -- no tool can dodge the harness
# --------------------------------------------------------------------------


def test_registry_covers_exactly_the_registered_tools(toolbox):
    registered = toolbox.registered_names
    in_registry = set(REGISTRY)
    missing = sorted(registered - in_registry)
    stale = sorted(in_registry - registered)
    assert not missing and not stale, (
        f"registry drift -- unclassified registered tools: {missing}; "
        f"registry entries with no registered tool: {stale}. "
        "Every tool registered by register_all_tools needs a registry.py entry "
        "classified CODEGEN or DIRECT."
    )


def test_direct_tools_carry_a_reason():
    unreasoned = [n for n, e in REGISTRY.items() if e.mode == DIRECT and not e.notes.strip()]
    assert not unreasoned, f"DIRECT entries must explain why they are skipped: {unreasoned}"


def test_codegen_tools_actually_generate_code(toolbox):
    silent = [name for name in CODEGEN_TOOLS if not toolbox.codes_for(name)]
    assert not silent, (
        f"classified CODEGEN but captured no execute_python call: {silent} "
        "(misclassified, or the tool errored before generating code)"
    )


# --------------------------------------------------------------------------
# Gate 1: generated Python must compile
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", CODEGEN_TOOLS)
def test_generated_code_compiles(toolbox, tool_name):
    codes = toolbox.codes_for(tool_name)
    assert codes, f"{tool_name}: no generated code captured"
    for i, code in enumerate(codes):
        try:
            compile(code, f"<{tool_name}#{i}>", "exec")
        except SyntaxError as e:
            pytest.fail(
                f"{tool_name}: generated script #{i} does not compile: {e}\n"
                f"--- generated source ---\n{code}"
            )


# --------------------------------------------------------------------------
# Gate 2: success branch must execute and report honestly
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", CODEGEN_TOOLS)
def test_generated_code_executes_and_reports(toolbox, tool_name):
    entry = REGISTRY[tool_name]
    codes = toolbox.codes_for(tool_name)
    stub = make_unreal_stub()  # default: everything the real API offers succeeds

    for i, code in enumerate(codes):
        try:
            stdout = exec_generated(code, stub, name=f"<{tool_name}#{i}>")
        except SyntaxError as e:
            pytest.fail(f"{tool_name}: script #{i} does not compile (see compile gate): {e}")
        except Exception as e:  # noqa: BLE001 -- any runtime crash is the finding
            pytest.fail(
                f"{tool_name}: script #{i} crashed during exec against the strict "
                f"unreal stub: {type(e).__name__}: {e}\n"
                f"--- generated source ---\n{code}"
            )

        assert has_result_line(stdout), (
            f"{tool_name}: script #{i} printed no RESULT: line. stdout was:\n{stdout!r}"
        )
        parsed = parse_result(stdout)

        if entry.expect_error:
            continue  # an honest error is this tool's documented correct behavior

        assert not is_failure(parsed["result"]), (
            f"{tool_name}: script #{i} reported failure under the all-success stub "
            f"(a tool that can never succeed is dead, or it hit a bug in its own "
            f"success branch): RESULT={parsed['result']!r}"
        )


# --------------------------------------------------------------------------
# Gate 3: sentinel kwargs must survive into the generated source
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", CODEGEN_TOOLS)
def test_sentinel_kwargs_reach_the_generated_source(toolbox, tool_name):
    entry = REGISTRY[tool_name]
    if not entry.sentinel_checkable:
        pytest.skip(f"{tool_name}: no literally-embedded kwargs to check")

    blob = "\n".join(toolbox.codes_for(tool_name))
    missing = []
    for kwarg in entry.sentinel_checkable:
        value = str(entry.kwargs[kwarg])
        if value not in blob and escape_for_fstring(value) not in blob:
            missing.append(f"{kwarg}={value!r}")

    assert not missing, (
        f"{tool_name}: kwargs validated but absent from the generated source "
        f"(validated-then-discarded): {missing}"
    )
