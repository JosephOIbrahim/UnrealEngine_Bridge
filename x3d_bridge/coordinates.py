"""
coordinates.py

The coordinate crux for the UE <-> X3D thin slice.

Unreal Engine is Z-up, LEFT-handed, centimetres.
X3D (like glTF / OpenGL) is Y-up, RIGHT-handed, metres.

Every transform crosses that gap twice per round trip. The change of basis is
expressed as a single ORTHONORMAL matrix B (UE -> X3D). Because B is orthonormal,
B^-1 == B^T, so the round trip is EXACT for *any* correct B -- correctness is
structural. Picking the *right* B (so external glTF/X3D tools agree with UE) is a
separate empirical calibration step (see `basis_from_axis_images`).

Provides:
- B_UE_TO_X3D, CM_TO_M: the locked change-of-basis and unit scale
- ue_to_x3d_pos / x3d_to_ue_pos: position conversion (cm <-> m + basis)
- ue_to_x3d_scale / x3d_to_ue_scale: scale conversion (axis permutation)
- ue_to_x3d_rot / x3d_to_ue_rot: rotation, UE quat <-> X3D axis-angle
- quat_to_matrix / matrix_to_quat / axis_angle_to_matrix / matrix_to_axis_angle
- is_orthonormal / determinant / basis_from_axis_images: calibration + guards
- quat_close: rotation-aware equality (handles quaternion double-cover)
"""

import math

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]  # (x, y, z, w), UE convention
Mat3 = tuple[tuple[float, float, float], ...]
AxisAngle = tuple[Vec3, float]  # (axis, angle-in-radians)

# Numerical tolerance for degeneracy branches (identity / 180-degree rotations).
_EPS = 1e-9

# ===========================================================================
# The locked change of basis  (UE Z-up LH cm  ->  X3D Y-up RH m)
# ===========================================================================
# Derived by role preservation:  UE.right(Y)->X3D.right(X), UE.up(Z)->X3D.up(Y),
# UE.forward(X)->X3D.forward(-Z, since +Z is "toward viewer"/back in X3D).
# Columns of B are the images of UE's basis vectors in X3D space, so B maps a
# UE column vector to an X3D column vector:  x3d = B @ ue.
#
#   X3D.x =  UE.y
#   X3D.y =  UE.z
#   X3D.z = -UE.x
#
# det(B) = -1  ->  a reflection, which is exactly what flips LH -> RH.
# (The often-quoted "template" ((1,0,0),(0,0,1),(0,-1,0)) has det +1 -- a pure
#  rotation -- and therefore CANNOT convert handedness. That was the bug.)
CM_TO_M: float = 0.01

B_UE_TO_X3D: Mat3 = (
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (-1.0, 0.0, 0.0),
)


# ===========================================================================
# 3x3 linear algebra (pure Python, no numpy dependency)
# ===========================================================================
def _mat_vec(m: Mat3, v: Vec3) -> Vec3:
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))  # type: ignore[return-value]


def _mat_mul(a: Mat3, b: Mat3) -> Mat3:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )  # type: ignore[return-value]


def _transpose(m: Mat3) -> Mat3:
    return tuple(tuple(m[k][i] for k in range(3)) for i in range(3))  # type: ignore[return-value]


def determinant(m: Mat3) -> float:
    """Determinant of a 3x3 matrix. det == -1 confirms a handedness flip."""
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def is_orthonormal(m: Mat3, tol: float = 1e-9) -> bool:
    """True iff M^T M == I -- the precondition for a lossless round trip."""
    prod = _mat_mul(_transpose(m), m)
    for i in range(3):
        for j in range(3):
            expected = 1.0 if i == j else 0.0
            if abs(prod[i][j] - expected) > tol:
                return False
    return True


# ===========================================================================
# Position  (cm <-> m, plus the basis change)
# ===========================================================================
def ue_to_x3d_pos(t_cm: Vec3) -> Vec3:
    """UE location (cm) -> X3D translation (m)."""
    return tuple(c * CM_TO_M for c in _mat_vec(B_UE_TO_X3D, t_cm))  # type: ignore[return-value]


def x3d_to_ue_pos(p_m: Vec3) -> Vec3:
    """X3D translation (m) -> UE location (cm). Uses B^T (== B^-1)."""
    ue = _mat_vec(_transpose(B_UE_TO_X3D), p_m)
    return tuple(c / CM_TO_M for c in ue)  # type: ignore[return-value]


# ===========================================================================
# Scale  (a signed-permutation basis permutes scale axes; sign is irrelevant to
# a magnitude, so we permute by |B|. Derived from B so it tracks calibration.)
# ===========================================================================
def _abs_mat(m: Mat3) -> Mat3:
    return tuple(tuple(abs(x) for x in row) for row in m)  # type: ignore[return-value]


def ue_to_x3d_scale(s: Vec3) -> Vec3:
    """UE scale multiplier -> X3D scale (axis permutation only)."""
    return _mat_vec(_abs_mat(B_UE_TO_X3D), s)


def x3d_to_ue_scale(s: Vec3) -> Vec3:
    """X3D scale -> UE scale (inverse permutation)."""
    return _mat_vec(_transpose(_abs_mat(B_UE_TO_X3D)), s)


# ===========================================================================
# Rotation quaternion <-> matrix <-> axis-angle
# ===========================================================================
def quat_to_matrix(q: Quat) -> Mat3:
    """Unit quaternion (x, y, z, w) -> 3x3 rotation matrix."""
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n < _EPS:
        return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    x, y, z, w = x / n, y / n, z / n, w / n
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return (
        (1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)),
        (2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)),
        (2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)),
    )


def matrix_to_quat(m: Mat3) -> Quat:
    """3x3 rotation matrix -> unit quaternion (x, y, z, w). Numerically stable."""
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0  # s = 4w
        w = 0.25 * s
        x = (m[2][1] - m[1][2]) / s
        y = (m[0][2] - m[2][0]) / s
        z = (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0  # s = 4x
        w = (m[2][1] - m[1][2]) / s
        x = 0.25 * s
        y = (m[0][1] + m[1][0]) / s
        z = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0  # s = 4y
        w = (m[0][2] - m[2][0]) / s
        x = (m[0][1] + m[1][0]) / s
        y = 0.25 * s
        z = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0  # s = 4z
        w = (m[1][0] - m[0][1]) / s
        x = (m[0][2] + m[2][0]) / s
        y = (m[1][2] + m[2][1]) / s
        z = 0.25 * s
    n = math.sqrt(x * x + y * y + z * z + w * w)
    return (x / n, y / n, z / n, w / n)


def axis_angle_to_matrix(axis: Vec3, angle: float) -> Mat3:
    """X3D axis-angle (radians) -> 3x3 rotation matrix (Rodrigues)."""
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z)
    if n < _EPS:
        return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    x, y, z = x / n, y / n, z / n
    c, s = math.cos(angle), math.sin(angle)
    cc = 1.0 - c
    return (
        (c + x * x * cc, x * y * cc - z * s, x * z * cc + y * s),
        (y * x * cc + z * s, c + y * y * cc, y * z * cc - x * s),
        (z * x * cc - y * s, z * y * cc + x * s, c + z * z * cc),
    )


def matrix_to_axis_angle(m: Mat3) -> AxisAngle:
    """3x3 rotation matrix -> X3D axis-angle (unit axis, radians)."""
    trace = m[0][0] + m[1][1] + m[2][2]
    cos_a = max(-1.0, min(1.0, (trace - 1.0) / 2.0))
    angle = math.acos(cos_a)

    if angle < _EPS:
        # Identity -- X3D's canonical "no rotation" is axis (0,0,1), angle 0.
        return ((0.0, 0.0, 1.0), 0.0)

    if math.pi - angle < _EPS:
        # 180 degrees: (R - I) is singular, recover axis from the diagonal.
        xx = (m[0][0] + 1.0) / 2.0
        yy = (m[1][1] + 1.0) / 2.0
        zz = (m[2][2] + 1.0) / 2.0
        ax = math.sqrt(max(xx, 0.0))
        ay = math.sqrt(max(yy, 0.0))
        az = math.sqrt(max(zz, 0.0))
        xy = (m[0][1] + m[1][0]) / 4.0
        xz = (m[0][2] + m[2][0]) / 4.0
        yz = (m[1][2] + m[2][1]) / 4.0
        if ax >= ay and ax >= az:
            ay = ay if xy >= 0 else -ay
            az = az if xz >= 0 else -az
        elif ay >= az:
            ax = ax if xy >= 0 else -ax
            az = az if yz >= 0 else -az
        else:
            ax = ax if xz >= 0 else -ax
            ay = ay if yz >= 0 else -ay
        n = math.sqrt(ax * ax + ay * ay + az * az)
        return ((ax / n, ay / n, az / n), math.pi)

    rx = m[2][1] - m[1][2]
    ry = m[0][2] - m[2][0]
    rz = m[1][0] - m[0][1]
    s = math.sqrt(rx * rx + ry * ry + rz * rz)
    return ((rx / s, ry / s, rz / s), angle)


def ue_to_x3d_rot(q_ue: Quat) -> AxisAngle:
    """UE rotation quaternion -> X3D axis-angle, via R' = B R B^T."""
    r_ue = quat_to_matrix(q_ue)
    r_x3d = _mat_mul(_mat_mul(B_UE_TO_X3D, r_ue), _transpose(B_UE_TO_X3D))
    return matrix_to_axis_angle(r_x3d)


def x3d_to_ue_rot(axis: Vec3, angle: float) -> Quat:
    """X3D axis-angle -> UE rotation quaternion, via R = B^T R' B."""
    r_x3d = axis_angle_to_matrix(axis, angle)
    bt = _transpose(B_UE_TO_X3D)
    r_ue = _mat_mul(_mat_mul(bt, r_x3d), B_UE_TO_X3D)
    return matrix_to_quat(r_ue)


def quat_close(a: Quat, b: Quat, tol: float = 1e-6) -> bool:
    """
    Rotation-aware quaternion comparison. q and -q are the SAME rotation
    (double cover), so compare |dot| ~ 1 rather than component equality.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return abs(abs(dot) - 1.0) < tol


# ===========================================================================
# Calibration -- Mile 1 made operational
# ===========================================================================
def basis_from_axis_images(x_image: Vec3, y_image: Vec3, z_image: Vec3) -> Mat3:
    """
    Build B from a live calibration: export ONE known actor via UE's glTF
    exporter (or read it back from a trusted X3D pipeline), observe where UE's
    +X, +Y, +Z unit axes land in X3D space, and pass those three images here.

    B's columns ARE the axis images, so B = [x_image | y_image | z_image].
    The result is returned as-is; assert `is_orthonormal(B)` and
    `determinant(B) == -1` before locking it in place of B_UE_TO_X3D.
    """
    return (
        (x_image[0], y_image[0], z_image[0]),
        (x_image[1], y_image[1], z_image[1]),
        (x_image[2], y_image[2], z_image[2]),
    )


def axis_images_of(m: Mat3) -> list[Vec3]:
    """Inverse of `basis_from_axis_images`: the columns of B (for inspection)."""
    return [tuple(m[i][j] for i in range(3)) for j in range(3)]  # type: ignore[misc]
