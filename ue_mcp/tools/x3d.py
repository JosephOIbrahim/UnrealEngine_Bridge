"""
x3d.py

MCP tools exposing the x3d_bridge UE<->X3D harness inside the editor.

The harness (x3d_bridge/) round-trips a level's assembly state through a closed
X3D grammar with a lossless invariant and a validation boundary. These tools put
it on the wire:

- ue_x3d_export   Read + Serialize : the live level -> X3D text
- ue_x3d_validate Validate         : the paper boundary, as a tool
- ue_x3d_apply    Apply            : X3D transforms -> the editor via execute_python
- ue_x3d_preview  Preview          : X3D -> a standalone X_ITE browser page

Coordinate conversion, the grammar, and op emission all live in x3d_bridge; this
module is a thin, validated adapter between it and the Remote Control bridge.

v0.4.0 scope: apply sets actor transforms (spawn / delete / material / reparent
apply are a documented follow-up). Export captures mesh/material/parent so the
X3D is complete even though apply currently acts on transforms only.
"""

from __future__ import annotations

import json
import logging

from x3d_bridge import (
    Actor,
    SetTransform,
    X3DGrammarError,
    deserialize,
    emit_python,
    serialize,
    to_preview_html,
)
from x3d_bridge import validate as x3d_validate

from ._types import MCPServer, UEBridge
from ._validation import make_error, sanitize_object_path

logger = logging.getLogger("ue5-mcp.tools.x3d")

# Read every level actor's identity + UE-native transform (rotation as a
# QUATERNION, read straight off the actor transform so we never reconstruct UE's
# Euler convention), mesh path, first material, and attach parent. Static: no
# user input is interpolated, so no escaping is required.
_READ_ACTORS_CODE = """
import unreal, json
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
out = []
for a in sub.get_all_level_actors():
    try:
        t = a.get_actor_transform()
        loc = t.translation; rot = t.rotation; scl = t.scale3d
        mesh_path = ""
        mat_path = None
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        if comp:
            try:
                sm = comp.static_mesh
            except Exception:
                sm = None
            if sm:
                mesh_path = sm.get_path_name()
            try:
                if comp.get_num_materials() > 0:
                    m = comp.get_material(0)
                    if m:
                        mat_path = m.get_path_name()
            except Exception:
                pass
        parent = a.get_attach_parent_actor()
        out.append({
            "guid": a.get_path_name(),
            "mesh": mesh_path,
            "material": mat_path,
            "t": [loc.x, loc.y, loc.z],
            "r": [rot.x, rot.y, rot.z, rot.w],
            "s": [scl.x, scl.y, scl.z],
            "parent": parent.get_path_name() if parent else None,
        })
    except Exception:
        pass
print("RESULT:" + json.dumps(out))
"""


def register(server: MCPServer, ue: UEBridge) -> None:
    @server.tool(
        name="ue_x3d_export",
        description=(
            "Serialize the current level to X3D text (the x3d_bridge thin-slice "
            "grammar). Reads each actor's quaternion transform, static mesh, "
            "material, and attach parent; converts UE (Z-up, cm) to X3D "
            "(Y-up, m). mesh_only=True (default) exports only actors with a "
            "static mesh. Returns {actor_count, x3d}."
        ),
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    )
    async def x3d_export(mesh_only: bool = True) -> str:
        result = await ue.execute_python(_READ_ACTORS_CODE)
        rows = result.get("result")
        if not isinstance(rows, list):
            detail = result.get("error") or result.get("output") or "no result"
            return make_error(f"could not read level actors: {detail}")
        actors = []
        for row in rows:
            if mesh_only and not row.get("mesh"):
                continue
            actors.append(
                Actor(
                    guid=row["guid"],
                    mesh=row.get("mesh") or "",
                    material=row.get("material"),
                    parent=row.get("parent"),
                    t=tuple(row["t"]),
                    r=tuple(row["r"]),
                    s=tuple(row["s"]),
                )
            )
        return json.dumps({"actor_count": len(actors), "x3d": serialize(actors)}, indent=2)

    @server.tool(
        name="ue_x3d_validate",
        description=(
            "Validate an X3D document against the closed thin-slice grammar "
            "without touching the editor: rejects out-of-grammar nodes, dangling "
            "USE references, wrong numeric arity, non-X3D roots, and NaN/inf. "
            "Returns {ok, errors}. Run this on model-edited X3D before apply."
        ),
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    )
    async def x3d_validate_doc(x3d: str) -> str:
        ok, errors = x3d_validate(x3d)
        return json.dumps({"ok": ok, "errors": errors}, indent=2)

    @server.tool(
        name="ue_x3d_apply",
        description=(
            "Apply an X3D document's actor transforms back to the live level. "
            "Validates the document, then for each Transform (addressed by its "
            "DEF = the actor's object path) sets location/rotation/scale in the "
            "editor. Actors must already exist. Returns {applied} or an error. "
            "v0.4.0 applies transforms only."
        ),
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    )
    async def x3d_apply(x3d: str) -> str:
        ok, errors = x3d_validate(x3d)
        if not ok:
            return make_error("invalid X3D: " + "; ".join(errors[:5]))
        try:
            actors = deserialize(x3d)
        except X3DGrammarError as exc:
            return make_error(f"X3D parse error: {exc}")

        ops = []
        for a in actors:
            if err := sanitize_object_path(a.guid, "guid (X3D DEF)"):
                return make_error(err)
            ops.append(SetTransform(guid=a.guid, t=a.t, r=a.r, s=a.s))
        if not ops:
            return json.dumps({"applied": 0, "note": "no actors in document"}, indent=2)

        code = (
            "import unreal, json\n"
            + "\n".join(emit_python(op) for op in ops)
            + f'\nprint("RESULT:" + json.dumps({{"applied": {len(ops)}}}))\n'
        )
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_x3d_preview",
        description=(
            "Render an X3D document to a standalone HTML page that views it in a "
            "browser via the X_ITE runtime (no editor needed). Returns "
            "{chars, html}. The page references X_ITE from a CDN, so viewing it "
            "needs network access; the X3D payload is embedded inline."
        ),
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    )
    async def x3d_preview(x3d: str, title: str = "UE x X3D preview") -> str:
        html = to_preview_html(x3d, title=title)
        return json.dumps({"chars": len(html), "html": html}, indent=2)
