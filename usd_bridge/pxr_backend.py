"""
pxr_backend.py

OpenUSD Python bindings import guard and HAS_PXR flag.

All modules that need pxr should import HAS_PXR from here.
"""

import logging

logger = logging.getLogger("ue5-bridge.usd")

# Try to import OpenUSD Python bindings
try:
    from pxr import Usd, Sdf, UsdGeom  # noqa: F401
    HAS_PXR = True
except ImportError:
    HAS_PXR = False
    print("[USD Bridge] Warning: pxr not available, using text-based USDA generation")
