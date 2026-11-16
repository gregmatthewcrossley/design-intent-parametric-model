"""Q2 -- does OCCT history support structural references, and are they edit-stable?"""
from __future__ import annotations

import itertools
import json
import os

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

import bracket
import topo
from refs import CardinalityError

HERE = os.path.dirname(os.path.abspath(__file__))


def r(x, nd=3):
    v = round(x, nd)
    return 0.0 if v == 0 else v


def in_solid(face, solid):
    """The face as it is oriented inside the solid (ledger/history copies may carry
    an arbitrary orientation; the solid's shell carries the outward one)."""
    for f in topo.subshapes(solid, TopAbs_FACE):
        if f.IsSame(face):
            return f
    raise KeyError("face not in solid")


def face_descriptor(face, solid) -> str:
    """Surface type + outward normal (planes) or axis (cylinders/cones)."""
    f = TopoDS.Face(in_solid(face, solid))
    st = topo.surface_type(f)
    if st == "Plane":
        pl = BRepAdaptor_Surface(f).Plane()
        d = pl.Axis().Direction()
        sgn = -1 if f.Orientation() == TopAbs_REVERSED else 1
        n = gp_Vec(d.X() * sgn, d.Y() * sgn, d.Z() * sgn)
        return f"Plane n=({r(n.X())},{r(n.Y())},{r(n.Z())})"
    s = BRepAdaptor_Surface(f)
    ax = (s.Cylinder() if st == "Cylinder" else s.Cone()).Axis().Direction()
    d = [r(ax.X()), r(ax.Y()), r(ax.Z())]
    if [x for x in d if x][0] < 0:                    # sign-normalise axis
        d = [-x if x else 0.0 for x in d]
    return f"{st} axis=({d[0]},{d[1]},{d[2]})"


# ------------------------------------------------------------- A. API capability probes

def capability_probes() -> list[dict]:
    rows = []
    # prism roles
    from bracket import named_profile_yz
    prof, edges, verts = named_profile_yz(0, {"a": (0, 0), "b": (10, 0), "c": (10, 5), "d": (0, 5)}, list("abcd"))
    mk = BRepPrimAPI_MakePrism(prof, gp_Vec(20, 0, 0))
    mk.Build()
    rows.append({"api": "MakePrism.FirstShape/LastShape", "role": "E.cap(START|END)",
                 "result": f"{topo.surface_type(mk.FirstShape())}/{topo.surface_type(mk.LastShape())}",
                 "ok": mk.FirstShape().ShapeType() == TopAbs_FACE and mk.LastShape().ShapeType() == TopAbs_FACE})
    gen = {k: len(list(mk.Generated(e))) for k, e in edges.items()}
    rows.append({"api": "MakePrism.Generated(sketch edge)", "role": "E.side(from=edge)",
                 "result": f"faces per edge {sorted(set(gen.values()))}", "ok": set(gen.values()) == {1}})
    genv = {k: [s.ShapeType() for s in mk.Generated(v)] for k, v in verts.items()}
    rows.append({"api": "MakePrism.Generated(sketch vertex)", "role": "E.lateral_edge(from=vertex)",
                 "result": "1 edge per vertex" if all(g == [TopAbs_EDGE] for g in genv.values()) else str(genv),
                 "ok": all(g == [TopAbs_EDGE] for g in genv.values())})

    # boolean: Modified / Generated / IsDeleted
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    cm = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(5, 5, -1), gp_Dir(0, 0, 1)), 2, 12)
    cm.Build()
    op = BRepAlgoAPI_Cut(box, cm.Shape())
    lat, top = cm.Cylinder().LateralFace(), cm.Cylinder().TopFace()
    mods = list(op.Modified(lat))
    rows.append({"api": "BRepAlgoAPI_Cut.Modified(tool face)", "role": "H.wall",
                 "result": f"{len(mods)} face(s), {topo.surface_type(mods[0])}", "ok": len(mods) == 1})
    rows.append({"api": "BRepAlgoAPI_Cut.IsDeleted(tool cap)", "role": "(tool caps vanish)",
                 "result": str(bool(op.IsDeleted(top))), "ok": bool(op.IsDeleted(top))})
    gens = [s for s in op.Generated(lat) if s.ShapeType() == TopAbs_EDGE]
    rows.append({"api": "BRepAlgoAPI_Cut.Generated(face)", "role": "H.rim(on=face X) section edges",
                 "result": f"{len(gens)} edges ({', '.join(topo.curve_type(e) for e in gens)}) + vertices",
                 "ok": len(gens) == 2})

    # fillet
    fb = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    es = topo.subshapes(fb, TopAbs_EDGE)
    fm = BRepFilletAPI_MakeFillet(fb)
    fm.Add(1.0, TopoDS.Edge(es[0]))
    fm.Build()
    g = list(fm.Generated(es[0]))
    rows.append({"api": "BRepFilletAPI_MakeFillet.Generated(edge)", "role": "F.blend(from=edge) / F.created()",
                 "result": f"{len(g)} {topo.surface_type(g[0]) if g else ''}", "ok": len(g) == 1})
    untouched = es[-1]
    still_there = any(untouched.IsSame(x) for x in topo.subshapes(fm.Shape(), TopAbs_EDGE))
    rows.append({"api": "BRepFilletAPI_MakeFillet.IsDeleted(untouched edge)", "role": "(ledger propagation)",
                 "result": f"IsDeleted={bool(fm.IsDeleted(untouched))} but edge present={still_there}",
                 "ok": bool(fm.IsDeleted(untouched)) == (not still_there)})
    return rows


def build123d_probe() -> list[dict]:
    """What build123d's own history surface (0.13: ShapeHistory, Select.LAST/NEW) offers."""
    from build123d import Axis, Box, BuildPart, BuildSketch, Circle, Hole, Select, extrude, fillet
    out = []
    with BuildPart() as p:
        Box(40, 30, 10)
        with BuildSketch(p.faces().sort_by(Axis.Z)[-1]):
            Circle(5)
        extrude(amount=8)
        out.append({"op": "extrude boss", "faces(LAST)": len(p.faces(Select.LAST)),
                    "faces(NEW)": len(p.faces(Select.NEW)), "note": "cap and side not distinguished"})
        Hole(2)
        out.append({"op": "Hole", "faces(LAST)": len(p.faces(Select.LAST)),
                    "faces(NEW)": len(p.faces(Select.NEW)), "note": "hole wall = LAST"})
        fillet(p.edges().filter_by(Axis.Z), 1)
        out.append({"op": "fillet 4 vertical edges", "faces(LAST)": len(p.faces(Select.LAST)),
                    "faces(NEW)": len(p.faces(Select.NEW)), "note": "blend faces = NEW (no per-edge source)"})
    return out


# ------------------------------------------------------------- C. edit-stability sweep

def resolve_all(b) -> dict:
    out = {}
    for f, role, src, card in bracket.FINAL_REFERENCES:
        key = f"{f}.{role}({src})" if src else f"{f}.{role}"
        try:
            shapes = b.ledger.resolve(f, role, src, card)
            out[key] = {"n": len(shapes), "ok": True,
                        "tag_gen": [f, role, src],
                        "events": [list(map(list, g)) for g in b.ledger.genealogy(f, role, src)],
                        "geom": sorted(face_descriptor(s, b.shape) for s in shapes)}
        except CardinalityError as e:
            out[key] = {"n": None, "ok": False, "error": str(e)}
    return out


SWEEP_DEPTH = [150, 175, 200, 250, 300]
SWEEP_T = [4, 5, 6, 8]


def edit_stability():
    base = resolve_all(bracket.build_bracket(bracket.Params()))
    rows = []
    for d, t in itertools.product(SWEEP_DEPTH, SWEEP_T):
        try:
            b = bracket.build_bracket(bracket.Params(shelf_depth=d, t=t))
        except Exception as e:  # noqa: BLE001
            rows.append({"shelf_depth": d, "t": t, "build": f"FAIL {e}"})
            continue
        res = resolve_all(b)
        card_ok = all(v["ok"] and v["n"] == base[k]["n"] for k, v in res.items())
        geom_ok = all(v.get("geom") == base[k]["geom"] for k, v in res.items())
        ev_diff = [k for k, v in res.items() if v.get("events") != base[k]["events"]]
        dh_ok = all(l["ok"] for l in b.log)
        valid = all(l["valid"] for l in b.log)
        rows.append({"shelf_depth": d, "t": t, "build": "ok", "cardinality_ok": card_ok,
                     "geom_descriptor_ok": geom_ok, "dH_ok": dh_ok, "valid": valid,
                     "VEFRSH": topo.euler_counts(b.shape).tuple6(),
                     "adj_topo": topo.adjacency_hash(b.shape, geometric=False)[:12],
                     "event_genealogy_changed": ev_diff,
                     "event_detail": {k: res[k]["events"] for k in ev_diff}})
    # negative controls: edits that genuinely change topology must be caught
    controls = []
    for label, prm in [("shelf_hole_u 0.75->0.4 (shelf hole now lands on the gusset)",
                        bracket.Params(shelf_hole_u=0.4)),
                       ("t=4, countersink_d 9->14 (countersink swallows the screw bore)",
                        bracket.Params(t=4, countersink_d=14)),
                       ("shelf_depth 120 (no room for wall pattern)", bracket.Params(shelf_depth=120))]:
        try:
            b = bracket.build_bracket(prm)
            res = resolve_all(b)
            controls.append({"edit": label, "build": "ok",
                             "dH_failures": [l for l in b.log if not l["ok"]],
                             "cardinality_failures": [v["error"] for v in res.values() if not v["ok"]],
                             "geom_changed": [k for k, v in res.items() if v.get("geom") != base[k]["geom"]]})
        except Exception as e:  # noqa: BLE001
            controls.append({"edit": label, "build": f"refused: {type(e).__name__}: {e}"})
    return base, rows, controls


# ------------------------------------------------------------- D. split ordering

def split_order_probe():
    """Cut grooves across a plate's top face so it splits; record the order in which
    Modified() returns the fragments (by fragment centroid X)."""
    rows = []
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Trsf
    cases = [(0, [5]), (0, [30]), (0, [45]), (0, [12, 30]), (0, [30, 12]), (0, [8, 25, 40]),
             (0, [40, 8, 25]), (90, [12, 30]), (180, [12, 30]), (180, [8, 25, 40]), (270, [8, 25, 40])]
    for rot, xs in cases:
        tr = gp_Trsf()
        tr.SetRotation(gp_Ax1(gp_Pnt(25, 10, 0), gp_Dir(0, 0, 1)), rot * 3.141592653589793 / 180)
        place = lambda s: BRepBuilderAPI_Transform(s, tr, True).Shape()
        plate = place(BRepPrimAPI_MakeBox(50, 20, 5).Shape())
        top = [f for f in topo.subshapes(plate, TopAbs_FACE) if abs(topo.centroid(f)[2] - 5) < 1e-9][0]
        tool = None
        for x in xs:
            g = place(BRepPrimAPI_MakeBox(gp_Pnt(x, -1, 4), 2, 22, 2).Shape())
            tool = g if tool is None else BRepAlgoAPI_Fuse(tool, g).Shape()
        op = BRepAlgoAPI_Cut(plate, tool)
        frags = list(op.Modified(top))
        # express fragment centroids in the plate's own (unrotated) frame
        inv = tr.Inverted()
        cx = []
        for f in frags:
            c = gp_Pnt(*topo.centroid(f)).Transformed(inv)
            cx.append(round(c.X(), 2))
        rows.append({"plate_rotation_deg": rot, "grooves_at_local_x": xs, "fragments": len(frags),
                     "Modified_order_local_x": cx, "ascending_local_x": cx == sorted(cx)})
    # identical plate, sketch polygon started at a different vertex / opposite winding
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    for winding in ("ccw", "cw"):
        for start in range(4):
            pts = [(0, 0), (50, 0), (50, 20), (0, 20)]
            if winding == "cw":
                pts = pts[::-1]
            pts = pts[start:] + pts[:start]
            mp = BRepBuilderAPI_MakePolygon()
            for x, y in pts:
                mp.Add(gp_Pnt(x, y, 0))
            mp.Close()
            prism = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(mp.Wire(), True).Face(), gp_Vec(0, 0, 5))
            prism.Build()
            top = prism.LastShape()
            tool = None
            for x in (8, 25, 40):
                g = BRepPrimAPI_MakeBox(gp_Pnt(x, -1, 4), 2, 22, 2).Shape()
                tool = g if tool is None else BRepAlgoAPI_Fuse(tool, g).Shape()
            op = BRepAlgoAPI_Cut(prism.Shape(), tool)
            cx = [round(topo.centroid(f)[0], 2) for f in op.Modified(top)]
            rows.append({"sketch_winding": winding, "sketch_start_vertex": start, "grooves_at_local_x": [8, 25, 40],
                         "fragments": len(cx), "Modified_order_local_x": cx, "ascending_local_x": cx == sorted(cx)})
    # the same question on the bracket: order of the two corner-edge fragments after G
    edge_rows = []
    for d, t in itertools.product(SWEEP_DEPTH, SWEEP_T):
        b = bracket.build_bracket(bracket.Params(shelf_depth=d, t=t), stop_after="G")
        es = b.ledger.resolve("E", "lateral_edge", "inner", ("exactly", 2))
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        xs = []
        for e in es:
            pr = GProp_GProps()
            BRepGProp.LinearProperties_s(e, pr)
            xs.append(round(pr.CentreOfMass().X(), 2))
        edge_rows.append({"shelf_depth": d, "t": t, "fragment_x_in_ledger_order": xs})
    return rows, edge_rows


def code_size():
    def n(path, start=None, end=None):
        lines = open(os.path.join(HERE, path)).read().splitlines()
        return sum(1 for l in lines if l.strip() and not l.strip().startswith("#"))
    return {"refs.py (ledger + resolve + cardinality)": n("refs.py"),
            "bracket.py (whole model incl. tagging)": n("bracket.py")}


def main():
    probes = capability_probes()
    b123 = build123d_probe()
    base, sweep, controls = edit_stability()
    splits, edge_order = split_order_probe()
    b = bracket.build_bracket()
    result = {"capability_probes": probes, "build123d_probe": b123,
              "baseline_refs": base, "sweep": sweep, "negative_controls": controls, "split_order": splits,
              "corner_edge_split_order": edge_order, "code_size": code_size(),
              "isdeleted_disagreements_default_build": b.ledger.isdeleted_disagreements}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "q2.json"), "w") as fh:
        json.dump(result, fh, indent=1, default=str)

    print("\n## Q2 capability probes")
    for p in probes:
        print(f"| {p['api']} | {p['role']} | {p['result']} | {'PASS' if p['ok'] else 'FAIL'} |")
    print("\n## Q2 build123d probe")
    for p in b123:
        print(p)
    print("\n## Q2 baseline references (shelf_depth=200, t=5)")
    for k, v in base.items():
        print(f"| {k} | {v['n']} | {v['geom']} | {v['events']} |")
    print("\n## Q2 edit-stability sweep")
    for r_ in sweep:
        print({k: v for k, v in r_.items() if k != "event_detail"})
        if r_.get("event_detail"):
            print("   events changed:", r_["event_detail"])
    print("\n## Q2 negative controls")
    for c in controls:
        print(c)
    print("\n## Q2 split ordering")
    for r_ in splits:
        print(r_)
    for r_ in edge_order:
        print(r_)
    print("\ncode size:", code_size())
    print("IsDeleted disagreements:", b.ledger.isdeleted_disagreements)
    return result


if __name__ == "__main__":
    main()
