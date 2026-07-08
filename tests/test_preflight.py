"""
Tests for the Capability Ladder preflight (remote_control/preflight.py).

The centerpiece is the golden FAILURE test: the probe must turn UE 5.8's silent
400 into a NAMED cause + the exact fix. That is the regression that would have
caught the whole "connected but dead" detour in five seconds.

All fakes -- no live editor. The mock suite proves the ladder's LOGIC; the
opt-in live tier (smoke_live.py) proves CAPABILITY. They are never conflated.
"""

import pytest

from remote_control.preflight import diagnose, http_error_detail, preflight

_NOT_ALLOWED = (
    '{ "errorMessage": "Executing function \'KismetSystemLibrary GetEngineVersion\' '
    "is not allowed by remote control settings. (see 'Custom Allowed Remote "
    "Function Calls' or 'Allow Any Remote Function Call')\" }"
)


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class FakeHTTPStatusError(Exception):
    def __init__(self, response):
        super().__init__("Client error '400 ' for url ...")
        self.response = response


class FakeConnectError(Exception):
    pass


class FakeRC:
    """Minimal stand-in exposing exactly the two methods preflight needs."""

    def __init__(
        self,
        info=(200, "{}"),
        call=(200, '{"ReturnValue": "5.8.0-x"}'),
        py_result="PREFLIGHT_OK",
        info_exc=None,
        call_exc=None,
    ):
        self._info = (info[0], info[1], info_exc)
        self._call = (call[0], call[1], call_exc)
        self._py_result = py_result

    async def _probe_call(self, path, method="GET", payload=None):
        return self._info if path == "/remote/info" else self._call

    async def execute_python(self, code):
        return {"result": self._py_result, "output": "", "error": None}


# ===========================================================================
# The golden failure test -- the 5.8 block becomes a named fix
# ===========================================================================
@pytest.mark.asyncio
async def test_preflight_names_the_58_function_block():
    r = await preflight(FakeRC(call=(400, _NOT_ALLOWED)))
    assert not r.ok
    assert r.rung == "Permitted"
    assert "bAllowAnyRemoteFunctionCall" in r.fix
    assert "not allowed" in r.evidence.lower()  # the raw body is preserved


# ===========================================================================
# The ladder rungs
# ===========================================================================
@pytest.mark.asyncio
async def test_preflight_all_green():
    r = await preflight(FakeRC())
    assert r.ok
    assert r.rung == "OK"
    assert r.engine_version == "5.8.0-x"


@pytest.mark.asyncio
async def test_preflight_unreachable():
    r = await preflight(FakeRC(info=(None, ""), info_exc=FakeConnectError("refused")))
    assert not r.ok
    assert r.rung == "Reachable"
    assert "unreachable" in r.cause.lower()


@pytest.mark.asyncio
async def test_preflight_permitted_but_no_value_is_capable_rung():
    r = await preflight(FakeRC(call=(200, "{}")))
    assert not r.ok
    assert r.rung == "Capable"


@pytest.mark.asyncio
async def test_preflight_roundtrip_failure_keeps_version():
    r = await preflight(FakeRC(py_result="WRONG"))
    assert not r.ok
    assert r.rung == "RoundTrip"
    assert r.engine_version == "5.8.0-x"  # captured before the round-trip rung


# ===========================================================================
# The diagnosis map
# ===========================================================================
def test_diagnose_passphrase():
    d = diagnose(403, '{"errorMessage": "passphrase required"}', None)
    assert "passphrase" in d.cause.lower()
    assert d.fix


def test_diagnose_python_execution_disabled():
    d = diagnose(400, "python execution is not allowed by remote control settings", None)
    assert "bEnableRemotePythonExecution" in d.fix


def test_diagnose_unreachable_from_exc():
    d = diagnose(None, "", FakeConnectError("refused"))
    assert "unreachable" in d.cause.lower()


def test_diagnose_unknown_is_still_actionable():
    d = diagnose(418, "i am a teapot", None)
    assert d.cause and d.fix  # never a dead end


# ===========================================================================
# http_error_detail -- the P0 body-preservation fix
# ===========================================================================
def test_http_error_detail_preserves_body():
    err = FakeHTTPStatusError(FakeResponse(400, '{"errorMessage": "not allowed by remote control settings"}'))
    detail = http_error_detail(err)
    assert "400" in detail
    assert "not allowed by remote control settings" in detail  # NOT swallowed


def test_http_error_detail_connection_error():
    detail = http_error_detail(FakeConnectError("connection refused"))
    assert "FakeConnectError" in detail
    assert "refused" in detail
