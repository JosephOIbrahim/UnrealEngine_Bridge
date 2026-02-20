"""Shared fixtures for ue-bridge tests."""

import sys
from pathlib import Path

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
