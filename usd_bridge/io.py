"""
io.py

Atomic file I/O, path helpers, and configuration constants for the USD bridge.

Provides:
- _file_lock: Advisory file locking (msvcrt on Windows, fcntl on Unix)
- _atomic_write: Atomic file write via tmp + os.replace
- _safe_read: Retry-enabled file read
- _validate_bridge_path: Path traversal prevention
- get_bridge_file_path: Resolve bridge_state.usda path
- ensure_bridge_directory: Create bridge directory if needed
- get_timestamp: ISO 8601 timestamp
"""

from contextlib import contextmanager
from datetime import datetime
import logging
import os
from pathlib import Path
import tempfile
from typing import Optional

logger = logging.getLogger("ue5-bridge.usd")

# ===============================================================================
# CONFIGURATION
# ===============================================================================

DEFAULT_BRIDGE_PATH = Path.home() / ".translators"
BRIDGE_STATE_FILE = "bridge_state.usda"
BRIDGE_VERSION = "2.0.0"


# ===============================================================================
# ATOMIC FILE I/O
# ===============================================================================

@contextmanager
def _file_lock(file_path: Path, timeout: float = 5.0):
    """Advisory file lock using msvcrt on Windows, fcntl on Unix.

    Acquires an exclusive lock on a .lock file adjacent to the target.
    Falls back to no-op if locking is unavailable.
    """
    lock_path = file_path.with_suffix(file_path.suffix + ".lock")
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w", encoding="utf-8")
        try:
            import msvcrt
            import time
            deadline = time.monotonic() + timeout
            while True:
                try:
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        logger.warning("File lock timeout on %s", file_path.name)
                        break
                    time.sleep(0.05)
        except ImportError:
            try:
                import fcntl
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass  # No locking available -- proceed without
        yield
    finally:
        if lock_fd is not None:
            try:
                try:
                    import msvcrt
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                except (ImportError, OSError):
                    pass
                lock_fd.close()
            except OSError:
                pass


def _atomic_write(file_path: Path, content: str) -> None:
    """Write content to file atomically via tmp + os.replace (NTFS-safe), with file locking."""
    parent = file_path.parent
    with _file_lock(file_path):
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp", prefix=".bridge_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(file_path))
        except BaseException:
            # Clean up temp file on any failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def _safe_read(file_path: Path, retries: int = 3, delay: float = 0.05) -> Optional[str]:
    """Read file with retry on Windows file-lock errors."""
    import time
    for attempt in range(retries):
        try:
            return file_path.read_text(encoding="utf-8")
        except (PermissionError, OSError):
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
    return None


# ===============================================================================
# PATH HELPERS
# ===============================================================================

def _validate_bridge_path(bridge_path: Optional[Path]) -> Path:
    """Validate and resolve a bridge path, preventing path traversal.

    All bridge file operations MUST go through this function to ensure
    files stay within the expected bridge directory.
    """
    base_path = (bridge_path or DEFAULT_BRIDGE_PATH).resolve()
    allowed_root = DEFAULT_BRIDGE_PATH.resolve()
    try:
        base_path.relative_to(allowed_root)
    except ValueError:
        raise ValueError(
            f"Bridge path '{base_path}' is outside the allowed directory '{allowed_root}'. "
            f"Path traversal is not permitted."
        )
    return base_path


def get_bridge_file_path(bridge_path: Optional[Path] = None) -> Path:
    """Get path to bridge_state.usda."""
    base_path = _validate_bridge_path(bridge_path)
    return base_path / BRIDGE_STATE_FILE


def ensure_bridge_directory(bridge_path: Optional[Path] = None) -> Path:
    """Ensure bridge directory exists."""
    base_path = _validate_bridge_path(bridge_path)
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path


def get_timestamp() -> str:
    """Get ISO 8601 timestamp."""
    from datetime import timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
