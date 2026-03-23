"""Synchronous client for the UE5 Remote Control REST API."""

import json
import time
from typing import Any, Optional

import httpx

from ue_mcp.metrics import metrics

from .constants import (
    BASE_URL,
    TIMEOUT,
    POOL_MAX_CONNECTIONS,
    POOL_MAX_KEEPALIVE,
    logger,
)
from .circuit_breaker import CircuitBreaker
from .codegen import _CodeGen
from .execution import (
    _make_temp_dir,
    _prepare_execution,
    _build_exec_payload,
    _poll_result_sync,
)


class UnrealRemoteControl:
    """Synchronous wrapper around UE5 Remote Control REST API."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            limits=httpx.Limits(
                max_connections=POOL_MAX_CONNECTIONS,
                max_keepalive_connections=POOL_MAX_KEEPALIVE,
            ),
        )
        self._temp_dir = _make_temp_dir()
        self._cb = CircuitBreaker()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def info(self) -> dict:
        r = self._client.get("/remote/info")
        r.raise_for_status()
        return r.json()

    def is_connected(self) -> bool:
        try:
            self.info()
            self._cb.record_success()
            return True
        except (httpx.ConnectError, httpx.TimeoutException):
            self._cb.record_failure()
            return False

    def get_property(self, object_path: str, property_name: str) -> Any:
        r = self._client.put(
            "/remote/object/property",
            json={"objectPath": object_path, "propertyName": property_name, "access": "READ_ACCESS"},
        )
        r.raise_for_status()
        return r.json()

    def set_property(self, object_path: str, property_name: str, value: Any) -> dict:
        r = self._client.put(
            "/remote/object/property",
            json={
                "objectPath": object_path,
                "propertyName": property_name,
                "propertyValue": {"value": value} if not isinstance(value, dict) else value,
                "access": "WRITE_ACCESS",
            },
        )
        r.raise_for_status()
        return r.json()

    def execute_python(self, code: str) -> dict:
        metrics.inc("requests.total")
        if not self._cb.allow_request():
            metrics.inc("requests.circuit_breaker_rejected")
            return self._cb.fail_fast_error()
        t0 = time.time()
        try:
            result_file, script_file, _ = _prepare_execution(self._temp_dir, code)
            r = self._client.put("/remote/object/call", json=_build_exec_payload(script_file))
            r.raise_for_status()
            result = _poll_result_sync(result_file, script_file)
            self._cb.record_success()
            metrics.inc("requests.success")
            metrics.record_latency("execute_python", time.time() - t0)
            return result
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            self._cb.record_failure()
            metrics.inc("requests.error")
            metrics.record_latency("execute_python", time.time() - t0)
            logger.error("UE5 connection failed: %s", e)
            return {"result": None, "output": "", "error": f"Connection failed: {e}"}

    def spawn_actor(self, class_path: str, location=(0, 0, 0), rotation=(0, 0, 0), label=None) -> dict:
        return self.execute_python(_CodeGen.spawn_actor_code(class_path, location, rotation, label))

    def delete_actor(self, actor_path: str) -> dict:
        return self.execute_python(_CodeGen.delete_actor_code(actor_path))

    def list_actors(self, class_filter: Optional[str] = None) -> dict:
        return self.execute_python(_CodeGen.list_actors_code(class_filter))

    def set_actor_transform(self, actor_path, location=None, rotation=None, scale=None) -> dict:
        return self.execute_python(_CodeGen.set_actor_transform_code(actor_path, location, rotation, scale))

    def find_assets(self, search_pattern: str, class_filter: Optional[str] = None) -> dict:
        return self.execute_python(_CodeGen.find_assets_code(search_pattern, class_filter))

    def get_level_info(self) -> dict:
        return self.execute_python(_CodeGen.get_level_info_code())

    def save_level(self) -> dict:
        return self.execute_python(_CodeGen.save_level_code())
