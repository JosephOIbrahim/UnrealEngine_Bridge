"""
preview.py

Mile 6 -- the free win. The same X3D that round-trips through the bridge drops
straight into a browser via the X_ITE runtime, so a scene is previewable with no
editor and no cost.

This is a developer convenience, deliberately out of the tested thin slice: the
generated page references the X_ITE runtime from a CDN, so viewing it needs
network access. The X3D payload itself is embedded inline and unchanged.

Provides:
- to_preview_html(x3d, title=...) -> str
- write_preview(x3d, path, title=...) -> Path
"""

import html
from pathlib import Path

_X_ITE_CDN = "https://cdn.jsdelivr.net/npm/x_ite@latest/dist/x_ite.min.js"

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<script src="{cdn}"></script>
<style>html,body{{margin:0;height:100%}}x3d-canvas{{width:100vw;height:100vh}}</style>
</head>
<body>
<x3d-canvas>
{x3d}
</x3d-canvas>
</body>
</html>
"""


def to_preview_html(x3d: str, title: str = "UE x X3D preview") -> str:
    """Wrap an X3D document in a standalone X_ITE viewer page.

    `title` is HTML-escaped (it lands in an HTML text context); `x3d` is left
    raw, as X_ITE requires unescaped XML.
    """
    return _TEMPLATE.format(title=html.escape(title), cdn=_X_ITE_CDN, x3d=x3d)


def write_preview(x3d: str, path: Path, title: str = "UE x X3D preview") -> Path:
    """Write a preview page to disk and return its path."""
    path = Path(path)
    path.write_text(to_preview_html(x3d, title=title), encoding="utf-8")
    return path
