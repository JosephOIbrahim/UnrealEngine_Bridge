# exec_sim — exec-simulating codegen harness

The mock suite asserts on generated code *strings*; this harness **runs** the
generated UE editor Python against a strict fake `unreal` module and asserts on
*behavior*. It exists to catch the bug classes string-assertions are blind to:
syntax errors, NameErrors in success branches, args validated-then-discarded,
phantom (nonexistent) `unreal` APIs, and hard-coded success prints.

## Files

| File | Role |
|------|------|
| `unreal_stub.py` | `make_unreal_stub()` builds a fresh fake `unreal` module (strict: unknown top-level symbols raise `AttributeError`). `exec_generated()` installs it in `sys.modules` and runs a script, capturing stdout. `parse_result()` reuses the product RESULT-line parser. |
| `registry.py` | One `ToolEntry` per registered tool: canonical sentinel kwargs, `mode` (`CODEGEN`/`DIRECT`), `sentinel_checkable` kwargs, `expect_error`, notes. |
| `conftest.py` | Registers all tools once per session against a recording fake server and a `CaptureUE` (real `AsyncUnrealRemoteControl` delegation, `execute_python` captures instead of sending). |
| `test_codegen_exec.py` | The four generic gates (below), parametrized over every CODEGEN tool. |
| `test_honesty.py` | Scripted-failure contracts: force a real-world failure, assert the code does not claim success. |

## The gates and what each catches

1. **Registry completeness** — `REGISTRY` keys must equal the registered tool
   names exactly. A new tool cannot dodge the harness.
2. **Compile** — generated Python must `compile()`. Catches interpolation /
   indentation breakage (e.g. a label kwarg producing an `IndentationError`).
3. **Exec + honest success** — run under the default all-success stub: must
   finish, print a `RESULT:` line, and not report failure. Catches phantom
   APIs (`AttributeError`), bare JSON literals (`true` → `NameError`),
   unserializable results (`unreal.Name` dict keys → `TypeError`), and dead
   tools that can *never* succeed.
4. **Sentinel** — each `sentinel_checkable` kwarg's value must appear literally
   (raw or `escape_for_fstring`-escaped) in the source. Catches
   validated-then-discarded arguments.
5. **Honesty (scripted failure)** — `stub.configure(load_level=False)`-style
   overrides force failure paths; the RESULT must not claim success.

## Adding a new tool

1. Register it as usual in `ue_mcp/tools/`.
2. Add a `ToolEntry` in `registry.py` (gate 1 fails until you do):
   - `mode=CODEGEN` with distinctive sentinel kwargs (dyadic floats like
     `433.25` survive `str()`/`json.dumps` exactly), listing in
     `sentinel_checkable` every kwarg embedded *literally* in the script;
   - or `mode=DIRECT` with a `notes` reason (HTTP-only, pass-through, pure
     server-side...).
3. If the generated code uses a new `unreal` symbol, add it to the stub —
   **only after verifying it exists in the real UE Python API**. Phantom
   symbols staying absent is the whole point (`editor_undo`,
   `transaction_undo`, and actor `is_hidden()` are deliberately missing).
4. If the tool needs a forced-failure contract, add a `stub.configure(...)`
   flag and a test in `test_honesty.py`.

## Notes

- The stub's seeded world (actors `SENTINEL_LBL_9Q`, `SENTINEL_LBL_B2`,
  `Cube_1`) matches the registry sentinels so success branches actually run.
- `ue_viewport_percept` is DIRECT (HTTP primary path), but its Python fallback
  is exec-simmed via `perception._fallback_capture` in `test_honesty`.
- `ue_status` / `ue_health_check` live in `mcp_server.py`, outside
  `register_all_tools`, and are out of scope here.
