"""
grammar.py

The closed X3D grammar for UE assembly state, and the serialize/deserialize
pair that round-trips a level through it.

The whole point of a fixed vocabulary is that you can hand a model *all of it*
and validate against it. This module owns the node set (`GRAMMAR`), the `Actor`
record, and the two pure functions the golden test pins:

    deserialize(serialize(actors)) == actors        (lossless on thin-slice fields)

UE specifics that X3D has no node for (mesh path, mobility, folder, attach
parent) ride in `MetadataSet` / `MetadataString`, keeping the document valid X3D.
Placement is FLAT (every Transform is a direct child of Scene) and world-space:
nesting would make transforms relative, which fights the lossless invariant.
Attach hierarchy is carried as `ue:parent` metadata and realised as a reparent
op at apply time (see loop.py), not as document nesting.

Provides:
- Actor: the thin-slice actor record (UE-native units)
- GRAMMAR: the closed set of allowed X3D tag names
- X3DGrammarError: raised by deserialize on an out-of-grammar node
- serialize(actors) -> x3d string
- deserialize(x3d string) -> list[Actor]
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import coordinates as coords

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]

# The closed grammar. Anything outside this set is rejected -- on paper by
# validate(), and hard by deserialize().
GRAMMAR = {
    "X3D",
    "Scene",
    "Group",
    "Transform",
    "Shape",
    "Appearance",
    "Material",
    "MetadataSet",
    "MetadataString",
    "MetadataFloat",
}

_X3D_HEADER = '<X3D profile="Interchange" version="4.0">\n <Scene>\n'
_X3D_FOOTER = ' </Scene>\n</X3D>\n'


class X3DGrammarError(ValueError):
    """An X3D document contained a node outside the closed grammar."""


@dataclass
class Actor:
    """
    One placed actor, in UE-native units.

    guid  -> X3D Transform DEF (stable identity the model addresses)
    t     -> UE location, centimetres
    r     -> UE rotation quaternion (x, y, z, w)
    s     -> UE scale multiplier
    mesh / material / mobility / folder / parent -> carried as ue: metadata
    (mesh & material are references to UE assets, never embedded geometry).
    """

    guid: str
    mesh: str = ""
    material: str | None = None
    mobility: str | None = None
    folder: str | None = None
    parent: str | None = None
    t: Vec3 = (0.0, 0.0, 0.0)
    r: Quat = (0.0, 0.0, 0.0, 1.0)
    s: Vec3 = (1.0, 1.0, 1.0)

    def __post_init__(self) -> None:
        # An empty optional string means "unset". Normalize to None so the round
        # trip is symmetric: serialize omits unset metadata, deserialize returns
        # None -- and diff_actors sees no spurious change between "" and None.
        for name in ("material", "mobility", "folder", "parent"):
            if getattr(self, name) == "":
                setattr(self, name, None)


# ===========================================================================
# helpers
# ===========================================================================
def _esc(s: str) -> str:
    """Escape a string for use inside an XML attribute value.

    Tab/newline/CR are emitted as numeric character references: without them,
    XML attribute-value normalization collapses literal control whitespace to a
    single space on parse, breaking the round trip for such fields.
    """
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\t", "&#9;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
    )


def _fmt(x: float) -> str:
    """Shortest round-tripping decimal for a float (Python repr guarantees it)."""
    return repr(float(x))


def _fmt_vec(v: tuple[float, ...]) -> str:
    return " ".join(_fmt(c) for c in v)


def _localname(tag: str) -> str:
    """Strip any XML namespace: '{ns}Transform' -> 'Transform'."""
    return tag.rsplit("}", 1)[-1]


# ===========================================================================
# serialize:  actors -> X3D
# ===========================================================================
def serialize(actors: list[Actor]) -> str:
    """Serialize actors to an X3D document string (UE -> X3D basis applied)."""
    material_defs: dict = {}  # material path -> DEF name
    parts: list[str] = [_X3D_HEADER]

    for a in actors:
        tx = coords.ue_to_x3d_pos(a.t)
        (ax, ay, az), angle = coords.ue_to_x3d_rot(a.r)
        sc = coords.ue_to_x3d_scale(a.s)

        parts.append(
            f'  <Transform DEF="{_esc(a.guid)}"'
            f' translation="{_fmt_vec(tx)}"'
            f' rotation="{_fmt(ax)} {_fmt(ay)} {_fmt(az)} {_fmt(angle)}"'
            f' scale="{_fmt_vec(sc)}">\n'
        )

        # ue: metadata (only fields that are set)
        meta: list[tuple[str, str]] = []
        if a.mesh:
            meta.append(("mesh", a.mesh))
        if a.mobility:
            meta.append(("mobility", a.mobility))
        if a.folder:
            meta.append(("folder", a.folder))
        if a.parent:
            meta.append(("parent", a.parent))
        if meta:
            parts.append('    <MetadataSet name="ue">\n')
            for name, value in meta:
                parts.append(
                    f'      <MetadataString name="{name}" value="{_esc(value)}"/>\n'
                )
            parts.append("    </MetadataSet>\n")

        # material: DEF on first occurrence, USE on reuse (instancing / dedupe)
        if a.material:
            parts.append("    <Shape>\n      <Appearance>\n")
            if a.material in material_defs:
                parts.append(f'        <Material USE="{material_defs[a.material]}"/>\n')
            else:
                def_name = f"Mat_{len(material_defs)}"
                material_defs[a.material] = def_name
                parts.append(f'        <Material DEF="{def_name}"/>\n')
                parts.append(
                    f'        <MetadataString name="ue:material" value="{_esc(a.material)}"/>\n'
                )
            parts.append("      </Appearance>\n    </Shape>\n")

        parts.append("  </Transform>\n")

    parts.append(_X3D_FOOTER)
    return "".join(parts)


# ===========================================================================
# deserialize:  X3D -> actors
# ===========================================================================
def _floats(text: str | None, n: int, default: tuple[float, ...]) -> tuple[float, ...]:
    if not text:
        return default
    vals = tuple(float(v) for v in text.split())
    if len(vals) != n:
        raise X3DGrammarError(f"expected {n} numbers, got {len(vals)!r}")
    return vals


def deserialize(x3d: str) -> list[Actor]:
    """
    Parse an X3D document back into actors (X3D -> UE basis applied).

    An out-of-grammar node raises X3DGrammarError -- deserialize assumes a
    validated document (validate() is the non-raising boundary). Material USE
    references resolve to the ue:material path recorded at the matching DEF.
    """
    try:
        root = ET.fromstring(x3d)
    except ET.ParseError as exc:
        raise X3DGrammarError(f"malformed XML: {exc}") from exc

    if _localname(root.tag) != "X3D":
        raise X3DGrammarError(f"root is {_localname(root.tag)!r}, expected 'X3D'")

    # Hard grammar gate: every node must be in the closed set.
    for el in root.iter():
        name = _localname(el.tag)
        if name not in GRAMMAR:
            raise X3DGrammarError(f"out-of-grammar node: {name!r}")

    material_paths: dict = {}  # DEF name -> ue:material path
    actors: list[Actor] = []

    for tr in root.iter():
        if _localname(tr.tag) != "Transform":
            continue

        tx = _floats(tr.get("translation"), 3, (0.0, 0.0, 0.0))
        rot = _floats(tr.get("rotation"), 4, (0.0, 0.0, 1.0, 0.0))
        sc = _floats(tr.get("scale"), 3, (1.0, 1.0, 1.0))

        meta = {"mesh": "", "mobility": None, "folder": None, "parent": None}
        material: str | None = None

        for child in tr:
            cname = _localname(child.tag)
            if cname == "MetadataSet":
                for ms in child:
                    if _localname(ms.tag) == "MetadataString":
                        key = ms.get("name", "")
                        if key in meta:
                            meta[key] = ms.get("value", "")
            elif cname == "Shape":
                material = _read_material(child, material_paths)

        actors.append(
            Actor(
                guid=tr.get("DEF", ""),
                mesh=meta["mesh"] or "",
                material=material,
                mobility=meta["mobility"],
                folder=meta["folder"],
                parent=meta["parent"],
                t=coords.x3d_to_ue_pos(tx),  # type: ignore[arg-type]
                r=coords.x3d_to_ue_rot((rot[0], rot[1], rot[2]), rot[3]),
                s=coords.x3d_to_ue_scale(sc),  # type: ignore[arg-type]
            )
        )

    return actors


def _read_material(shape: ET.Element, material_paths: dict) -> str | None:
    """Resolve a Shape's material path, honouring DEF/USE references."""
    for appearance in shape:
        if _localname(appearance.tag) != "Appearance":
            continue
        def_path: str | None = None
        material_el: ET.Element | None = None
        for el in appearance:
            name = _localname(el.tag)
            if name == "Material":
                material_el = el
            elif name == "MetadataString" and el.get("name") == "ue:material":
                def_path = el.get("value")
        if material_el is None:
            return None
        use = material_el.get("USE")
        if use is not None:
            return material_paths.get(use)
        deff = material_el.get("DEF")
        if deff is not None and def_path is not None:
            material_paths[deff] = def_path
        return def_path
    return None
