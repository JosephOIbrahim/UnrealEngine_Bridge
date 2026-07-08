"""UE5 Remote Control bridge -- modular package.

All public names are re-exported for backward compatibility with
code that imports from remote_control_bridge.
"""
from .async_client import AsyncUnrealRemoteControl
from .circuit_breaker import CircuitBreaker
from .codegen import _CodeGen
from .constants import BASE_URL, TIMEOUT
from .preflight import (
    Diagnosis,
    PreflightResult,
    diagnose,
    http_error_detail,
    preflight,
)
from .sync_client import UnrealRemoteControl

__all__ = [
    "BASE_URL", "TIMEOUT",
    "CircuitBreaker", "_CodeGen",
    "UnrealRemoteControl", "AsyncUnrealRemoteControl",
    # capability preflight
    "preflight", "diagnose", "http_error_detail", "PreflightResult", "Diagnosis",
]
