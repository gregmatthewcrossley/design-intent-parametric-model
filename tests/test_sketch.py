"""v0 sketch profiles: named points/edges, constructions, branch tags (dsl.md §3.2)."""
import pytest

from dipm import XY, Design, Profile, SketchError
from dipm.expr import ParamRef
from dipm.sketch import between, line_line, midpoint, offset, on_side, rect_points


class Env:
    def __init__(self, **p):
        self.params = p


def test_points_are_parameter_expressions():
    w = ParamRef("w")
    p = Profile(XY, rect_points(0.0, 0.0, 2 * w, w))
    sp = p.evaluate(Env(w=5.0))
    assert sp.points2d["c"] == (10.0, 5.0) and sp.signed_area == pytest.approx(50.0)
    assert set(sp.edges) == {"a-b", "b-c", "c-d", "d-a"}


def test_edge_aliases_become_reference_sources():
    d = Design("x")
    E = d.extrude("E", Profile(XY, rect_points(0.0, 0.0, 4.0, 3.0), edge_names={"a-b": "front"}), 2.0)
    b = d.build()
    assert len(b.resolve(E.side("front"))) == 1


def test_constructions():
    pts = {"a": (0.0, 0.0), "b": (10.0, 0.0), "c": (10.0, 10.0)}
    env = Env()
    assert midpoint("a", "b").solve(env, pts) == (5.0, 0.0)
    assert between("a", "b", 0.25).solve(env, pts) == (2.5, 0.0)
    assert offset("a", (0.0, 2.0), 3.0).solve(env, pts) == (0.0, 3.0)
    assert line_line("a", "c", "b", (0.0, 10.0)).solve(env, pts) == pytest.approx((5.0, 5.0))
    with pytest.raises(SketchError, match="parallel"):
        line_line("a", "b", (0.0, 1.0), (5.0, 1.0)).solve(env, pts)


def test_construction_inside_profile():
    p = Profile(XY, {"a": (0.0, 0.0), "b": (10.0, 0.0), "m": offset(midpoint("a", "b"), (0.0, 1.0), 4.0)})
    sp = p.evaluate(Env())
    assert sp.points2d["m"] == (5.0, 4.0)


def test_branch_tag_on_side_fails_loudly_on_flip():
    h = ParamRef("h")
    p = Profile(XY, {"a": (0.0, 0.0), "b": (10.0, 0.0), "apex": on_side((5.0, h), "a", "b", "left")})
    assert p.evaluate(Env(h=3.0)).points2d["apex"] == (5.0, 3.0)
    with pytest.raises(SketchError, match="branch flip"):
        p.evaluate(Env(h=-3.0))


def test_winding_branch_tag():
    h = ParamRef("h")
    p = Profile(XY, {"a": (0.0, 0.0), "b": (10.0, 0.0), "c": (5.0, h)}, winding="ccw")
    p.evaluate(Env(h=4.0))
    with pytest.raises(SketchError) as ei:
        p.evaluate(Env(h=-4.0))
    assert ei.value.expected == "ccw" and ei.value.got == "cw"


def test_self_intersecting_and_degenerate_profiles():
    with pytest.raises(SketchError, match="self-intersecting"):
        Profile(XY, {"a": (0.0, 0.0), "b": (10.0, 10.0), "c": (10.0, 0.0), "d": (0.0, 10.0)}, winding=None).evaluate(Env())
    with pytest.raises(SketchError, match="zero length"):
        Profile(XY, {"a": (0.0, 0.0), "b": (0.0, 0.0), "c": (1.0, 1.0)}).evaluate(Env())


def test_parameter_range_is_enforced():
    from dipm import ParameterError
    d = Design("x")
    w = d.param("w", 5.0, range=(1.0, 10.0))
    d.extrude("E", Profile(XY, rect_points(0.0, 0.0, w, w)), 1.0)
    with pytest.raises(ParameterError):
        d.build(w=20.0)
    with pytest.raises(ParameterError):
        d.build(nope=1.0)
