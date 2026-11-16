"""Invariants (dsl.md §5), including the spike negative controls."""
from dataclasses import dataclass

import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from dipm import (XZ, Design, InteractionError, InvariantError, Profile, X, Y, Z, blind, face_point, intent,
                  linear_pattern, plain, through)
from dipm import kernel as K
from dipm.invariants import adjacency_hash, euler_counts
from dipm.ops import Expect, Feature
from dipm.program import StepOut
from dipm.refs import Tag

from conftest import block


# ---------------------------------------------------------------- Euler counting rule

def _box(a=10, b=10, c=10):
    return BRepPrimAPI_MakeBox(a, b, c).Shape()


def test_euler_counting_rule_on_primitives():
    assert euler_counts(_box()).tuple6() == (8, 12, 6, 0, 1, 0)
    cyl = BRepPrimAPI_MakeCylinder(5, 10).Shape()
    assert euler_counts(cyl).tuple6() == (2, 3, 3, 0, 1, 0)          # seam counted once
    sph = euler_counts(BRepPrimAPI_MakeSphere(5).Shape())
    assert sph.tuple6() == (2, 1, 1, 0, 1, 0) and sph.E_degenerated == 2   # pole edges excluded


def test_euler_excludes_fillet_corner_degenerated_edges():
    box = _box()
    mk = BRepFilletAPI_MakeFillet(box)
    for e in K.subshapes(box, K.KINDS["edge"]):
        mk.Add(1.0, TopoDS.Edge(e))
    mk.Build()
    c = euler_counts(mk.Shape())
    assert c.ok and int(c.H) == 0 and c.E_degenerated == 8


def test_genus_of_through_holes():
    box = _box(30, 30, 10)
    for i, x in enumerate((8, 22), start=1):
        box = BRepAlgoAPI_Cut(box, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, 15, -1), gp_Dir(0, 0, 1)), 2, 12).Shape()).Shape()
        assert int(euler_counts(box).H) == i


# ---------------------------------------------------------------- ΔH negative controls

def test_blind_hole_caught_by_delta_h_on_bracket(bracket_mod):
    """Spike 01 §2.3: the shelf screw at u=0.4 lands on the gusset and turns blind.
    All references still resolve; only ΔH catches it.  The extent comes from the bracket's
    interpretations lock (B.1 -> through_plate); re-resolving this variant instead raises a
    'default overridden' notice (tests/test_interpret.py)."""
    d = bracket_mod.make_design(shelf_hole_u=0.4)
    with pytest.raises(InvariantError) as ei:
        d.build()
    e = ei.value
    assert e.feature == "B.1.screw" and e.invariant == "delta_H"
    assert e.expected == 1 and e.got == 0
    assert "hole@B.1" in str(e) and "hole(clearance, through_plate)" in str(e)
    # in record mode the wall reference still resolves one(): a reference check alone would miss it
    b = d.build(on_fail="record")
    assert not b.ok
    assert b.record("B.1.screw").checks.failures()[0].name == "delta_H"


def test_through_plate_hole_turns_blind_when_backed():
    d = Design("backed")
    from dipm.sketch import XY, rect_points
    E = d.extrude("E", Profile(XY, rect_points(0.0, 0.0, 40.0, 30.0)), 5.0)
    d.extrude("B", Profile(XY.offset(-10.0), rect_points(0.0, 0.0, 20.0, 30.0)), 10.0, mode="add")
    d.hole("H1", E.cap("END"), face_point(E.cap("END"), along=(X, 0.75), across=(Y, 0.5)), plain(4.0), through(5.0))
    d.hole("H2", E.cap("END"), face_point(E.cap("END"), along=(X, 0.25), across=(Y, 0.5)), plain(4.0), through(5.0))
    with pytest.raises(InvariantError) as ei:
        d.build()
    assert ei.value.feature == "H2" and ei.value.invariant == "delta_H" and ei.value.got == 0
    # declaring it blind is the honest intent and passes
    d2 = Design("backed2")
    E = d2.extrude("E", Profile(XY, rect_points(0.0, 0.0, 40.0, 30.0)), 5.0)
    d2.hole("H", E.cap("END"), face_point(E.cap("END"), along=(X, 0.25), across=(Y, 0.5)), plain(4.0), blind(3.0))
    b = d2.build()
    assert b.ok and len(b.resolve(b.design.features[-1].floor(0))) == 1


def test_crossing_holes_need_declared_interaction():
    """Spike 01 §1.4: a through-hole crossing another adds ΔH=+2, so it must be declared."""
    d, E = block()
    d.hole("V", E.cap("END"), face_point(E.cap("END"), along=(X, 0.5), across=(Y, 0.5)), plain(6.0))
    d.hole("H", E.side("b-c"), face_point(E.side("b-c"), along=(Y, 0.5), across=(Z, 0.5)), plain(6.0))
    with pytest.raises(InteractionError, match="meets V instance 0"):
        d.build()
    d2, E2 = block()
    d2.hole("V", E2.cap("END"), face_point(E2.cap("END"), along=(X, 0.5), across=(Y, 0.5)), plain(6.0))
    d2.hole("H", E2.side("b-c"), face_point(E2.side("b-c"), along=(Y, 0.5), across=(Z, 0.5)), plain(6.0),
            expect={"dH": 2, "why": "crosses V: one tunnel system with 4 openings"})
    b = d2.build()
    ck = {c.name: c for c in b.record("H").checks.checks}
    assert ck["delta_H"].ok and ck["delta_H"].got == 2


# ---------------------------------------------------------------- compound-tool negative control (ΔS / volume)

@dataclass(frozen=True)
class OverlappingPatternCut(Feature):
    """Deliberately buggy op: two overlapping hole tools.  compound=True packs them in ONE compound
    tool (the spike-02 'silently wrong but valid' failure); compound=False passes a tool list."""
    id: str
    tags: tuple
    compound: bool
    op_name = "cut"

    def apply(self, ctx):
        tools = [BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, 15, -1), gp_Dir(0, 0, 1)), 3, 22).Shape() for x in (8, 13)]
        for k, t in enumerate(tools):
            ctx.ledger.add(Tag(self.id, "wall", str(k)), K.subshapes(t, K.KINDS["face"])[:1])
        if self.compound:
            c, bb = TopoDS_Compound(), BRep_Builder()
            bb.MakeCompound(c)
            for t in tools:
                bb.Add(c, t)
            algo = BRepAlgoAPI_Cut(ctx.shape, c)
        else:
            algo = K.boolean("cut", ctx.shape, tools)
        shape = algo.Shape()
        ctx.ledger.propagate(self.id, algo, shape)
        # declared intent: one slot through the block
        return StepOut(shape, Expect(1, 0, "-", "two overlapping bores merge into one slot", "no split"))


def test_compound_tool_caught_by_delta_s_and_volume():
    d, E = block()
    d.add(OverlappingPatternCut("P", (intent("P", "pattern"),), compound=True))
    b = d.build(on_fail="record")
    fails = {c.name for c in b.record("P").checks.failures()}
    assert "validity" not in fails and "euler" not in fails      # passes BRepCheck AND Euler...
    assert "delta_S" in fails or "volume_sign" in fails            # ...caught only by ΔS / volume
    assert "volume_sign" in fails


def test_tool_list_path_is_correct():
    d, E = block()
    d.add(OverlappingPatternCut("P", (), compound=False))
    b = d.build()
    assert b.ok and b.signature.VEFRSH[5] == 1


# ---------------------------------------------------------------- volume sign, validity, null

@dataclass(frozen=True)
class LyingCut(Feature):
    """Claims to cut but fuses: caught by the volume-sign invariant."""
    id: str
    tags: tuple
    op_name = "cut"

    def apply(self, ctx):
        tool = BRepPrimAPI_MakeBox(gp_Pnt(10, 10, 20), 5, 5, 5).Shape()
        algo = K.boolean("fuse", ctx.shape, [tool])
        ctx.ledger.propagate(self.id, algo, algo.Shape())
        return StepOut(algo.Shape(), Expect(0, 0, "-"))


@dataclass(frozen=True)
class NullResult(Feature):
    id: str
    tags: tuple
    op_name = "broken"

    def apply(self, ctx):
        from OCP.TopoDS import TopoDS_Shape
        return StepOut(TopoDS_Shape(), Expect(0, 0, "-"))


def test_volume_sign_catches_adds_declared_as_cuts():
    d, E = block()
    d.add(LyingCut("X", (intent("Q", "pocket"),)))
    with pytest.raises(InvariantError) as ei:
        d.build()
    assert ei.value.invariant == "volume_sign" and "pocket@Q" in str(ei.value)


def test_null_shape_is_caught_as_silently_invalid():
    d, E = block()
    d.add(NullResult("N", ()))
    with pytest.raises(InvariantError) as ei:
        d.build()
    assert ei.value.invariant == "validity"


def test_collapsing_shell_is_caught():
    """Spike 02 §1.3: an open-top shell at half the wall width collapses without raising."""
    d, E = block()
    d.shell("SH", [E.cap("END")], 15.0)
    b = d.build(on_fail="record")
    assert not b.ok


# ---------------------------------------------------------------- signature

def test_topology_hash_ignores_surface_and_curve_type():
    """A box and a 90° revolve of a rectangle share a face graph but not surface types."""
    from dipm.sketch import rect_points
    box = _box(10, 10, 10)
    d = Design("rev")
    d.revolve("R", Profile(XZ, rect_points(5.0, 0.0, 15.0, 10.0)), axis=((0.0, 0.0), (0.0, 1.0)), angle=90.0)
    rev = d.build().shape
    assert adjacency_hash(box, geometric=False) == adjacency_hash(rev, geometric=False)
    assert adjacency_hash(box, geometric=True) != adjacency_hash(rev, geometric=True)


def test_signature_geometry_vs_topology_hash():
    d, E = block()
    b1, b2 = d.build(), block(Lx=50.0)[0].build()
    assert b1.signature.adj_topo == b2.signature.adj_topo
    assert b1.signature.adj_geom != b2.signature.adj_geom
    assert b1.signature.roles_geom != b2.signature.roles_geom


@dataclass(frozen=True)
class FakeJoinModeOffset(Feature):
    """Stands in for a BRepOffset join-mode op (not byte-deterministic): only flips the flag."""
    id: str
    tags: tuple
    op_name = "offset(join)"

    def apply(self, ctx):
        from dipm.ops import Transform
        out = Transform(self.id, (), translate=(0.0, 0.0, 0.0)).apply(ctx)
        out.byte_deterministic = False
        return out


def test_canonical_falls_back_to_fingerprint_for_join_mode_ops():
    d, E = block()
    assert d.build().canonical()[0] == "brep"
    d.add(FakeJoinModeOffset("O", ()))
    mode, data = d.build().canonical()
    assert mode == "fingerprint" and b"VEFRSH" in data and b"roles_geom" in data


def test_invariant_error_is_readable():
    d, E = block()
    d.add(LyingCut("X", (intent("Q.1", "pocket"),)))
    try:
        d.build()
    except InvariantError as e:
        s = str(e)
        assert "feature X" in s and "pocket@Q.1" in s and "volume_sign" in s and "expected" in s
        assert e.as_dict()["feature"] == "X"
