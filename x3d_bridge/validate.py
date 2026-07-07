"""
validate.py

The validation boundary -- where bad edits die on paper, before the live editor
is ever touched.

Two checks, both structural and cheap:
  1. Schema  -- every node is in the closed grammar (grammar.GRAMMAR).
  2. Semantic -- DEF/USE references resolve, and every numeric field is finite.

`validate` never raises and never mutates: it returns (ok, errors). That makes
it safe to run on untrusted model output as the gate between Edit and Apply in
the loop. The harness proves the boundary by asserting a battery of known-bad
documents all fail here.

Provides:
- validate(x3d) -> (ok: bool, errors: list[str])
"""

import math
import xml.etree.ElementTree as ET

from .grammar import GRAMMAR, _localname

# Numeric attributes and their required component count. Arity is enforced
# here so deserialize() -- which requires exactly these counts -- can never be
# reached from a document that passed validate() (the boundary is a superset).
_NUMERIC_ARITY = {"translation": 3, "rotation": 4, "scale": 3}


def validate(x3d: str) -> tuple[bool, list[str]]:
    """Validate an X3D document against the closed thin-slice grammar."""
    errors: list[str] = []

    try:
        root = ET.fromstring(x3d)
    except ET.ParseError as exc:
        return (False, [f"malformed XML: {exc}"])

    # The root must be X3D: deserialize() rejects any other root, so a document
    # rooted at an in-grammar-but-non-X3D tag (e.g. bare Scene) must die here.
    if _localname(root.tag) != "X3D":
        errors.append(f"root is {_localname(root.tag)!r}, expected 'X3D'")

    # Collect DEF names first so a USE may legally reference a later DEF.
    defs = {el.get("DEF") for el in root.iter() if el.get("DEF")}

    for el in root.iter():
        name = _localname(el.tag)

        if name not in GRAMMAR:
            errors.append(f"out-of-grammar: {name}")

        use = el.get("USE")
        if use and use not in defs:
            errors.append(f"dangling USE: {use}")

        for attr, arity in _NUMERIC_ARITY.items():
            raw = el.get(attr)
            if raw is None:
                continue
            tokens = raw.split()
            if len(tokens) != arity:
                errors.append(
                    f"{attr} on {el.get('DEF') or name} needs {arity} numbers, got {len(tokens)}"
                )
            for token in tokens:
                try:
                    value = float(token)
                except ValueError:
                    errors.append(
                        f"non-numeric {attr} on {el.get('DEF') or name}: {token!r}"
                    )
                    continue
                if not math.isfinite(value):
                    errors.append(
                        f"non-finite {attr} on {el.get('DEF') or name}: {token}"
                    )

    return (not errors, errors)
