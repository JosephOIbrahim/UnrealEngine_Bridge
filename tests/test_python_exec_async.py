"""Async integration tests for ue_mcp/tools/python_exec.py.

Exercises the full tool registration -> call -> mock response path
using FastMCP server instances and the mock_ue fixture.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.python_exec import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestExecutePythonAsync:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="import unreal\nprint('hello')")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once_with("import unreal\nprint('hello')")

    @pytest.mark.asyncio
    async def test_blocks_subprocess(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="import subprocess\nsubprocess.run(['ls'])")
        data = json.loads(result)
        assert "error" in data
        assert "subprocess" in data["error"]
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocks_os_system(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="import os\nos.system('rm -rf /')")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocks_eval(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="eval('1+1')")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocks_exec(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="exec('print(1)')")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocks_dunder_import(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="__import__('os')")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocks_shutil(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="import shutil")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocks_socket(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="import socket")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_syntax_error(self, server, mock_ue):
        fn = _call(server, "ue_execute_python")
        result = await fn(code="def foo(")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_allows_unreal_and_json(self, server, mock_ue):
        code = "import unreal, json\nprint(json.dumps({'test': True}))"
        fn = _call(server, "ue_execute_python")
        result = await fn(code=code)
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once_with(code)

    @pytest.mark.asyncio
    async def test_error_from_editor_propagated(self, server, mock_ue):
        mock_ue.execute_python.return_value = {"error": "NameError: name 'foo' is not defined"}
        fn = _call(server, "ue_execute_python")
        result = await fn(code="print(foo)")
        data = json.loads(result)
        assert "error" in data
