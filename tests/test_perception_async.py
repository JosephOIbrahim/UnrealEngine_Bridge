"""Async integration tests for ue_mcp/tools/perception.py.

Perception tools use HTTP (httpx) to a C++ plugin, with fallback to
ue.execute_python(). We mock _perception_request to test both paths.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.perception import _compute_scene_diff, register


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


class TestViewportDiffAsync:
    @pytest.mark.asyncio
    async def test_delay_too_small(self, server, mock_ue):
        fn = _call(server, "ue_viewport_diff")
        result = await fn(delay_ms=50)
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_delay_too_large(self, server, mock_ue):
        fn = _call(server, "ue_viewport_diff")
        result = await fn(delay_ms=60000)
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_no_changes(self, server, mock_ue):
        snapshot = {
            "actors": [{"label": "Cube", "class": "StaticMeshActor", "location": [0, 0, 0]}],
            "camera": {"available": False},
            "selected": [],
            "actor_count": 1,
        }
        mock_ue.execute_python = AsyncMock(return_value=snapshot)
        fn = _call(server, "ue_viewport_diff")
        result = await fn(delay_ms=100)
        data = json.loads(result)
        assert data["changed"] is False
        assert data["changes"] == []

    @pytest.mark.asyncio
    async def test_actor_added(self, server, mock_ue):
        snap1 = {
            "actors": [{"label": "Cube", "class": "StaticMeshActor", "location": [0, 0, 0]}],
            "camera": {"available": False},
            "selected": [],
            "actor_count": 1,
        }
        snap2 = {
            "actors": [
                {"label": "Cube", "class": "StaticMeshActor", "location": [0, 0, 0]},
                {"label": "Sphere", "class": "StaticMeshActor", "location": [100, 0, 0]},
            ],
            "camera": {"available": False},
            "selected": [],
            "actor_count": 2,
        }
        mock_ue.execute_python = AsyncMock(side_effect=[snap1, snap2])
        fn = _call(server, "ue_viewport_diff")
        result = await fn(delay_ms=100)
        data = json.loads(result)
        assert data["changed"] is True
        types = [c["type"] for c in data["changes"]]
        assert "actor_added" in types
        assert "actor_count_changed" in types

    @pytest.mark.asyncio
    async def test_actor_moved(self, server, mock_ue):
        snap1 = {
            "actors": [{"label": "Cube", "class": "StaticMeshActor", "location": [0, 0, 0]}],
            "camera": {"available": False},
            "selected": [],
            "actor_count": 1,
        }
        snap2 = {
            "actors": [{"label": "Cube", "class": "StaticMeshActor", "location": [100, 0, 0]}],
            "camera": {"available": False},
            "selected": [],
            "actor_count": 1,
        }
        mock_ue.execute_python = AsyncMock(side_effect=[snap1, snap2])
        fn = _call(server, "ue_viewport_diff")
        result = await fn(delay_ms=100)
        data = json.loads(result)
        assert data["changed"] is True
        moved = [c for c in data["changes"] if c["type"] == "actor_moved"]
        assert len(moved) == 1
        assert moved[0]["distance"] == 100.0


class TestComputeSceneDiff:
    def test_error_in_snapshot(self):
        result = _compute_scene_diff({"error": "fail"}, {"actors": []})
        assert "error" in result

    def test_selection_changed(self):
        snap1 = {"actors": [], "camera": {}, "selected": ["Cube"], "actor_count": 0}
        snap2 = {"actors": [], "camera": {}, "selected": ["Sphere"], "actor_count": 0}
        result = _compute_scene_diff(snap1, snap2)
        assert result["changed"] is True
        sel = [c for c in result["changes"] if c["type"] == "selection_changed"]
        assert len(sel) == 1
        assert sel[0]["now_selected"] == ["Sphere"]

    def test_actor_removed(self):
        snap1 = {
            "actors": [{"label": "Cube", "class": "StaticMeshActor", "location": [0, 0, 0]}],
            "camera": {},
            "selected": [],
            "actor_count": 1,
        }
        snap2 = {"actors": [], "camera": {}, "selected": [], "actor_count": 0}
        result = _compute_scene_diff(snap1, snap2)
        assert result["changed"] is True
        removed = [c for c in result["changes"] if c["type"] == "actor_removed"]
        assert len(removed) == 1
        assert removed[0]["label"] == "Cube"

    def test_camera_moved(self):
        snap1 = {
            "actors": [],
            "camera": {"available": True, "location": [0, 0, 0]},
            "selected": [],
            "actor_count": 0,
        }
        snap2 = {
            "actors": [],
            "camera": {"available": True, "location": [200, 0, 0]},
            "selected": [],
            "actor_count": 0,
        }
        result = _compute_scene_diff(snap1, snap2)
        assert result["changed"] is True
        cam = [c for c in result["changes"] if c["type"] == "camera_moved"]
        assert len(cam) == 1
        assert cam[0]["distance"] == 200.0
