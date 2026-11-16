"""Core and trusted ops: roles, expected ΔH/ΔS, interaction checks (spike 02 §2, §6)."""
import pytest

from dipm import (XY, XZ, CardinalityError, Design, InteractionError, KernelError, Profile, X, Y, Z,
                  centered_on, circular_pattern, countersink, edges_between, exactly, face_point, intent,
                  linear_pattern, plain)
from dipm import kernel as K
from dipm.sketch import rect_points

from conftest import block


def _ring(angle):
    d = Design("ring")
    prof = Profile(XZ, {"ib": (5.0, 0.0), "ob": (10.0, 0.0), "ot": (10.0, 4.0), "it": (5.0, 4.0)},
                   edge_names={"ib-ob": "bottom", "ob-ot": "outer", "ot-it": "top", "it-ib": "inner"})
    R = d.revolve("R", prof, axis=((0.0, 0.0), (0.0, 1.0)), angle=angle, tags=intent("R", "ring"))
    return d, R


def test_revolve_partial_has_caps_and_genus_0():
    d, R = _ring(180.0)
    b = d.build()
    assert b.signature.VEFRSH == (8, 12, 6, 0, 1, 0)
    assert len(b.resolve(R.cap("START"))) == 1 and len(b.resolve(R.side("top"))) == 1


def test_full_revolve_uses_fallback_and_declares_genus_1():
    d, R = _ring(360.0)
    b = d.build()
    assert b.signature.VEFRSH == (4, 6, 4, 2, 1, 1)
    assert set(b.record("R").detail["revol_fallback"]) == {"bottom", "top"}   # spike 02 §1.1 workaround
    for e in ("bottom", "outer", "top", "inner"):
        assert len(b.resolve(R.side(e))) == 1
    with pytest.raises(CardinalityError):
        b.resolve(R.cap("START"))                            # no caps on a full revolve


def test_full_revolve_touching_axis_has_genus_0():
    d = Design("disc")
    prof = Profile(XZ, rect_points(0.0, 0.0, 10.0, 4.0))
    d.revolve("R", prof, axis=((0.0, 0.0), (0.0, 1.0)))
    b = d.build()
    assert b.ok and b.signature.VEFRSH[5] == 0


def test_revolve_crossing_axis_is_refused():
    d = Design("bad")
    d.revolve("R", Profile(XZ, rect_points(-2.0, 0.0, 10.0, 4.0)), axis=((0.0, 0.0), (0.0, 1.0)))
    with pytest.raises(Exception, match="crosses its axis"):
        d.build()


def test_extrude_cut_with_declared_tunnel():
    d, E = block()
    slot = Profile(XY.offset(-1.0), rect_points(15.0, 10.0, 25.0, 20.0))
    S = d.extrude("S", slot, 22.0, mode="cut", expect={"dH": 1, "why": "through slot"}, tags=intent("S", "slot"))
    b = d.build()
    assert b.ok and b.signature.VEFRSH[5] == 1
    assert len(b.resolve(S.side("a-b"))) == 1               # tool side face became the slot wall


def test_extrude_cut_without_declaration_fails_delta_h():
    d, E = block()
    d.extrude("S", Profile(XY.offset(-1.0), rect_points(15.0, 10.0, 25.0, 20.0)), 22.0, mode="cut")
    b = d.build(on_fail="record")
    assert b.record("S").checks.failures()[0].name == "delta_H"


def test_add_must_touch_and_cut_must_overlap():
    d, E = block()
    d.extrude("F", Profile(XY.offset(50.0), rect_points(0.0, 0.0, 5.0, 5.0)), 5.0, mode="add")
    with pytest.raises(InteractionError, match="does not touch"):
        d.build()
    d, E = block()
    d.extrude("F", Profile(XY.offset(50.0), rect_points(0.0, 0.0, 5.0, 5.0)), 5.0, mode="cut")
    with pytest.raises(InteractionError, match="remove nothing"):
        d.build()


def test_chamfer_roles_and_overreach_is_loud():
    d, E = block()
    top_ab = edges_between(E.side("a-b"), E.cap("END"))
    C = d.chamfer("C", top_ab, 3.0)
    b = d.build()
    assert len(b.resolve(C.face(of=top_ab, card=exactly(1)))) == 1
    d2, E2 = block()
    d2.chamfer("C", edges_between(E2.side("a-b"), E2.cap("END")), 25.0)
    with pytest.raises(KernelError):
        d2.build()


def test_fillet_blend_role():
    d, E = block()
    F = d.fillet("F", [E.lateral_edge("a"), E.lateral_edge("b")], 2.0)
    b = d.build()
    assert len(b.resolve(F.blend())) == 2
    assert len(b.resolve(F.blend(of=E.lateral_edge("a"), card=exactly(1)))) == 1


def test_mirror_disjoint_declares_second_shell():
    d, E = block()
    d.mirror("M", (-5.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    b = d.build()
    assert b.ok and b.signature.VEFRSH[4] == 2


def test_transform_keeps_references_and_volume():
    d, E = block()
    d.transform("T", translate=(1.0, 2.0, 3.0), rotate=((0, 0, 0), (0, 0, 1), 30.0))
    b = d.build()
    (f,) = b.resolve(E.cap("END"))
    assert K.centroid(f).z == pytest.approx(23.0)
    assert K.volume(b.shape) == pytest.approx(40 * 30 * 20)


def test_shell_rim_and_offset_roles():
    d, E = block()
    S = d.shell("SH", [E.cap("END")], 2.0)
    b = d.build()
    assert b.ok and b.signature.VEFRSH == (16, 24, 11, 1, 1, 0)
    (rim,) = b.resolve(E.cap("END"))                         # opening ref continues onto the rim
    assert len(K.subshapes(rim, K.KINDS["wire"])) == 2
    assert len(b.resolve(S.offset(E.side("a-b")))) == 1


def test_clean_is_identity_when_nothing_merges(bracket):
    b0 = bracket.build()
    assert all(r.ok for r in b0.records)
    d, E = block()
    d.clean("CL")
    b = d.build()
    assert b.ok and all(e.genealogy == () for e in b.ledger.items)


def test_linear_and_circular_hole_patterns():
    d, E = block()
    H = d.hole("P", E.cap("END"), linear_pattern(face_point(E.cap("END"), along=(X, 0.2), across=(Y, 0.5)), X, 3, 12.0),
               plain(6.0), tags=intent("P", "pattern"), instance_tags=["P.1", "P.2", "P.3"])
    b = d.build()
    assert b.ok and b.signature.VEFRSH[5] == 3
    assert [round(K.centroid(b.resolve(H.wall(k))[0]).x, 6) for k in range(3)] == [8.0, 20.0, 32.0]
    d2, E2 = block(Lx=40.0, Wy=40.0)
    H2 = d2.hole("C", E2.cap("END"), circular_pattern(centered_on(E2.cap("END")), Z, 6, 12.0, X), countersink("#8"))
    b2 = d2.build()
    assert b2.ok and b2.signature.VEFRSH[5] == 6 and len(b2.resolve(H2.countersink(5))) == 1


def test_hole_center_must_lie_on_and_inside_the_face():
    d, E = block()
    d.hole("P", E.cap("END"), linear_pattern(face_point(E.cap("END"), along=(X, 0.5), across=(Y, 0.5)), X, 3, 15.0),
           plain(4.0))
    with pytest.raises(InteractionError, match="not inside face"):
        d.build()
