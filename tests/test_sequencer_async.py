"""Async integration tests for ue_mcp/tools/sequencer.py.

Exercises the full tool registration -> call -> mock response path
using FastMCP server instances and the mock_ue fixture.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from ue_mcp.tools.sequencer import register


@pytest.fixture
def server(mock_ue):
    s = FastMCP("test")
    register(s, mock_ue)
    return s


def _call(server, name):
    return server._tool_manager._tools[name].fn


class TestCreateLevelSequence:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_create_level_sequence")
        result = await fn(name="MySequence")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_name(self, server, mock_ue):
        fn = _call(server, "ue_create_level_sequence")
        await fn(name="TestSeq", folder="/Game/Cinematics")
        code = mock_ue.execute_python.call_args[0][0]
        assert "TestSeq" in code
        assert "LevelSequenceFactoryNew" in code
        assert "/Game/Cinematics" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_name(self, server, mock_ue):
        fn = _call(server, "ue_create_level_sequence")
        result = await fn(name='bad"; import os')
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_empty_name(self, server, mock_ue):
        fn = _call(server, "ue_create_level_sequence")
        result = await fn(name="")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_folder(self, server, mock_ue):
        fn = _call(server, "ue_create_level_sequence")
        result = await fn(name="GoodName", folder="../etc/passwd")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestPlaySequence:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_play_sequence")
        result = await fn(sequence_path="/Game/Sequences/MySeq")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_path_and_rate(self, server, mock_ue):
        fn = _call(server, "ue_play_sequence")
        await fn(sequence_path="/Game/Sequences/TestSeq", start_time=2.5, playback_rate=0.5)
        code = mock_ue.execute_python.call_args[0][0]
        assert "/Game/Sequences/TestSeq" in code
        assert "2.5" in code
        assert "0.5" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_play_sequence")
        result = await fn(sequence_path="not a valid path!!!")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestAddActorToSequence:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_add_actor_to_sequence")
        result = await fn(sequence_path="/Game/Sequences/MySeq", actor_label="MyCube")
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_actor_and_path(self, server, mock_ue):
        fn = _call(server, "ue_add_actor_to_sequence")
        await fn(sequence_path="/Game/Sequences/TestSeq", actor_label="TestActor")
        code = mock_ue.execute_python.call_args[0][0]
        assert "TestActor" in code
        assert "/Game/Sequences/TestSeq" in code
        assert "add_possessable" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_path(self, server, mock_ue):
        fn = _call(server, "ue_add_actor_to_sequence")
        result = await fn(sequence_path="bad path!!!", actor_label="MyCube")
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_label(self, server, mock_ue):
        fn = _call(server, "ue_add_actor_to_sequence")
        result = await fn(sequence_path="/Game/Sequences/MySeq", actor_label='bad"; drop')
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()


class TestAddKeyframe:
    @pytest.mark.asyncio
    async def test_happy_path(self, server, mock_ue):
        fn = _call(server, "ue_add_keyframe")
        result = await fn(
            sequence_path="/Game/Sequences/MySeq",
            actor_label="MyCube",
            property_name="RelativeLocation",
            time_seconds=1.0,
            value='{"X": 100, "Y": 0, "Z": 0}',
        )
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_code_contains_all_params(self, server, mock_ue):
        fn = _call(server, "ue_add_keyframe")
        await fn(
            sequence_path="/Game/Sequences/TestSeq",
            actor_label="TestActor",
            property_name="Intensity",
            time_seconds=2.5,
            value="100.0",
        )
        code = mock_ue.execute_python.call_args[0][0]
        assert "/Game/Sequences/TestSeq" in code
        assert "TestActor" in code
        assert "Intensity" in code
        assert "2.5" in code

    @pytest.mark.asyncio
    async def test_rejects_invalid_sequence_path(self, server, mock_ue):
        fn = _call(server, "ue_add_keyframe")
        result = await fn(
            sequence_path="bad!!!",
            actor_label="MyCube",
            property_name="Location",
            time_seconds=0.0,
            value="0",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_actor_label(self, server, mock_ue):
        fn = _call(server, "ue_add_keyframe")
        result = await fn(
            sequence_path="/Game/Sequences/MySeq",
            actor_label='bad"; import os',
            property_name="Location",
            time_seconds=0.0,
            value="0",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_property_name(self, server, mock_ue):
        fn = _call(server, "ue_add_keyframe")
        result = await fn(
            sequence_path="/Game/Sequences/MySeq",
            actor_label="MyCube",
            property_name="bad property!!!",
            time_seconds=0.0,
            value="0",
        )
        data = json.loads(result)
        assert "error" in data
        mock_ue.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_plain_string_value(self, server, mock_ue):
        """Non-JSON value strings should be handled gracefully."""
        fn = _call(server, "ue_add_keyframe")
        result = await fn(
            sequence_path="/Game/Sequences/MySeq",
            actor_label="MyCube",
            property_name="Visibility",
            time_seconds=0.0,
            value="hello",
        )
        data = json.loads(result)
        assert "error" not in data
        mock_ue.execute_python.assert_awaited_once()
