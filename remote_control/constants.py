"""Module-level constants for the UE5 Remote Control bridge."""

import logging
import os

logger = logging.getLogger("ue5-mcp.bridge")

BASE_URL = os.environ.get("UE_REMOTE_URL", "http://localhost:30010")
TIMEOUT = 10.0
RESULT_POLL_INTERVAL = 0.2  # seconds between result file checks
RESULT_POLL_TIMEOUT = 10.0  # max seconds to wait for result
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB cap on JSON responses

# Circuit breaker settings
CB_FAILURE_THRESHOLD = 5    # consecutive failures before opening
CB_RECOVERY_TIMEOUT = 30.0  # seconds before half-open retry
CB_HALF_OPEN_MAX = 1        # max concurrent requests in half-open

# Connection pool settings
POOL_MAX_CONNECTIONS = 10
POOL_MAX_KEEPALIVE = 5
