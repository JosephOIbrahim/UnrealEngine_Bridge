"""
x3d_bridge

A UE <-> X3D thin-slice harness. Serializes Unreal Engine assembly state (actor
placement, identity, asset references) to a closed X3D grammar and back, with a
lossless round-trip as the single defended invariant:

    deserialize(serialize(level)) == level

and a validation boundary where malformed edits are rejected on paper, before
the live editor is touched. The coordinate crux (UE Z-up LH cm <-> X3D Y-up RH m)
is an orthonormal change of basis, so the round trip is exact by construction;
matching UE's exact external convention is a separate calibration step.

Direct UE <-> X3D -- independent of the USD messaging channel.

Public API is re-exported flat below (house style).
"""

# ruff: noqa: I001  -- the grouped facade (banner-per-module) is intentional.

# --- coordinates: the crux (basis change, quat/axis-angle, calibration) ---
from .coordinates import (
    B_UE_TO_X3D,
    CM_TO_M,
    ue_to_x3d_pos,
    x3d_to_ue_pos,
    ue_to_x3d_scale,
    x3d_to_ue_scale,
    ue_to_x3d_rot,
    x3d_to_ue_rot,
    quat_to_matrix,
    matrix_to_quat,
    axis_angle_to_matrix,
    matrix_to_axis_angle,
    is_orthonormal,
    determinant,
    quat_close,
    basis_from_axis_images,
    axis_images_of,
)

# --- grammar: the closed vocabulary + serialize/deserialize ---
from .grammar import (
    Actor,
    GRAMMAR,
    X3DGrammarError,
    serialize,
    deserialize,
)

# --- validate: the paper boundary ---
from .validate import validate

# --- loop: the five-stage headless loop + apply seam ---
from .loop import (
    ApplyOp,
    SpawnActor,
    DeleteActor,
    SetTransform,
    AssignMaterial,
    Reparent,
    diff_actors,
    emit_python,
    Bridge,
    MockBridge,
    LoopResult,
    run_loop,
)

# --- preview: the free X_ITE browser view (Mile 6) ---
from .preview import to_preview_html, write_preview

__all__ = [
    # coordinates
    "B_UE_TO_X3D",
    "CM_TO_M",
    "ue_to_x3d_pos",
    "x3d_to_ue_pos",
    "ue_to_x3d_scale",
    "x3d_to_ue_scale",
    "ue_to_x3d_rot",
    "x3d_to_ue_rot",
    "quat_to_matrix",
    "matrix_to_quat",
    "axis_angle_to_matrix",
    "matrix_to_axis_angle",
    "is_orthonormal",
    "determinant",
    "quat_close",
    "basis_from_axis_images",
    "axis_images_of",
    # grammar
    "Actor",
    "GRAMMAR",
    "X3DGrammarError",
    "serialize",
    "deserialize",
    # validate
    "validate",
    # loop
    "ApplyOp",
    "SpawnActor",
    "DeleteActor",
    "SetTransform",
    "AssignMaterial",
    "Reparent",
    "diff_actors",
    "emit_python",
    "Bridge",
    "MockBridge",
    "LoopResult",
    "run_loop",
    # preview
    "to_preview_html",
    "write_preview",
]
