"""Shared fixtures for ue-bridge tests."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Add project root to path so we can import modules
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_bridge_dir(tmp_path):
    """Create a temporary bridge directory for USD bridge tests."""
    bridge_dir = tmp_path / ".translators"
    bridge_dir.mkdir()
    return bridge_dir


@pytest.fixture
def mock_ue():
    """Mock AsyncUnrealRemoteControl for testing tools without a running editor.

    All methods return empty dicts by default. Override specific methods
    in individual tests as needed.
    """
    ue = AsyncMock()
    ue.execute_python = AsyncMock(return_value={"output": "", "success": True})
    ue.spawn_actor = AsyncMock(return_value={"path": "/Game/Test", "success": True})
    ue.delete_actor = AsyncMock(return_value={"success": True})
    ue.list_actors = AsyncMock(return_value={"actors": []})
    ue.find_assets = AsyncMock(return_value={"assets": []})
    ue.save_level = AsyncMock(return_value={"success": True})
    ue.get_level_info = AsyncMock(return_value={"name": "TestLevel", "actor_count": 0})
    ue.set_actor_transform = AsyncMock(return_value={"success": True})
    return ue
