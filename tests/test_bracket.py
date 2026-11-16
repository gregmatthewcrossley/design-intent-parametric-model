"""The architecture §8 shelf bracket: build, §8.6 edit tests via the stability harness, determinism."""
import hashlib
import subprocess
import sys

import pytest

from dipm import kernel as K
from dipm import stability

from conftest import EXAMPLE, ROOT


def _axis_point(build, ref):
    """Centre of a hole wall (cylinder face centroid lies on the axis)."""
    (f,) = build.resolve(ref)
    return K.centroid(f)


def _radius(build, ref):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.TopoDS import TopoDS
    (f,) = build.resolve(ref)
    return BRepAdaptor_Surface(TopoDS.Face(f)).Cylinder().Radius()


def test_default_bracket_builds_and_passes_all_invariants(bracket_build):
    b = bracket_build
    assert b.ok, [str(e) for e in b.errors]
    assert [r.id for r in b.records] == ["R.body", "C.gusset", "A.P.holes", "A.3.cable", "B.1.screw", "R.fillet"]
    dh = [next(c.got for c in r.checks.checks if c.name == "delta_H") for r in b.records]
    assert dh == [0, 0, 2, 1, 1, 0]                  # spike 01: E,G,(W+K)x2,C,S,F
    assert b.signature.VEFRSH[5] == 4 and b.signature.VEFRSH[4] == 1
    assert not b.untracked_faces()                    # every face has a genealogy
    assert b.record("R.fillet").inputs[0].genealogies == ("C.gusset:split2",)


def test_layout_relations_at_defaults(bracket, bracket_build):
    """A.P: lower hole 2xØ above the leg end, upper hole one tool-access radius below the gusset;
    A.3: midpoint of the exposed plate (0 .. gusset bottom), NOT between the screws (DECISIONS #8)."""
    b = bracket_build
    AP, A3 = bracket.feature("A.P.holes"), bracket.feature("A.3.cable")
    lo, hi = _axis_point(b, AP.wall(0)), _axis_point(b, AP.wall(1))
    cab = _axis_point(b, A3.wall(0))
    gusset_bottom = 0.75 * 200 - 5 - 0.4 * 200          # 65
    assert (lo.x, lo.z) == pytest.approx((0.0, 2 * 4.5))
    assert (hi.x, hi.z) == pytest.approx((0.0, gusset_bottom - 15.0))
    assert (cab.x, cab.z) == pytest.approx((0.0, gusset_bottom / 2))
    assert cab.z != pytest.approx((lo.z + hi.z) / 2)    # the two readings of §8.5 differ here
    s = _axis_point(b, bracket.feature("B.1.screw").wall(0))
    assert (s.x, s.y) == pytest.approx((0.0, 0.75 * 0.8 * 200))


def test_edit_shelf_depth_200_to_300(bracket):
    """§8.6: holes stay symmetric and re-spread; gusset scales; no structural change."""
    b0, b1, problems = stability.edit_test(bracket, {"shelf_depth": 200.0}, {"shelf_depth": 300.0})
    assert problems == []
    AP = bracket.feature("A.P.holes")
    for b, d in ((b0, 200.0), (b1, 300.0)):
        gb = 0.75 * d - 5 - 0.4 * d
        assert _axis_point(b, AP.wall(1)).z == pytest.approx(gb - 15.0)
        assert _axis_point(b, AP.wall(0)).x == pytest.approx(0.0)
        assert _axis_point(b, AP.wall(1)).x == pytest.approx(0.0)
    hyp = bracket.feature("C.gusset").side("hypotenuse")
    a0, a1 = (K.area(b.resolve(hyp)[0]) for b in (b0, b1))
    assert a1 / a0 == pytest.approx(1.5)              # gusset scales with shelf_depth


def test_edit_t_5_to_8(bracket):
    """§8.6: fillet radius and gusset thickness follow t."""
    b0, b1, problems = stability.edit_test(bracket, {"t": 5.0}, {"t": 8.0})
    assert problems == []
    F, G = bracket.feature("R.fillet"), bracket.feature("C.gusset")
    for b, t in ((b0, 5.0), (b1, 8.0)):
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.TopoDS import TopoDS
        radii = {round(BRepAdaptor_Surface(TopoDS.Face(f)).Cylinder().Radius(), 9) for f in b.resolve(F.blend())}
        assert radii == {t}
        x0 = K.centroid(b.resolve(G.cap("START"))[0]).x
        x1 = K.centroid(b.resolve(G.cap("END"))[0]).x
        assert x1 - x0 == pytest.approx(t)


def test_edit_screw_8_to_10_and_cable_hole_does_not_move(bracket):
    """§8.6: Ø and edge inset grow, pattern stays symmetric; moving the wall pattern does NOT
    move the cable hole (its intent is 'plate centre', not 'between the screws')."""
    b0, b1, problems = stability.edit_test(bracket, {"screw": "#8"}, {"screw": "#10"})
    assert problems == []
    AP, A3, B1 = (bracket.feature(i) for i in ("A.P.holes", "A.3.cable", "B.1.screw"))
    assert _radius(b0, AP.wall(0)) == pytest.approx(2.25) and _radius(b1, AP.wall(0)) == pytest.approx(2.6)
    assert _radius(b1, B1.wall(0)) == pytest.approx(2.6)
    assert _axis_point(b1, AP.wall(0)).z == pytest.approx(2 * 5.2)       # inset = 2 x Ø grew
    assert _axis_point(b0, AP.wall(0)).z != pytest.approx(_axis_point(b1, AP.wall(0)).z)   # pattern moved
    c0, c1 = _axis_point(b0, A3.wall(0)), _axis_point(b1, A3.wall(0))
    assert (c1.x, c1.y, c1.z) == pytest.approx((c0.x, c0.y, c0.z))      # cable hole did not move


def test_stability_harness_over_declared_ranges(bracket):
    rep = stability.run(bracket)
    assert rep.ok, str(rep)
    assert len(rep.points) >= 8


def test_stability_harness_flags_structural_change():
    """Negative control: a parameter whose range lets a hole leave its face is reported unstable."""
    from dipm import XY, Design, Profile, X, Y, face_point, plain
    from dipm.sketch import rect_points
    d = Design("slider")
    u = d.param("u", 0.5, range=(0.3, 1.2), unit="")
    E = d.extrude("E", Profile(XY, rect_points(0.0, 0.0, 40.0, 30.0)), 5.0)
    d.hole("H", E.cap("END"), face_point(E.cap("END"), along=(X, u), across=(Y, 0.5)), plain(4.0))
    rep = stability.run(d)
    assert not rep.ok
    bad = [p for p in rep.points if not p.ok]
    assert [p.changed for p in bad] == [{"u": 1.2}]
    assert "not inside face" in bad[0].problems[0]


def test_determinism_in_process(bracket):
    a = bracket.build().canonical()
    bracket.build(shelf_depth=300.0, t=8.0, screw="#10")       # no state leaks between builds
    b = bracket.build().canonical()
    assert a[0] == "brep" and a == b


def test_determinism_across_processes(bracket):
    here = hashlib.sha256(bracket.build().canonical()[1]).hexdigest()
    code = ("import importlib.util,hashlib;"
            f"s=importlib.util.spec_from_file_location('m', r'{EXAMPLE}');m=importlib.util.module_from_spec(s);"
            "s.loader.exec_module(m);print(hashlib.sha256(m.design.build().canonical()[1]).hexdigest())")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, check=True)
    assert out.stdout.strip() == here


def test_stability_full_corner_grid(bracket):
    """Every corner of the declared ranges x every screw (12 builds): same topology and genealogy."""
    pts = stability.grid_points(bracket, {"shelf_depth": [180.0, 300.0], "t": [4.0, 8.0], "screw": ["#6", "#8", "#10"]})
    rep = stability.run(bracket, pts)
    assert rep.ok, str(rep)


def test_out_of_range_geometry_fails_loudly_not_silently(bracket_mod):
    """Below the declared shelf_depth range the cable hole meets a countersink: an InteractionError,
    not a silently wrong solid (why the range starts at 180; DECISIONS #12)."""
    from dipm import InteractionError
    from dipm.expr import Param
    d = bracket_mod.make_design()
    d.params["shelf_depth"] = Param("shelf_depth", 200.0, (100.0, 300.0))
    with pytest.raises(InteractionError) as ei:
        d.build(shelf_depth=150.0, t=8.0)
    assert ei.value.feature == "A.3.cable" and "A.P.holes" in str(ei.value)
