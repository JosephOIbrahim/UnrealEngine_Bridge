"""Async integration tests for ue_mcp/tools/assets.py.

Exercises the full tool registration -> call -> mock response path
using FastMCP server instances and the mock_ue fixture.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.assets import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestFindAssetsAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_find_assets")
        result = await fn(search_pattern="Chrome")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.find_assets.assert_awaited_once_with("Chrome", class_filter=None)

    @pytest.mark.asyncio
    async def test_with_class_filter(self, server, mock_ue):
        fn = _call(server, "ue_find_assets")
        result = await fn(search_pattern="Chrome", class_filter="Material")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.find_assets.assert_awaited_once_with("Chrome", class_filter="Material")

    @pytest.mark.asyncio
    async def test_rejects_empty_pattern(self, server, mock_ue):
        fn = _call(server, "ue_find_assets")
        result = await fn(search_pattern="")
        data = json.loads(result)
        assert "error" in data
        mock_ue.find_assets.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_class_filter(self, server, mock_ue):
        fn = _call(server, "ue_find_assets")
        result = await fn(search_pattern="Chrome", class_filter="1Bad;Class")
        data = json.loads(result)
        assert "error" in data
        mock_ue.find_assets.assert_not_awaited()


class TestCreateMaterialAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_create_material")
        result = await fn(name="M_Test")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_material_name(self, server, mock_ue):
        fn = _call(server, "ue_create_material")
        await fn(name="M_Chrome", roughness=0.2, metallic=1.0)
        code = mock_ue.execute_python.call_args[0][0]
        assert "M_Chrome" in code
        assert "0.2" in code
        assert "1.0" in code

    @pytest.mark.asyncio
    async def test_rejects_empty_name(self, server, mock_ue):
        fn = _call(server, "ue_create_material")
        result = await fn(name="")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestDeleteAssetAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_delete_asset")
        result = await fn(asset_path="/Game/Materials/M_Old")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_path(self, server, mock_ue):
        fn = _call(server, "ue_delete_asset")
        await fn(asset_path="/Game/Materials/M_Old")
        code = mock_ue.execute_python.call_args[0][0]
        assert "/Game/Materials/M_Old" in code
        assert "delete_asset" in code

    @pytest.mark.asyncio
    async def test_rejects_path_traversal(self, server, mock_ue):
        fn = _call(server, "ue_delete_asset")
        result = await fn(asset_path="../etc/passwd")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()
