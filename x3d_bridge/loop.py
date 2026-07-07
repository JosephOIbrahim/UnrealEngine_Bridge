"""
loop.py

The five-stage bridge loop, made headless. Each red seam from the spec is a
plain callable you swap for a fixture (in CI) or the live bridge (in prod):

    Read      seam: read_fn() -> list[Actor]         (fixture dump / list_actors)
    Serialize       grammar.serialize                (pure)
    Edit      seam: edit_fn(x3d) -> x3d              (replay / model call)
    Validate        validate.validate                (the boundary -- bad edits die here)
    Apply     seam: bridge.apply(ops)                (mock / execute_python emitter)

Apply is expressed as a diff of UE-frame actors into a typed op list, so tests
assert the op *sequence* without a live editor, and `emit_python` renders each
op into the exact `unreal.` call the real bridge runs via `ue_execute_python`
(the only mutation path mounted in the `core` MCP profile).

Identifier note: UE's tools are inconsistent -- set_transform/delete key on the
object PATH, assign_material/duplicate on the LABEL. The ops below carry `guid`
as the actor identity; wire it to whichever identifier the target tool expects
when Mile 5 goes live. Reparent has no UE primitive; emit_python synthesises it
via attach_to_actor, mirroring mograph.py.

Provides:
- ApplyOp and subclasses: SpawnActor, DeleteActor, SetTransform, AssignMaterial, Reparent
- diff_actors(before, after) -> list[ApplyOp]
- emit_python(op) -> str
- Bridge (protocol), MockBridge
- LoopResult, run_loop(...)
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from . import coordinates as coords
from .grammar import Actor, X3DGrammarError, deserialize, serialize
from .validate import validate

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]

_POS_TOL = 1e-4  # cm  -- below UE's practical placement precision
_SCALE_TOL = 1e-6


# ===========================================================================
# apply ops
# ===========================================================================
@dataclass
class ApplyOp:
    """Base for a single UE mutation. `guid` is the actor identity (DEF)."""

    guid: str


@dataclass
class SpawnActor(ApplyOp):
    # Material and attach-parent are emitted as follow-up AssignMaterial /
    # Reparent ops (see diff_actors), not folded into the spawn.
    mesh: str = ""
    t: Vec3 = (0.0, 0.0, 0.0)
    r: Quat = (0.0, 0.0, 0.0, 1.0)
    s: Vec3 = (1.0, 1.0, 1.0)


@dataclass
class DeleteActor(ApplyOp):
    pass


@dataclass
class SetTransform(ApplyOp):
    t: Vec3 = (0.0, 0.0, 0.0)
    r: Quat = (0.0, 0.0, 0.0, 1.0)
    s: Vec3 = (1.0, 1.0, 1.0)


@dataclass
class AssignMaterial(ApplyOp):
    material: str = ""
    slot_index: int = 0


@dataclass
class Reparent(ApplyOp):
    parent: str | None = None


# ===========================================================================
# diff:  two UE-frame actor lists -> the ops that turn `before` into `after`
# ===========================================================================
def _vec_changed(a: tuple[float, ...], b: tuple[float, ...], tol: float) -> bool:
    return any(abs(x - y) > tol for x, y in zip(a, b, strict=True))


def _transform_changed(a: Actor, b: Actor) -> bool:
    return (
        _vec_changed(a.t, b.t, _POS_TOL)
        or _vec_changed(a.s, b.s, _SCALE_TOL)
        or not coords.quat_close(a.r, b.r)
    )


def diff_actors(before: list[Actor], after: list[Actor]) -> list[ApplyOp]:
    """Compute the ordered op list that mutates `before` into `after`, by guid."""
    before_by_id = {a.guid: a for a in before}
    after_by_id = {a.guid: a for a in after}
    ops: list[ApplyOp] = []

    # spawns + changes, in `after` order (stable, reviewable)
    for a in after:
        prev = before_by_id.get(a.guid)
        if prev is None:
            ops.append(SpawnActor(guid=a.guid, mesh=a.mesh, t=a.t, r=a.r, s=a.s))
            if a.material:
                ops.append(AssignMaterial(guid=a.guid, material=a.material))
            if a.parent:
                ops.append(Reparent(guid=a.guid, parent=a.parent))
            continue
        if _transform_changed(prev, a):
            ops.append(SetTransform(guid=a.guid, t=a.t, r=a.r, s=a.s))
        # NOTE: clearing a material (X -> None) emits no op -- the thin-slice
        # vocabulary has no un-assign primitive. A material *change* to another
        # asset is expressed; a removal is a documented limitation.
        if a.material != prev.material and a.material:
            ops.append(AssignMaterial(guid=a.guid, material=a.material))
        if a.parent != prev.parent:
            ops.append(Reparent(guid=a.guid, parent=a.parent))

    # deletes, in `before` order
    for a in before:
        if a.guid not in after_by_id:
            ops.append(DeleteActor(guid=a.guid))

    return ops


# ===========================================================================
# emit_python:  render one op into the UE-Python the real bridge would run
# ===========================================================================
def _v(v: Vec3) -> str:
    return f"{v[0]}, {v[1]}, {v[2]}"


def emit_python(op: ApplyOp) -> str:
    """Render an op into a `unreal.` snippet for ue_execute_python (Mile 5 seam)."""
    if isinstance(op, SetTransform):
        rx, ry, rz, rw = op.r
        return (
            f'actor = unreal.load_object(None, "{op.guid}")\n'
            f"if actor:\n"
            f"    actor.set_actor_location(unreal.Vector({_v(op.t)}), False, False)\n"
            f"    actor.set_actor_rotation(unreal.Quat({rx}, {ry}, {rz}, {rw}).rotator(), False)\n"
            f"    actor.set_actor_scale3d(unreal.Vector({_v(op.s)}))"
        )
    if isinstance(op, SpawnActor):
        rx, ry, rz, rw = op.r
        return (
            "subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)\n"
            f"actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, "
            f"unreal.Vector({_v(op.t)}), unreal.Quat({rx}, {ry}, {rz}, {rw}).rotator())\n"
            "if actor:\n"
            f'    actor.set_actor_label("{op.guid}")\n'
            f"    actor.set_actor_scale3d(unreal.Vector({_v(op.s)}))\n"
            f'    mesh = unreal.load_asset("{op.mesh}")\n'
            "    if mesh:\n"
            "        actor.static_mesh_component.set_static_mesh(mesh)"
        )
    if isinstance(op, DeleteActor):
        return (
            "subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)\n"
            f'actor = unreal.load_object(None, "{op.guid}")\n'
            "if actor:\n"
            "    subsystem.destroy_actor(actor)"
        )
    if isinstance(op, AssignMaterial):
        return (
            f'actor = unreal.load_object(None, "{op.guid}")\n'
            f'mat = unreal.EditorAssetLibrary.load_asset("{op.material}")\n'
            "if actor and mat:\n"
            "    comp = actor.get_component_by_class(unreal.StaticMeshComponent)\n"
            "    if comp:\n"
            f"        comp.set_material({op.slot_index}, mat)"
        )
    if isinstance(op, Reparent):
        if not op.parent:
            return (
                f'child = unreal.load_object(None, "{op.guid}")\n'
                "if child:\n"
                "    child.detach_from_actor(unreal.DetachmentRule.KEEP_WORLD, "
                "unreal.DetachmentRule.KEEP_WORLD, unreal.DetachmentRule.KEEP_WORLD)"
            )
        return (
            f'child = unreal.load_object(None, "{op.guid}")\n'
            f'parent = unreal.load_object(None, "{op.parent}")\n'
            "if child and parent:\n"
            "    child.attach_to_actor(parent, \"\", unreal.AttachmentRule.KEEP_WORLD, "
            "unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)"
        )
    raise TypeError(f"unknown op: {type(op).__name__}")


# ===========================================================================
# the bridge seam
# ===========================================================================
class Bridge(Protocol):
    """The apply seam. Prod wires this to ue_execute_python; tests use MockBridge."""

    def apply(self, ops: list[ApplyOp]) -> None: ...


@dataclass
class MockBridge:
    """Records the op sequence instead of touching an editor."""

    ops: list[ApplyOp] = field(default_factory=list)

    def apply(self, ops: list[ApplyOp]) -> None:
        self.ops.extend(ops)


# ===========================================================================
# the loop
# ===========================================================================
@dataclass
class LoopResult:
    ok: bool
    errors: list[str]
    x3d_before: str
    x3d_after: str
    ops: list[ApplyOp]


def _identity_edit(x3d: str) -> str:
    return x3d


def run_loop(
    read_fn: Callable[[], list[Actor]],
    edit_fn: Callable[[str], str] = _identity_edit,
    bridge: Bridge | None = None,
) -> LoopResult:
    """
    Run Read -> Serialize -> Edit -> Validate -> Apply headlessly.

    Validation is the gate: if the edited document is invalid the loop returns
    the errors and applies NOTHING. Only a valid edit reaches the bridge.
    """
    before = read_fn()
    x3d_before = serialize(before)

    x3d_after = edit_fn(x3d_before)
    ok, errors = validate(x3d_after)
    if not ok:
        return LoopResult(False, errors, x3d_before, x3d_after, [])

    # Defense in depth: validate() is meant to catch everything deserialize()
    # would reject, but guard anyway so a boundary gap can never crash apply.
    try:
        after = deserialize(x3d_after)
    except X3DGrammarError as exc:
        return LoopResult(False, [str(exc)], x3d_before, x3d_after, [])
    ops = diff_actors(before, after)
    if bridge is not None and ops:
        bridge.apply(ops)

    return LoopResult(True, [], x3d_before, x3d_after, ops)
