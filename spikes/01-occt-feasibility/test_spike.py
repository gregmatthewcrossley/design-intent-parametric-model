"""Regression tests pinning the spike's findings.  Run: ../../.venv/bin/python -m pytest -q"""
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeSphere

import bracket
import q1_euler as q1
import topo
from refs import CardinalityError


# ---- Q1: counting convention

@pytest.mark.parametrize("name", list(q1.cases()))
def test_recommended_convention_holds(name):
    s = q1.cases()[name]
    c = topo.euler_counts(s)
    assert c.ok, c
    assert c.H == q1.EXPECTED_H.get(name, 0)
    assert c.S == q1.EXPECTED_S.get(name, 1)


def test_degenerated_edges_must_be_excluded():
    assert q1.h_under(BRepPrimAPI_MakeSphere(10).Shape(), "include_degenerated") == 1   # wrong genus
    assert q1.h_under(BRepPrimAPI_MakeCone(10, 0, 20).Shape(), "include_degenerated") == 0.5  # non-integer
    assert q1.h_under(q1.fillet_all(q1.box(), 2.0), "include_degenerated") == 4    # fillet corner patches


def test_dedup_must_use_tshape_plus_location():
    # MakePrism's END cap shares the START cap's TShape (different Location)
    assert q1.h_under(bracket.build_bracket().shape, "tshape_only") != 4
    assert q1.h_under(q1.box(), "orientation_sensitive") != 0


def test_genus_deltas():
    rows = {r["feature"]: r for r in q1.delta_cases()}
    assert rows["through-hole in plate"]["pass"]
    assert rows["blind hole (depth 3 of 5)"]["pass"]
    assert not rows["'blind' pocket too deep (6 > 5) -- intended blind"]["pass"]   # caught
    assert rows["2nd through-hole CROSSING the 1st (naive +1)"]["measured_dH"] == 2  # naive rule wrong


# ---- Q2: references

@pytest.mark.parametrize("d,t", [(150, 4), (200, 5), (300, 8)])
def test_bracket_references_resolve(d, t):
    b = bracket.build_bracket(bracket.Params(shelf_depth=d, t=t))
    for f, role, src, card in bracket.FINAL_REFERENCES:
        b.ledger.resolve(f, role, src, card)
    assert all(l["ok"] for l in b.log)


def test_fillet_isdeleted_is_unreliable():
    b = bracket.build_bracket()
    assert any(op == "F" and not ours and kernel for _, op, ours, kernel in b.ledger.isdeleted_disagreements)


def test_negative_control_countersink_swallows_bore():
    b = bracket.build_bracket(bracket.Params(t=4, countersink_d=14))
    with pytest.raises(CardinalityError):
        b.ledger.resolve("W1", "wall", None, ("exactly", 1))


def test_negative_control_blind_shelf_hole_caught_by_dH_only():
    b = bracket.build_bracket(bracket.Params(shelf_hole_u=0.4))
    s_step = [l for l in b.log if l["feature"] == "S"][0]
    assert not s_step["ok"]
    b.ledger.resolve("S", "wall", None, ("exactly", 1))   # the reference alone does NOT notice


def test_split_order_depends_on_sketch_start_vertex():
    import q2_history as q2
    rows, _ = q2.split_order_probe()
    starts = [r for r in rows if "sketch_start_vertex" in r]
    assert {r["ascending_local_x"] for r in starts} == {True, False}


# ---- Q3: determinism (quick in-process check; full run in q3_determinism.py)

def test_rebuild_is_byte_identical():
    a = bracket.build_bracket().shape
    b = bracket.build_bracket().shape
    assert topo.brep_bytes(a) == topo.brep_bytes(b)
    assert topo.canonical_step(topo.step_bytes(a, False)) == topo.canonical_step(topo.step_bytes(b, False))
    assert topo.step_bytes(a) != topo.step_bytes(b)   # per-process translator counter in PRODUCT name
    assert topo.signature(a) == topo.signature(b)
