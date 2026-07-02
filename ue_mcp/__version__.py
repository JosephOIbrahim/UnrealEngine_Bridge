"""Version metadata for ue-bridge MCP server.

Single source of truth: pyproject reads it via hatchling; git tags must match
(v0.2.0 <-> 0.2.0). The public line continues from v0.1.1 — the internal 2.x
numbering was never released and was retired at the Epic-MCP-era reset.
"""

__version__ = "0.2.0"
__version_info__ = (0, 2, 0)
