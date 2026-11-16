"""Q1 -- Euler-Poincare on OCCT topology: counting convention + genus-delta checks."""
from __future__ import annotations

import json
import os

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder,
                             BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeTorus)
from OCP.BRep import BRep_Builder
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.collections import List_TopoDS_Shape
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

import bracket
import topo

HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ test solids

def box(x=40, y=30, z=20):
    return BRepPrimAPI_MakeBox(x, y, z).Shape()


def cyl_z(x, y, r, z0, h):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)), r, h).Shape()


def cut(a, b):
    return BRepAlgoAPI_Cut(a, b).Shape()


def fillet_all(s, r):
    mk = BRepFilletAPI_MakeFillet(s)
    for e in topo.subshapes(s, TopAbs_EDGE):
        mk.Add(r, TopoDS.Edge(e))
    return mk.Shape()


def shelled_box():
    b = box()
    top = [f for f in topo.subshapes(b, TopAbs_FACE) if abs(topo.centroid(f)[2] - 20) < 1e-9]
    faces = List_TopoDS_Shape()
    for f in top:
        faces.Append(f)
    mk = BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidByJoin(b, faces, -2.0, 1e-3)
    mk.Build()
    return mk.Shape()


def hollow_box():
    """Closed internal void -> one solid with TWO shells."""
    return cut(box(), BRepPrimAPI_MakeBox(gp_Pnt(5, 5, 5), 30, 20, 10).Shape())


def moved(s, dx, dy=0, dz=0):
    tr = gp_Trsf()
    tr.SetTranslation(gp_Vec(dx, dy, dz))
    return s.Moved(TopLoc_Location(tr))      # shares the TShape, new Location


def compound(*shapes):
    c, bb = TopoDS_Compound(), BRep_Builder()
    bb.MakeCompound(c)
    for s in shapes:
        bb.Add(c, s)
    return c


def cases():
    plate = box(50, 30, 5)
    return {
        "box": box(),
        "cylinder": BRepPrimAPI_MakeCylinder(10, 20).Shape(),
        "cone (apex)": BRepPrimAPI_MakeCone(10, 0, 20).Shape(),
        "cone frustum": BRepPrimAPI_MakeCone(10, 5, 20).Shape(),
        "sphere": BRepPrimAPI_MakeSphere(10).Shape(),
        "torus": BRepPrimAPI_MakeTorus(20, 5).Shape(),
        "box + 1 through-hole": cut(plate, cyl_z(25, 15, 4, -1, 7)),
        "box + 2 through-holes": cut(cut(plate, cyl_z(15, 15, 4, -1, 7)), cyl_z(35, 15, 4, -1, 7)),
        "box + blind hole": cut(plate, cyl_z(25, 15, 4, 2, 4)),
        "filleted box (all 12 edges)": fillet_all(box(), 2.0),
        "shelled box (top removed)": shelled_box(),
        "hollow box (internal void)": hollow_box(),
        "sphere with through-hole": cut(BRepPrimAPI_MakeSphere(10).Shape(), cyl_z(0, 0, 3, -20, 40)),
        "shelf bracket (default)": bracket.build_bracket().shape,
    }


EXPECTED_H = {"torus": 1, "box + 1 through-hole": 1, "box + 2 through-holes": 2,
              "sphere with through-hole": 1, "shelf bracket (default)": 4}
EXPECTED_S = {"hollow box (internal void)": 2}


# ------------------------------------------------------------------ conventions

def counts_with(shape, mode: str):
    """V,E,F under a de-duplication convention.  R and S always via the standard map."""
    if mode == "recommended":
        c = topo.euler_counts(shape)
        return c.V, c.E, c.F
    if mode == "include_degenerated":
        c = topo.euler_counts(shape, exclude_degenerated=False)
        return c.V, c.E, c.F
    if mode == "orientation_sensitive":
        f = topo.count_orientation_sensitive
    elif mode == "tshape_only":
        f = topo.count_by_tshape
    elif mode == "raw_explorer":
        f = topo.raw_occurrences
    else:
        raise ValueError(mode)
    n_deg = len([e for e in topo.subshapes(shape, TopAbs_EDGE) if topo.is_degenerated(e)])
    return f(shape, TopAbs_VERTEX), f(shape, TopAbs_EDGE) - n_deg, f(shape, TopAbs_FACE)


MODES = ["recommended", "include_degenerated", "orientation_sensitive", "tshape_only", "raw_explorer"]


def h_under(shape, mode):
    V, E, F = counts_with(shape, mode)
    c = topo.euler_counts(shape)
    return c.S - (V - E + F - c.R) / 2


# ------------------------------------------------------------------ genus deltas

def delta_cases():
    plate = box(50, 30, 5)
    block = box(30, 30, 30)
    after_one = cut(block, cyl_z(15, 15, 4, -1, 32))
    x_hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(-1, 15, 15), gp_Dir(1, 0, 0)), 4, 32).Shape()
    y_hole_offset = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(5, -1, 5), gp_Dir(0, 1, 0)), 3, 32).Shape()
    two = BRepAlgoAPI_Fuse(cyl_z(15, 15, 4, -1, 7), cyl_z(35, 15, 4, -1, 7)).Shape()
    rows = [
        ("through-hole in plate", plate, cut(plate, cyl_z(25, 15, 4, -1, 7)), +1),
        ("blind hole (depth 3 of 5)", plate, cut(plate, cyl_z(25, 15, 4, 2, 4)), 0),
        ("'blind' pocket too deep (6 > 5) -- intended blind", plate, cut(plate, cyl_z(25, 15, 4, -1, 7)), 0),
        ("2 through-holes, one feature", plate, cut(plate, two), +2),
        ("countersink on an existing hole", cut(plate, cyl_z(25, 15, 2, -1, 7)),
         cut(cut(plate, cyl_z(25, 15, 2, -1, 7)),
             BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(25, 15, 6), gp_Dir(0, 0, -1)), 5, 0, 5).Shape()), 0),
        ("2nd through-hole CROSSING the 1st (naive +1)", after_one, cut(after_one, x_hole), +1),
        ("2nd through-hole NOT crossing the 1st", after_one, cut(after_one, y_hole_offset), +1),
        ("fillet all edges of holed plate", cut(plate, cyl_z(25, 15, 4, -1, 7)),
         fillet_all(cut(plate, cyl_z(25, 15, 4, -1, 7)), 0.5), 0),
    ]
    out = []
    for name, before, after, exp in rows:
        ok, dh = topo.check_delta_h(before, after, exp)
        out.append({"feature": name, "expected_dH": exp, "measured_dH": dh, "pass": ok})
    # split into two parts: count solids, not shells
    slab = box(50, 30, 5)
    split = cut(slab, BRepPrimAPI_MakeBox(gp_Pnt(24, -1, -1), 2, 32, 7).Shape())
    ns0, ns1 = len(topo.subshapes(slab, TopAbs_SOLID)), len(topo.subshapes(split, TopAbs_SOLID))
    out.append({"feature": "slot that splits the plate in two", "expected_dH": 0,
                "measured_dH": topo.genus(split) - topo.genus(slab), "pass": topo.genus(split) == 0,
                "note": f"solids {ns0}->{ns1}, shells {topo.euler_counts(slab).S}->{topo.euler_counts(split).S}"})
    return out


def shared_tshape_demo():
    """Two placed copies of one box TShape in a compound (what a pattern of instances gives)."""
    b = box(10, 10, 10)
    c = compound(b, moved(b, 20))
    rows = []
    for mode in MODES:
        V, E, F = counts_with(c, mode)
        S = len(topo.subshapes(c, TopAbs_SHELL))
        rows.append({"mode": mode, "V": V, "E": E, "F": F, "S": S, "H": S - (V - E + F) / 2})
    # does a boolean with patterned (shared-TShape) tools leave shared TShapes behind?
    tool = cyl_z(10, 15, 3, -1, 7)
    patterned = compound(tool, moved(tool, 30))
    res = cut(box(50, 30, 5), patterned)
    faces_map = len(topo.subshapes(res, TopAbs_FACE))
    faces_tshape = topo.count_by_tshape(res, TopAbs_FACE)
    return rows, {"faces_by_map": faces_map, "faces_by_tshape": faces_tshape,
                  "H": topo.euler_counts(res).H}


def main():
    rows = []
    for name, s in cases().items():
        c = topo.euler_counts(s)
        row = {"case": name, "V": c.V, "E": c.E, "F": c.F, "R": c.R, "S": c.S, "H": c.H,
               "E_all": c.E_all, "E_degen": c.E_degen, "E_seam": c.E_seam,
               "valid": topo.is_valid(s), "expected_H": EXPECTED_H.get(name, 0),
               "expected_S": EXPECTED_S.get(name, 1)}
        row["pass"] = c.ok and c.H == row["expected_H"] and c.S == row["expected_S"]
        row["H_by_mode"] = {m: h_under(s, m) for m in MODES}
        rows.append(row)
    deltas = delta_cases()
    shared_rows, shared_bool = shared_tshape_demo()
    result = {"cases": rows, "deltas": deltas, "shared_tshape_compound": shared_rows,
              "shared_tshape_boolean": shared_bool}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "q1.json"), "w") as fh:
        json.dump(result, fh, indent=1)

    print("\n## Q1 raw counts (recommended convention)")
    print("| case | V | E | F | R | S | H | E incl. degen | degen | seam | valid | pass |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['case']} | {r['V']} | {r['E']} | {r['F']} | {r['R']} | {r['S']} | {r['H']:g} | "
              f"{r['E_all']} | {r['E_degen']} | {r['E_seam']} | {r['valid']} | {'PASS' if r['pass'] else 'FAIL'} |")
    print("\n## Q1 solved H under alternative conventions")
    print("| case | " + " | ".join(MODES) + " |")
    print("|---" * (len(MODES) + 1) + "|")
    for r in rows:
        print(f"| {r['case']} | " + " | ".join(f"{r['H_by_mode'][m]:g}" for m in MODES) + " |")
    print("\n## Q1 genus deltas")
    for d in deltas:
        print(f"| {d['feature']} | {d['expected_dH']:+d} | {d['measured_dH']:+d} | "
              f"{'PASS' if d['pass'] else 'FAIL'} | {d.get('note', '')} |")
    print("\n## Q1 shared TShape compound (box + moved copy)")
    for r in shared_rows:
        print(r)
    print("boolean with patterned tool:", shared_bool)
    return result


if __name__ == "__main__":
    main()
