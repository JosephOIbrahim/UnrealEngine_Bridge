"""
Golden tests for the UE <-> X3D thin-slice harness (x3d_bridge).

The battery defends two guarantees and nothing else:
  1. Round trip is lossless on thin-slice fields:  deserialize(serialize(x)) == x
  2. Malformed edits are rejected at validate() -- on paper, before the editor.

Plus the coordinate crux is pinned (B orthonormal, det == -1 -- a real handedness
flip; position/scale/rotation each round-trip exactly), and the regressions found
by the adversarial verification pass are locked in (TestWorkflowRegressions).

All checks are synchronous, so no @pytest.mark.asyncio (asyncio_mode = "strict").
"""

import math

import pytest

from x3d_bridge import (
    B_UE_TO_X3D,
    CM_TO_M,
    Actor,
    ApplyOp,
    AssignMaterial,
    DeleteActor,
    MockBridge,
    Reparent,
    SetTransform,
    SpawnActor,
    X3DGrammarError,
    axis_images_of,
    basis_from_axis_images,
    deserialize,
    determinant,
    diff_actors,
    emit_python,
    is_orthonormal,
    quat_close,
    run_loop,
    serialize,
    to_preview_html,
    ue_to_x3d_pos,
    ue_to_x3d_rot,
    ue_to_x3d_scale,
    validate,
    write_preview,
    x3d_to_ue_pos,
    x3d_to_ue_rot,
    x3d_to_ue_scale,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


def _norm(q):
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


def _assert_actor_close(a, b):
    assert a.guid == b.guid
    assert a.mesh == b.mesh
    assert a.material == b.material
    assert a.mobility == b.mobility
    assert a.folder == b.folder
    assert a.parent == b.parent
    assert _close(a.t, b.t), (a.t, b.t)
    assert _close(a.s, b.s), (a.s, b.s)
    assert quat_close(a.r, b.r), (a.r, b.r)


# ===========================================================================
# The coordinate crux
# ===========================================================================
class TestBasis:
    def test_basis_is_orthonormal(self):
        assert is_orthonormal(B_UE_TO_X3D)

    def test_basis_flips_handedness(self):
        # det == -1 is the whole point: a reflection converts LH -> RH.
        # The spec's template ((1,0,0),(0,0,1),(0,-1,0)) had det +1 and was wrong.
        assert math.isclose(determinant(B_UE_TO_X3D), -1.0, abs_tol=1e-12)

    def test_axis_roles_preserved(self):
        # UE right (+Y) -> X3D right (+X); up (+Z) -> up (+Y); forward (+X) -> -Z.
        assert _close(ue_to_x3d_pos((0.0, 100.0, 0.0)), (1.0, 0.0, 0.0))
        assert _close(ue_to_x3d_pos((0.0, 0.0, 100.0)), (0.0, 1.0, 0.0))
        assert _close(ue_to_x3d_pos((100.0, 0.0, 0.0)), (0.0, 0.0, -1.0))

    def test_cm_to_m(self):
        assert CM_TO_M == 0.01

    def test_position_round_trip(self):
        for t in [(420.0, 0.0, 155.0), (-13.5, 7.25, 0.0), (1e5, -2e4, 3.3)]:
            assert _close(x3d_to_ue_pos(ue_to_x3d_pos(t)), t)

    def test_calibration_reconstructs_basis(self):
        # basis_from_axis_images rebuilds B from where UE unit axes land in X3D.
        cols = axis_images_of(B_UE_TO_X3D)
        rebuilt = basis_from_axis_images(cols[0], cols[1], cols[2])
        assert rebuilt == B_UE_TO_X3D
        assert is_orthonormal(rebuilt)
        assert math.isclose(determinant(rebuilt), -1.0, abs_tol=1e-12)


class TestRotation:
    @pytest.mark.parametrize(
        "q",
        [
            (0.0, 0.0, 0.0, 1.0),  # identity
            _norm((0.0, 0.0, 0.7071, 0.7071)),  # 90 deg about UE Z
            (1.0, 0.0, 0.0, 0.0),  # 180 deg about UE X
            (0.0, 1.0, 0.0, 0.0),  # 180 deg about UE Y
            _norm((0.3, -0.6, 0.2, 0.9)),  # arbitrary
            _norm((-0.5, 0.5, -0.5, 0.5)),  # 120 deg tri-axis
        ],
    )
    def test_rotation_round_trip(self, q):
        axis, angle = ue_to_x3d_rot(q)
        back = x3d_to_ue_rot(axis, angle)
        assert quat_close(q, back), (q, back)

    def test_rotation_leaves_x3d_axis_angle_wellformed(self):
        axis, angle = ue_to_x3d_rot(_norm((0.3, -0.6, 0.2, 0.9)))
        assert math.isclose(sum(c * c for c in axis), 1.0, abs_tol=1e-9)
        assert 0.0 <= angle <= math.pi + 1e-9


# ===========================================================================
# Grammar round trip -- the invariant
# ===========================================================================
class TestRoundTrip:
    def test_single_actor_pos_scale(self):
        a = Actor(guid="A1", mesh="/Game/M/SM_Rock", t=(420.0, 0.0, 155.0), s=(2.0, 1.0, 1.0))
        b = deserialize(serialize([a]))[0]
        _assert_actor_close(a, b)

    def test_full_transform_multiple_actors(self):
        actors = [
            Actor(
                guid="Actor_7F3A",
                mesh="/Game/Meshes/SM_Rock_01",
                material="/Game/Mat/M_Granite",
                mobility="Static",
                folder="Environment/Rocks",
                t=(0.0, 0.0, 0.0),
                r=_norm((0.0, 0.0, 0.3826, 0.9238)),  # 45 deg yaw
                s=(1.0, 1.0, 1.0),
            ),
            Actor(
                guid="Actor_91C2",
                mesh="/Game/Meshes/SM_Rock_01",
                material="/Game/Mat/M_Granite",
                t=(420.0, 155.0, -30.0),
                r=_norm((0.3, -0.6, 0.2, 0.9)),
                s=(3.0, 0.5, 2.0),
            ),
        ]
        out = deserialize(serialize(actors))
        assert len(out) == 2
        for a, b in zip(actors, out, strict=True):
            _assert_actor_close(a, b)

    def test_metadata_round_trip(self):
        a = Actor(
            guid="A1",
            mesh="/Game/M",
            mobility="Movable",
            folder="Set/Props",
            parent="Actor_Root",
            t=(1.0, 2.0, 3.0),
        )
        b = deserialize(serialize([a]))[0]
        _assert_actor_close(a, b)

    def test_escaping_round_trip(self):
        # Asset paths are safe, but the escaper must survive XML metacharacters.
        a = Actor(guid="A<1>&", mesh='/Game/"odd"/M&N', folder="a<b>c")
        b = deserialize(serialize([a]))[0]
        assert b.guid == "A<1>&"
        assert b.mesh == '/Game/"odd"/M&N'
        assert b.folder == "a<b>c"

    def test_material_def_use_dedup(self):
        actors = [
            Actor(guid="A1", material="/Game/Mat/M_Granite"),
            Actor(guid="A2", material="/Game/Mat/M_Granite"),
            Actor(guid="A3", material="/Game/Mat/M_Steel"),
        ]
        x3d = serialize(actors)
        assert x3d.count('DEF="Mat_0"') == 1
        assert x3d.count('USE="Mat_0"') == 1  # A2 reuses A1's material
        assert x3d.count('DEF="Mat_1"') == 1  # A3 is a distinct material
        out = deserialize(x3d)
        assert out[0].material == "/Game/Mat/M_Granite"
        assert out[1].material == "/Game/Mat/M_Granite"
        assert out[2].material == "/Game/Mat/M_Steel"

    def test_validate_accepts_serialized_output(self):
        actors = [Actor(guid="A1", mesh="/Game/M", material="/Game/Mat/M", t=(5.0, 6.0, 7.0))]
        ok, errors = validate(serialize(actors))
        assert ok, errors


# ===========================================================================
# The validation boundary -- bad edits die on paper
# ===========================================================================
class TestValidateBoundary:
    def test_out_of_grammar_rejected(self):
        ok, errors = validate("<X3D><Scene><Frobnicate/></Scene></X3D>")
        assert not ok
        assert any("out-of-grammar" in e for e in errors)

    def test_dangling_use_rejected(self):
        ok, errors = validate('<X3D><Scene><Material USE="ghost"/></Scene></X3D>')
        assert not ok
        assert any("dangling USE" in e for e in errors)

    def test_resolvable_use_accepted(self):
        ok, errors = validate(
            '<X3D><Scene><Material DEF="m"/><Material USE="m"/></Scene></X3D>'
        )
        assert ok, errors

    def test_nan_translation_rejected(self):
        ok, errors = validate('<X3D><Scene><Transform translation="0 nan 0"/></Scene></X3D>')
        assert not ok
        assert any("non-finite" in e or "non-numeric" in e for e in errors)

    def test_inf_scale_rejected(self):
        ok, errors = validate('<X3D><Scene><Transform scale="1 inf 1"/></Scene></X3D>')
        assert not ok

    def test_malformed_xml_rejected(self):
        ok, errors = validate("<X3D><Scene><Transform></X3D>")
        assert not ok
        assert any("malformed" in e for e in errors)

    def test_deserialize_raises_on_unknown_node(self):
        with pytest.raises(X3DGrammarError):
            deserialize("<X3D><Scene><Frobnicate/></Scene></X3D>")

    def test_deserialize_raises_on_bad_root(self):
        with pytest.raises(X3DGrammarError):
            deserialize("<Scene><Transform/></Scene>")


# ===========================================================================
# Apply seam -- assert the op sequence without a live editor
# ===========================================================================
class TestApplyDiff:
    def test_move_emits_one_set_transform(self):
        before = [Actor(guid="A1", t=(0.0, 0.0, 0.0))]
        after = [Actor(guid="A1", t=(100.0, 0.0, 0.0))]
        ops = diff_actors(before, after)
        assert len(ops) == 1
        assert isinstance(ops[0], SetTransform)
        assert ops[0].guid == "A1"
        assert _close(ops[0].t, (100.0, 0.0, 0.0))

    def test_unchanged_emits_nothing(self):
        actors = [Actor(guid="A1", t=(1.0, 2.0, 3.0), r=_norm((0.1, 0.2, 0.3, 0.9)))]
        # round-trip float noise must NOT produce a spurious op
        rt = deserialize(serialize(actors))
        assert diff_actors(actors, rt) == []

    def test_spawn_and_delete(self):
        before = [Actor(guid="A1")]
        after = [Actor(guid="A1"), Actor(guid="A2", mesh="/Game/M")]
        ops = diff_actors(before, after)
        assert [type(o) for o in ops] == [SpawnActor]
        assert ops[0].guid == "A2"

        ops2 = diff_actors(after, before)
        assert [type(o) for o in ops2] == [DeleteActor]
        assert ops2[0].guid == "A2"

    def test_material_change_emits_assign(self):
        before = [Actor(guid="A1", material=None)]
        after = [Actor(guid="A1", material="/Game/Mat/M")]
        ops = diff_actors(before, after)
        assert any(isinstance(o, AssignMaterial) and o.material == "/Game/Mat/M" for o in ops)

    def test_reparent_emits_op(self):
        before = [Actor(guid="A1", parent=None)]
        after = [Actor(guid="A1", parent="Root")]
        ops = diff_actors(before, after)
        assert any(isinstance(o, Reparent) and o.parent == "Root" for o in ops)

    def test_emit_python_shapes(self):
        # Assert the op's DATA reaches the snippet, not just the method name --
        # a presence-only check would pass with hardcoded/dropped arguments.
        st = emit_python(SetTransform(guid="/L/A1", t=(1.0, 2.0, 3.0), s=(4.0, 5.0, 6.0)))
        assert '"/L/A1"' in st
        assert "set_actor_location(unreal.Vector(1.0, 2.0, 3.0)" in st
        assert "set_actor_scale3d(unreal.Vector(4.0, 5.0, 6.0)" in st
        assert "unreal.Quat(" in st

        sp = emit_python(SpawnActor(guid="A1", mesh="/Game/M"))
        assert "spawn_actor_from_class" in sp and 'set_actor_label("A1")' in sp and '"/Game/M"' in sp

        de = emit_python(DeleteActor(guid="A1"))
        assert "destroy_actor" in de and '"A1"' in de

        am = emit_python(AssignMaterial(guid="A1", material="/Game/M"))
        assert "set_material" in am and '"/Game/M"' in am

        rp = emit_python(Reparent(guid="A1", parent="Root"))
        assert "attach_to_actor" in rp and '"Root"' in rp


# ===========================================================================
# The full loop
# ===========================================================================
class TestLoop:
    def test_identity_edit_applies_nothing(self):
        actors = [Actor(guid="A1", mesh="/Game/M", t=(10.0, 20.0, 30.0))]
        bridge = MockBridge()
        result = run_loop(lambda: actors, bridge=bridge)
        assert result.ok
        assert result.ops == []
        assert bridge.ops == []

    def test_invalid_edit_blocks_apply(self):
        actors = [Actor(guid="A1")]
        bridge = MockBridge()

        def bad_edit(_x3d):
            return "<X3D><Scene><Frobnicate/></Scene></X3D>"

        result = run_loop(lambda: actors, edit_fn=bad_edit, bridge=bridge)
        assert not result.ok
        assert result.ops == []
        assert bridge.ops == []  # the boundary held -- nothing reached the editor

    def test_valid_edit_reaches_bridge(self):
        actors = [Actor(guid="A1", t=(0.0, 0.0, 0.0))]
        bridge = MockBridge()

        def move_edit(x3d):
            # UE (0,0,0) serializes to X3D translation "0.0 0.0 0.0"; move it in X3D.
            return x3d.replace('translation="0.0 0.0 0.0"', 'translation="0.0 0.0 -1.0"')

        result = run_loop(lambda: actors, edit_fn=move_edit, bridge=bridge)
        assert result.ok
        assert len(bridge.ops) == 1
        assert isinstance(bridge.ops[0], SetTransform)
        # X3D (0,0,-1) m -> UE (+100, 0, 0) cm  (forward)
        assert _close(bridge.ops[0].t, (100.0, 0.0, 0.0), tol=1e-3)


# ===========================================================================
# Regressions surfaced by the adversarial verification workflow
# ===========================================================================
class TestWorkflowRegressions:
    def test_validate_rejects_short_translation(self):
        ok, errors = validate('<X3D><Scene><Transform DEF="a" translation="1 2"/></Scene></X3D>')
        assert not ok
        assert any("translation" in e and "numbers" in e for e in errors), errors

    def test_validate_rejects_short_rotation(self):
        ok, errors = validate('<X3D><Scene><Transform DEF="a" rotation="0 0 1"/></Scene></X3D>')
        assert not ok
        assert any("rotation" in e and "numbers" in e for e in errors), errors

    def test_validate_rejects_non_x3d_root(self):
        ok, errors = validate('<Scene><Transform translation="1 2 3"/></Scene>')
        assert not ok
        assert any("expected 'X3D'" in e for e in errors), errors

    def test_loop_blocks_wrong_arity_edit(self):
        bridge = MockBridge()

        def bad_arity(x3d):
            return x3d.replace('scale="1.0 1.0 1.0"', 'scale="1.0 1.0"')

        result = run_loop(lambda: [Actor(guid="A1", t=(1.0, 2.0, 3.0))], edit_fn=bad_arity, bridge=bridge)
        assert not result.ok
        assert bridge.ops == []

    def test_spawn_with_material_emits_assign(self):
        ops = diff_actors([], [Actor(guid="A2", mesh="/Game/M", material="/Game/Mat/M")])
        assert [type(o) for o in ops] == [SpawnActor, AssignMaterial]
        assert ops[1].material == "/Game/Mat/M"

    def test_spawn_with_parent_emits_reparent(self):
        ops = diff_actors([], [Actor(guid="A2", mesh="/Game/M", parent="Root")])
        assert [type(o) for o in ops] == [SpawnActor, Reparent]
        assert ops[1].parent == "Root"

    def test_spawn_with_material_and_parent(self):
        ops = diff_actors([], [Actor(guid="A2", material="/Game/Mat/M", parent="Root")])
        assert [type(o) for o in ops] == [SpawnActor, AssignMaterial, Reparent]

    def test_empty_optional_coerced_to_none(self):
        a = Actor(guid="A1", folder="", material="", parent="")
        assert a.folder is None and a.material is None and a.parent is None
        _assert_actor_close(a, deserialize(serialize([a]))[0])

    def test_control_whitespace_round_trip(self):
        a = Actor(guid="A1", mesh="/Game/a\tb\nc", folder="x\ny")
        b = deserialize(serialize([a]))[0]
        assert b.mesh == "/Game/a\tb\nc"
        assert b.folder == "x\ny"

    def test_preview_escapes_title_leaves_x3d_raw(self):
        out = to_preview_html(serialize([Actor(guid="A1")]), title="<script>alert(1)</script>")
        assert "<script>alert(1)</script>" not in out
        assert "&lt;script&gt;" in out
        assert 'DEF="A1"' in out  # x3d payload still raw


# ===========================================================================
# Audit hardening -- close false-green gaps found by the test-suite audit
# ===========================================================================
class TestAuditHardening:
    def test_rotation_forward_known_axis_angle(self):
        # Round-trip tests stay green even under an IDENTITY conjugation, so pin
        # the forward map to hand-computed values -- a missing/wrong B*R*B^T dies.
        # 90deg yaw about UE +Z -> 90deg about X3D -Y (handedness reverses sense).
        axis, angle = ue_to_x3d_rot(_norm((0.0, 0.0, 0.7071, 0.7071)))
        assert math.isclose(angle, math.pi / 2, abs_tol=1e-5), angle
        assert _close(axis, (0.0, -1.0, 0.0)), axis
        # 180deg about UE +X -> 180deg about the X3D Z axis (+Z ~ -Z at 180deg).
        axis2, angle2 = ue_to_x3d_rot((1.0, 0.0, 0.0, 0.0))
        assert math.isclose(angle2, math.pi, abs_tol=1e-6), angle2
        assert _close(axis2, (0.0, 0.0, 1.0)) or _close(axis2, (0.0, 0.0, -1.0)), axis2

    def test_scale_permutes_axes_not_identity(self):
        # Round trips are blind to a self-inverse identity bug; pin the permutation.
        assert ue_to_x3d_scale((3.0, 0.5, 2.0)) == (0.5, 2.0, 3.0)
        assert x3d_to_ue_scale((0.5, 2.0, 3.0)) == (3.0, 0.5, 2.0)

    def test_emit_python_reparent_detach(self):
        out = emit_python(Reparent(guid="A1", parent=None))
        assert "detach_from_actor" in out
        assert "attach_to_actor" not in out

    def test_emit_python_rejects_unknown_op(self):
        with pytest.raises(TypeError, match="unknown op"):
            emit_python(ApplyOp(guid="A1"))

    def test_write_preview_writes_file(self, tmp_path):
        x3d = serialize([Actor(guid="A1", mesh="/Game/M")])
        dest = tmp_path / "view.html"
        returned = write_preview(x3d, dest, title="T")
        assert returned == dest
        written = dest.read_text(encoding="utf-8")
        assert written == to_preview_html(x3d, title="T")
        assert 'DEF="A1"' in written

    def test_run_loop_survives_deserialize_gap(self, monkeypatch):
        # Fault-inject the defensive path: force validate to pass, then feed a
        # document deserialize rejects. run_loop must return ok=False, apply none.
        monkeypatch.setattr("x3d_bridge.loop.validate", lambda _x: (True, []))
        bridge = MockBridge()
        result = run_loop(
            lambda: [Actor(guid="A1")], edit_fn=lambda _x: "<Scene/>", bridge=bridge
        )
        assert not result.ok
        assert result.errors
        assert bridge.ops == []

    def test_loop_result_captures_both_documents(self):
        actors = [Actor(guid="A1", t=(0.0, 0.0, 0.0))]
        result = run_loop(lambda: actors)
        assert result.x3d_before == serialize(actors)
        assert result.x3d_after == result.x3d_before  # identity edit

    def test_material_removal_emits_no_op(self):
        before = [Actor(guid="A1", material="/Game/Mat/M")]
        after = [Actor(guid="A1", material=None)]
        assert diff_actors(before, after) == []  # documented: no un-assign op


# ===========================================================================
# Preview (Mile 6) -- smoke
# ===========================================================================
def test_preview_embeds_x3d():
    x3d = serialize([Actor(guid="A1", mesh="/Game/M")])
    html = to_preview_html(x3d)
    assert "<x3d-canvas>" in html
    assert 'DEF="A1"' in html
