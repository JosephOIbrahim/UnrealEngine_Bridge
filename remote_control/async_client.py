"""Async client for the UE5 Remote Control REST API (for MCP server use)."""

import time
from typing import Any

import httpx

from ue_mcp.metrics import metrics

from .circuit_breaker import CircuitBreaker
from .codegen import _CodeGen
from .constants import (
    BASE_URL,
    POOL_MAX_CONNECTIONS,
    POOL_MAX_KEEPALIVE,
    TIMEOUT,
    logger,
)
from .execution import (
    _build_exec_payload,
    _make_temp_dir,
    _poll_result_async,
    _prepare_execution,
)


class AsyncUnrealRemoteControl:
    """Async wrapper for MCP server use (httpx.AsyncClient)."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            limits=httpx.Limits(
                max_connections=POOL_MAX_CONNECTIONS,
                max_keepalive_connections=POOL_MAX_KEEPALIVE,
            ),
        )
        self._temp_dir = _make_temp_dir()
        self._cb = CircuitBreaker()

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def info(self) -> dict:
        r = await self._client.get("/remote/info")
        r.raise_for_status()
        return r.json()

    async def is_connected(self) -> bool:
        try:
            await self.info()
            self._cb.record_success()
            return True
        except (httpx.ConnectError, httpx.TimeoutException):
            self._cb.record_failure()
            return False

    async def get_property(self, object_path: str, property_name: str) -> Any:
        r = await self._client.put(
            "/remote/object/property",
            json={"objectPath": object_path, "propertyName": property_name, "access": "READ_ACCESS"},
        )
        r.raise_for_status()
        return r.json()

    async def set_property(self, object_path: str, property_name: str, value: Any) -> dict:
        r = await self._client.put(
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

    async def call_function(self, object_path: str, function_name: str, params: dict | None = None) -> dict:
        payload: dict[str, Any] = {"objectPath": object_path, "functionName": function_name}
        if params:
            payload["parameters"] = params
        r = await self._client.put("/remote/object/call", json=payload)
        r.raise_for_status()
        return r.json()

    async def execute_python(self, code: str) -> dict:
        metrics.inc("requests.total")
        if not self._cb.allow_request():
            metrics.inc("requests.circuit_breaker_rejected")
            return self._cb.fail_fast_error()
        t0 = time.time()
        try:
            result_file, script_file, _ = _prepare_execution(self._temp_dir, code)
            r = await self._client.put("/remote/object/call", json=_build_exec_payload(script_file))
            r.raise_for_status()
            result = await _poll_result_async(result_file, script_file)
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
        except Exception:
            # Non-connection fault (e.g. local file I/O in _prepare_execution): don't
            # trip the breaker, but release any HALF_OPEN probe slot we acquired so the
            # breaker can still recover, then propagate.
            self._cb.reset_probe()
            raise

    async def spawn_actor(self, class_path: str, location=(0, 0, 0), rotation=(0, 0, 0), label=None) -> dict:
        return await self.execute_python(_CodeGen.spawn_actor_code(class_path, location, rotation, label))

    async def delete_actor(self, actor_path: str) -> dict:
        return await self.execute_python(_CodeGen.delete_actor_code(actor_path))

    async def list_actors(self, class_filter: str | None = None) -> dict:
        return await self.execute_python(_CodeGen.list_actors_code(class_filter))

    async def set_actor_transform(self, actor_path, location=None, rotation=None, scale=None) -> dict:
        return await self.execute_python(_CodeGen.set_actor_transform_code(actor_path, location, rotation, scale))

    async def find_assets(self, search_pattern: str, class_filter: str | None = None) -> dict:
        return await self.execute_python(_CodeGen.find_assets_code(search_pattern, class_filter))

    async def get_level_info(self) -> dict:
        return await self.execute_python(_CodeGen.get_level_info_code())

    async def save_level(self) -> dict:
        return await self.execute_python(_CodeGen.save_level_code())
