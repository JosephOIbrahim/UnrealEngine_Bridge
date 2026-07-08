"""
preflight.py

The Capability Ladder: a runtime probe that answers "can the bridge actually
EXECUTE against the editor?" -- not merely "is it reachable?" -- and turns any
failure into a named cause plus a one-line fix.

Why this exists: connectivity, permission, and capability are THREE different
properties, and the bridge only ever measured the first. `ue_status` does a GET;
the circuit breaker only sees connection errors; the mock test suite never makes
a real Remote Control call. So the bridge can report "connected" and pass CI
while every codegen tool 400s live -- exactly what UE 5.8 caused by defaulting
`bAllowAnyRemoteFunctionCall` to False. This probe measures the other two
properties, and preserves the RC error body the client otherwise discards, so a
silent "400 " becomes an actionable diagnosis.

Provides:
- preflight(rc) -> PreflightResult : the ladder (Reachable -> Permitted -> Capable -> RoundTrip)
- diagnose(status, body, exc) -> Diagnosis : error signature -> cause + fix
- http_error_detail(exc) -> str : rich error string INCLUDING the RC response body
- PreflightResult, Diagnosis, RUNGS
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# The rungs, cheapest -> deepest. The probe stops at the first red.
RUNGS = ("Reachable", "Permitted", "Capable", "RoundTrip")

# A pure, side-effect-free engine function. It doubles as the Permitted probe
# (does the call get rejected?) and the Capable probe (does a value round-trip?).
_PROBE_OBJECT = "/Script/Engine.Default__KismetSystemLibrary"
_PROBE_FUNCTION = "GetEngineVersion"


@dataclass
class Diagnosis:
    cause: str
    fix: str


@dataclass
class PreflightResult:
    ok: bool
    rung: str  # Reachable | Permitted | Capable | RoundTrip | OK
    cause: str = ""
    fix: str = ""
    evidence: str = ""  # raw status + body, for the operator
    engine_version: str = ""


def http_error_detail(exc: Exception) -> str:
    """Rich detail from an httpx error, INCLUDING the Remote Control response body.

    The bare str() of an httpx.HTTPStatusError is "Client error '400 ' for url ..."
    -- it drops the JSON body that says *why*. This keeps it, so a caller can see
    (and diagnose) the actual reason.
    """
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            body = (resp.text or "").strip()
        except Exception:
            body = ""
        return f"HTTP {resp.status_code}: {body}" if body else f"HTTP {resp.status_code}"
    return f"{type(exc).__name__}: {exc}"


def diagnose(status: int | None, body: str | None, exc: Exception | None) -> Diagnosis:
    """Map a Remote Control failure signature to a named cause + one-line fix.

    Extend by adding a branch: every hard-won live failure should become a rule
    here so the next occurrence self-explains.
    """
    b = (body or "").lower()

    if exc is not None:
        return Diagnosis(
            f"Remote Control is unreachable ({type(exc).__name__}).",
            "Open the UE editor with the Remote Control plugin enabled and its Web "
            "Server started on :30010.",
        )

    if status == 400 and "not allowed by remote control settings" in b:
        if "python" in b:
            return Diagnosis(
                "Remote Python execution is disabled "
                "(RemoteControlSettings.bEnableRemotePythonExecution = False).",
                "Set bEnableRemotePythonExecution=True in the project's "
                "Config/DefaultRemoteControl.ini; restart the editor.",
            )
        return Diagnosis(
            "UE 5.8 blocks remote function calls by default "
            "(RemoteControlSettings.bAllowAnyRemoteFunctionCall = False).",
            "Set bAllowAnyRemoteFunctionCall=True in Config/DefaultRemoteControl.ini "
            "(or Project Settings -> Plugins -> Remote Control -> Security -> "
            "'Allow Any Remote Function Call'); restart the editor.",
        )

    if status in (401, 403) or "passphrase" in b:
        return Diagnosis(
            "Remote Control requires a passphrase (bRestrictServerAccess = True).",
            "Set bRestrictServerAccess=False, or configure the MCP client to send "
            "the passphrase.",
        )

    if status == 404:
        return Diagnosis(
            "The target object or function is not remotely accessible.",
            "Verify the objectPath/functionName; some engine objects (e.g. settings "
            "CDOs) cannot be reached remotely.",
        )

    return Diagnosis(
        f"Unrecognized Remote Control failure (HTTP {status}).",
        "Inspect the evidence body and add a diagnose() rule for this signature.",
    )


def _evidence(status: int | None, body: str | None, exc: Exception | None) -> str:
    if exc is not None:
        return f"{type(exc).__name__}: {exc}"
    return f"HTTP {status}: {(body or '').strip()}"


def _extract_return_value(body: str) -> str:
    """Pull the scalar return value out of an RC /remote/object/call response."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return ""
    if isinstance(data, dict):
        # RC names the return "ReturnValue"; fall back to the first non-empty string.
        if isinstance(data.get("ReturnValue"), str):
            return data["ReturnValue"]
        for value in data.values():
            if isinstance(value, str) and value:
                return value
    return ""


async def preflight(rc) -> PreflightResult:
    """Run the capability ladder against a Remote Control client.

    `rc` must provide:
        async _probe_call(path, method="GET", payload=None) -> (status|None, body, exc|None)
        async execute_python(code) -> {"result", "output", "error"}

    Stops at the first failed rung and returns a named cause + fix.
    """
    # Rung 0 -- Reachable
    status, body, exc = await rc._probe_call("/remote/info", "GET")
    if exc is not None or status != 200:
        d = diagnose(status, body, exc)
        return PreflightResult(False, "Reachable", d.cause, d.fix, _evidence(status, body, exc))

    # Rungs 1+2 -- Permitted (does the call get rejected?) and Capable (does a value return?)
    status, body, exc = await rc._probe_call(
        "/remote/object/call",
        "PUT",
        {"objectPath": _PROBE_OBJECT, "functionName": _PROBE_FUNCTION},
    )
    if exc is not None or status != 200:
        rung = "Reachable" if exc is not None else "Permitted"
        d = diagnose(status, body, exc)
        return PreflightResult(False, rung, d.cause, d.fix, _evidence(status, body, exc))

    version = _extract_return_value(body)
    if not version:
        return PreflightResult(
            False,
            "Capable",
            "A remote function call was permitted but returned no value.",
            "Unexpected Remote Control response shape; check the RC/engine version.",
            _evidence(status, body, None),
        )

    # Rung 3 -- RoundTrip (the full write -> exec -> poll -> result Python path)
    result = await rc.execute_python('print("RESULT: PREFLIGHT_OK")')
    if result.get("result") != "PREFLIGHT_OK":
        return PreflightResult(
            False,
            "RoundTrip",
            "Function calls work, but the Python write->exec->poll result path failed.",
            "Check the Python Editor Script Plugin and the temp-script directory; "
            "see remote_control/execution.py.",
            str(result.get("error") or result),
            engine_version=version,
        )

    return PreflightResult(True, "OK", engine_version=version)
