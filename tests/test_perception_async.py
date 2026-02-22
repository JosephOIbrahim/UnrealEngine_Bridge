"""Async integration tests for ue_mcp/tools/perception.py.

Perception tools use HTTP (httpx) to a C++ plugin, with fallback to
ue.execute_python(). We mock _perception_request to test both paths.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.perception import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestViewportPerceptAsync:
    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request")
    async def test_happy_path_plugin_available(self, mock_req, server, mock_ue):
        mock_req.return_value = {"image": "base64data", "width": 1280, "height": 720}
        fn = _call(server, "ue_viewport_percept")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        assert data["width"] == 1280
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request", return_value=None)
    async def test_fallback_to_python(self, mock_req, server, mock_ue):
        """When plugin is unreachable, falls back to execute_python."""
        fn = _call(server, "ue_viewport_percept")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request")
    async def test_exclude_image(self, mock_req, server, mock_ue):
        mock_req.return_value = {"image": "base64data", "width": 1280}
        fn = _call(server, "ue_viewport_percept")
        result = await fn(include_image=False)
        data = json.loads(result)
        assert "image" not in data


class TestViewportWatchAsync:
    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request")
    async def test_start_happy_path(self, mock_req, server, mock_ue):
        mock_req.return_value = {"status": "started", "fps": 5.0}
        fn = _call(server, "ue_viewport_watch")
        result = await fn(action="start")
        data = json.loads(result)
        assert "error" not in data
        assert data["status"] == "started"

    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request", return_value=None)
    async def test_start_plugin_unavailable(self, mock_req, server, mock_ue):
        fn = _call(server, "ue_viewport_watch")
        result = await fn(action="start")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request")
    async def test_stop(self, mock_req, server, mock_ue):
        mock_req.return_value = {"status": "stopped"}
        fn = _call(server, "ue_viewport_watch")
        result = await fn(action="stop")
        data = json.loads(result)
        assert "error" not in data

    @pytest.mark.asyncio
    async def test_invalid_action(self, server, mock_ue):
        fn = _call(server, "ue_viewport_watch")
        result = await fn(action="invalid")
        data = json.loads(result)
        assert "error" in data


class TestViewportConfigAsync:
    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request")
    async def test_set_config(self, mock_req, server, mock_ue):
        mock_req.return_value = {"max_fps": 10.0, "width": 1920}
        fn = _call(server, "ue_viewport_config")
        result = await fn(max_fps=10.0, width=1920)
        data = json.loads(result)
        assert "error" not in data

    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request")
    async def test_query_status_no_args(self, mock_req, server, mock_ue):
        mock_req.return_value = {"status": "idle", "fps": 5.0}
        fn = _call(server, "ue_viewport_config")
        result = await fn()
        data = json.loads(result)
        assert "error" not in data
        # Should call GET /perception/status
        mock_req.assert_awaited_once_with("GET", "/perception/status")

    @pytest.mark.asyncio
    @patch("ue_mcp.tools.perception._perception_request", return_value=None)
    async def test_plugin_unavailable(self, mock_req, server, mock_ue):
        fn = _call(server, "ue_viewport_config")
        result = await fn(max_fps=10.0)
        data = json.loads(result)
        assert "error" in data
