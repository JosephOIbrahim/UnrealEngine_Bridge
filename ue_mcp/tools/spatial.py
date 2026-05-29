"""Spatial reasoning tools for UE5 world-building.

Gives Claude a ruler and a floor: query where the ground is, snap actors to
grade, and reason about volumes/relationships between actors — the prerequisite
for reliable set dressing, scatter, and terrain placement. All read-side except
ue_snap_to_ground (one fast transaction). Everything routes through
ue_execute_python and returns a single "RESULT:" JSON line.

Tools:
- ue_ground_trace      : downward line trace to find the ground at (x, y)
- ue_snap_to_ground    : drop an actor onto the surface beneath it (optionally tilt to slope)
- ue_spatial_query     : nearest-N / AABB overlap / combined-bounds / box-contents
- ue_measure           : distance between actors / actor extent + footprint area
"""

from __future__ import annotations

import json
import logging

from ._types import MCPServer, UEBridge
from ._validation import (
    escape_for_fstring,
    make_error,
    sanitize_class_name,
    sanitize_label,
)

logger = logging.getLogger("ue5-mcp.tools.spatial")

# Shared editor-Python helpers, embedded verbatim into generated scripts.
# NOTE: contains no "{" / "}" so it is safe to interpolate into an f-string.
_HELPERS = """
def _world():
    try:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    except Exception:
        return unreal.EditorLevelLibrary.get_editor_world()

def _ground_hit(world, gx, gy, top, ignore_list, complex_trace=False):
    start = unreal.Vector(gx, gy, top)
    end = unreal.Vector(gx, gy, top - 100000000.0)
    res = unreal.SystemLibrary.line_trace_single(
        world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
        complex_trace, ignore_list, unreal.DrawDebugTrace.NONE, True
    )
    # The Python binding may return a HitResult, None, or a (bool, HitResult)
    # tuple depending on engine version — normalize all three.
    if isinstance(res, tuple):
        blocking = bool(res[0])
        hit = res[1] if len(res) > 1 else None
    else:
        hit = res
        blocking = res is not None
    if hit is not None and hasattr(hit, "blocking_hit"):
        try:
            blocking = bool(hit.blocking_hit)
        except Exception:
            pass
    return hit if (blocking and hit is not None) else None
"""


def register(server: MCPServer, ue: UEBridge) -> None:
    @server.tool(
        name="ue_ground_trace",
        description=(
            "Line-trace straight down at world (x, y) to find the ground/surface. "
            "Returns the hit point, surface normal, distance, and which actor was hit. "
            "Use before placing props so you know where the floor is."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def ground_trace(x: float, y: float, start_z: float = 100000.0) -> str:
        """Trace down from (x, y, start_z) to the first surface below."""
        code = f"""
import unreal, json
{_HELPERS}
world = _world()
hit = _ground_hit(world, {x}, {y}, {start_z}, [])
if hit is None:
    print("RESULT:" + json.dumps({{"hit": False, "x": {x}, "y": {y}}}))
else:
    ip = hit.impact_point
    n = hit.impact_normal
    ha = hit.hit_actor
    print("RESULT:" + json.dumps({{
        "hit": True,
        "location": {{"x": ip.x, "y": ip.y, "z": ip.z}},
        "normal": {{"x": n.x, "y": n.y, "z": n.z}},
        "distance": hit.distance,
        "actor": ha.get_actor_label() if ha else None,
    }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_snap_to_ground",
        description=(
            "Drop an actor (by label) onto the surface directly beneath it so its "
            "bounding-box bottom rests on the ground. Optionally tilt it to match the "
            "surface slope, and apply a vertical offset. One fast transaction."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def snap_to_ground(
        actor_label: str,
        align_to_normal: bool = False,
        z_offset: float = 0.0,
    ) -> str:
        """Snap an actor to grade. Traces from above the actor, ignoring itself."""
        if err := sanitize_label(actor_label, "actor_label"):
            return make_error(err)

        safe_label = escape_for_fstring(actor_label)
        align_py = "True" if align_to_normal else "False"
        code = f"""
import unreal, json
{_HELPERS}
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{safe_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "Actor not found: {safe_label}"}}))
else:
    world = _world()
    loc = actor.get_actor_location()
    origin, extent = actor.get_actor_bounds(False)
    top = origin.z + extent.z + 1000.0
    # Ignore the actor itself so the trace finds the ground, not its own collision.
    hit = _ground_hit(world, loc.x, loc.y, top, [actor])
    if hit is None:
        print("RESULT:" + json.dumps({{"error": "No ground found beneath actor", "actor": "{safe_label}"}}))
    else:
        ip = hit.impact_point
        # Offset from the actor's pivot to the bottom of its bounding box, so the
        # box bottom (not the pivot) lands on the surface.
        bottom_offset = loc.z - (origin.z - extent.z)
        new_z = ip.z + bottom_offset + {z_offset}
        actor.set_actor_location(unreal.Vector(loc.x, loc.y, new_z), False, True)
        aligned = {align_py}
        if aligned:
            actor.set_actor_rotation(unreal.MathLibrary.make_rot_from_z(hit.impact_normal), False)
        nl = actor.get_actor_location()
        print("RESULT:" + json.dumps({{
            "snapped": True,
            "actor": "{safe_label}",
            "ground_z": ip.z,
            "new_location": {{"x": nl.x, "y": nl.y, "z": nl.z}},
            "aligned_to_normal": aligned,
        }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_spatial_query",
        description=(
            "Reason about actor positions and volumes. Modes: "
            "'nearest' (N closest actors to a point), "
            "'overlap' (do two actors' bounding boxes intersect, + penetration depth), "
            "'combined_bounds' (union AABB of a filtered set — its footprint), "
            "'box_contents' (which actors sit inside an axis-aligned box). "
            "Filter the candidate set with class_filter / tag_filter."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def spatial_query(
        mode: str,
        actor_a: str | None = None,
        actor_b: str | None = None,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        extent_x: float = 100.0,
        extent_y: float = 100.0,
        extent_z: float = 100.0,
        class_filter: str | None = None,
        tag_filter: str | None = None,
        count: int = 5,
    ) -> str:
        """Spatial relationship query. See description for modes."""
        valid_modes = {"nearest", "overlap", "combined_bounds", "box_contents"}
        if mode not in valid_modes:
            return make_error(f"mode must be one of: {', '.join(sorted(valid_modes))}")
        if mode == "overlap" and (not actor_a or not actor_b):
            return make_error("overlap mode requires both actor_a and actor_b")
        for lbl, nm in ((actor_a, "actor_a"), (actor_b, "actor_b")):
            if lbl is not None:
                if err := sanitize_label(lbl, nm):
                    return make_error(err)
        if class_filter is not None:
            if err := sanitize_class_name(class_filter, "class_filter"):
                return make_error(err)
        if tag_filter is not None:
            if err := sanitize_label(tag_filter, "tag_filter"):
                return make_error(err)
        count = max(1, min(count, 100))

        safe_a = escape_for_fstring(actor_a) if actor_a else ""
        safe_b = escape_for_fstring(actor_b) if actor_b else ""
        safe_class = escape_for_fstring(class_filter) if class_filter else ""
        safe_tag = escape_for_fstring(tag_filter) if tag_filter else ""

        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
mode = "{mode}"
class_filter = "{safe_class}" or None
tag_filter = "{safe_tag}" or None

def _match(a):
    if class_filter and a.get_class().get_name() != class_filter:
        return False
    if tag_filter:
        tags = [str(t) for t in a.tags] if hasattr(a, "tags") else []
        if tag_filter not in tags:
            return False
    return True

def _aabb(a):
    o, e = a.get_actor_bounds(False)
    return (o.x - e.x, o.y - e.y, o.z - e.z, o.x + e.x, o.y + e.y, o.z + e.z)

def _find(label):
    for a in actors:
        if a.get_actor_label() == label:
            return a
    return None

cand = [a for a in actors if _match(a)]
out = {{}}

if mode == "nearest":
    ref = unreal.Vector({x}, {y}, {z})
    ranked = sorted(cand, key=lambda a: (a.get_actor_location() - ref).length())
    res = []
    for a in ranked[:{count}]:
        loc = a.get_actor_location()
        res.append({{
            "label": a.get_actor_label(),
            "class": a.get_class().get_name(),
            "distance": round((loc - ref).length(), 2),
            "location": {{"x": loc.x, "y": loc.y, "z": loc.z}},
        }})
    out = {{"mode": mode, "reference": {{"x": {x}, "y": {y}, "z": {z}}}, "count": len(res), "results": res}}

elif mode == "overlap":
    a = _find("{safe_a}")
    b = _find("{safe_b}")
    if a is None or b is None:
        out = {{"error": "Actor not found", "actor_a": "{safe_a}", "actor_b": "{safe_b}"}}
    else:
        ax0, ay0, az0, ax1, ay1, az1 = _aabb(a)
        bx0, by0, bz0, bx1, by1, bz1 = _aabb(b)
        ox = min(ax1, bx1) - max(ax0, bx0)
        oy = min(ay1, by1) - max(ay0, by0)
        oz = min(az1, bz1) - max(az0, bz0)
        overlapping = ox > 0 and oy > 0 and oz > 0
        out = {{
            "mode": mode,
            "actor_a": "{safe_a}",
            "actor_b": "{safe_b}",
            "overlapping": overlapping,
            "penetration": ({{"x": round(ox, 2), "y": round(oy, 2), "z": round(oz, 2)}} if overlapping else None),
        }}

elif mode == "combined_bounds":
    if not cand:
        out = {{"mode": mode, "count": 0, "bounds": None}}
    else:
        boxes = [_aabb(a) for a in cand]
        mnx = min(b[0] for b in boxes); mny = min(b[1] for b in boxes); mnz = min(b[2] for b in boxes)
        mxx = max(b[3] for b in boxes); mxy = max(b[4] for b in boxes); mxz = max(b[5] for b in boxes)
        out = {{
            "mode": mode,
            "count": len(cand),
            "min": {{"x": mnx, "y": mny, "z": mnz}},
            "max": {{"x": mxx, "y": mxy, "z": mxz}},
            "size": {{"x": round(mxx - mnx, 2), "y": round(mxy - mny, 2), "z": round(mxz - mnz, 2)}},
            "center": {{"x": (mnx + mxx) / 2, "y": (mny + mxy) / 2, "z": (mnz + mxz) / 2}},
        }}

elif mode == "box_contents":
    cx, cy, cz = {x}, {y}, {z}
    ex, ey, ez = {extent_x}, {extent_y}, {extent_z}
    inside = []
    for a in cand:
        loc = a.get_actor_location()
        if abs(loc.x - cx) <= ex and abs(loc.y - cy) <= ey and abs(loc.z - cz) <= ez:
            inside.append({{
                "label": a.get_actor_label(),
                "class": a.get_class().get_name(),
                "location": {{"x": loc.x, "y": loc.y, "z": loc.z}},
            }})
    out = {{"mode": mode, "count": len(inside), "actors": inside}}

print("RESULT:" + json.dumps(out))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_measure",
        description=(
            "Measure scene geometry. Modes: "
            "'distance' (straight-line distance + axis deltas between actor_a and actor_b), "
            "'extent' (world-space size and footprint area of actor_a's bounding box)."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def measure(mode: str, actor_a: str, actor_b: str | None = None) -> str:
        """Measure distance between two actors or the extent of one."""
        valid_modes = {"distance", "extent"}
        if mode not in valid_modes:
            return make_error(f"mode must be one of: {', '.join(sorted(valid_modes))}")
        if err := sanitize_label(actor_a, "actor_a"):
            return make_error(err)
        if mode == "distance":
            if not actor_b:
                return make_error("distance mode requires actor_b")
            if err := sanitize_label(actor_b, "actor_b"):
                return make_error(err)

        safe_a = escape_for_fstring(actor_a)
        safe_b = escape_for_fstring(actor_b) if actor_b else ""
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
mode = "{mode}"

def _find(label):
    for a in actors:
        if a.get_actor_label() == label:
            return a
    return None

out = {{}}
if mode == "distance":
    a = _find("{safe_a}")
    b = _find("{safe_b}")
    if a is None or b is None:
        out = {{"error": "Actor not found", "actor_a": "{safe_a}", "actor_b": "{safe_b}"}}
    else:
        la = a.get_actor_location()
        lb = b.get_actor_location()
        out = {{
            "mode": mode,
            "actor_a": "{safe_a}",
            "actor_b": "{safe_b}",
            "distance": round((la - lb).length(), 2),
            "delta": {{"x": round(lb.x - la.x, 2), "y": round(lb.y - la.y, 2), "z": round(lb.z - la.z, 2)}},
        }}
elif mode == "extent":
    a = _find("{safe_a}")
    if a is None:
        out = {{"error": "Actor not found", "actor": "{safe_a}"}}
    else:
        origin, extent = a.get_actor_bounds(False)
        out = {{
            "mode": mode,
            "actor": "{safe_a}",
            "size": {{"x": round(extent.x * 2, 2), "y": round(extent.y * 2, 2), "z": round(extent.z * 2, 2)}},
            "footprint_area": round(extent.x * 2 * extent.y * 2, 2),
            "origin": {{"x": origin.x, "y": origin.y, "z": origin.z}},
        }}

print("RESULT:" + json.dumps(out))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
