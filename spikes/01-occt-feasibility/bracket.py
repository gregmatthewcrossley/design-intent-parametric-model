"""Parametric shelf bracket (approximation of docs/architecture.md §8.5), built on raw OCP.

Axes: X = across the bracket width (extrude direction, symmetric about X=0),
      Y = out from the wall (wall face at Y=0), Z = up.
The L-profile lives in the YZ plane: a vertical leg against the wall and a
horizontal arm at the top that carries the shelf.

Each feature records the tags of the faces/edges it creates in a refs.Ledger
and checks its expected genus delta (Euler-Poincare) as it goes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from OCP.BOPAlgo import BOPAlgo_Options
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakeVertex, BRepBuilderAPI_MakeWire)
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder,
                             BRepPrimAPI_MakePrism)
from OCP.TopTools import TopTools_ShapeMapHasher  # noqa: F401  (documents hasher used)
from OCP.collections import List_TopoDS_Shape
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

import topo
from refs import Ledger, Tag, exactly, one


@dataclass
class Params:
    shelf_depth: float = 200.0
    t: float = 5.0
    screw_clear_d: float = 4.5     # #8 clearance
    countersink_d: float = 9.0     # 90 deg countersink, 2x clearance
    cable_d: float = 8.0
    tool_access_r: float = 15.0    # Ø30 screwdriver access cylinder (R.c4)
    gusset_frac: float = 0.4
    shelf_hole_u: float = 0.75     # shelf screw position along the arm (fraction of arm)
    parallel: bool = False         # OCCT parallel boolean mode

    @property
    def leg(self): return 0.75 * self.shelf_depth

    @property
    def arm(self): return 0.8 * self.shelf_depth

    @property
    def width(self): return 6 * self.t

    @property
    def gusset(self): return self.gusset_frac * self.shelf_depth


@dataclass
class Build:
    shape: object
    ledger: Ledger
    log: list = field(default_factory=list)   # per-feature: id, H before/after, expected dH, ok


# ---------------------------------------------------------------- helpers

def _boolean(kind, a, b, parallel):
    op = BRepAlgoAPI_Fuse() if kind == "fuse" else BRepAlgoAPI_Cut()
    args, tools = List_TopoDS_Shape(), List_TopoDS_Shape()
    args.Append(a)
    tools.Append(b)
    op.SetArguments(args)
    op.SetTools(tools)
    op.SetRunParallel(parallel)
    op.Build()
    if not op.IsDone():
        raise RuntimeError(f"boolean {kind} failed")
    return op


def named_profile_yz(x: float, pts: dict, loop: list[str]):
    """Planar polygon in the plane X=x.  pts: name->(y,z); loop: vertex names in order.

    Returns (face, {edge_name: edge}, {vertex_name: vertex}).  Edge i is named
    '<loop[i]>-<loop[i+1]>'.
    """
    verts = {n: BRepBuilderAPI_MakeVertex(gp_Pnt(x, *pts[n])).Vertex() for n in loop}
    edges, mw = {}, BRepBuilderAPI_MakeWire()
    for a, b in zip(loop, loop[1:] + loop[:1]):
        e = BRepBuilderAPI_MakeEdge(verts[a], verts[b]).Edge()
        edges[f"{a}-{b}"] = e
        mw.Add(e)
    face = BRepBuilderAPI_MakeFace(mw.Wire(), True).Face()
    return face, edges, verts


def extrude_x(fid: str, profile, edges: dict, verts: dict, length: float, ledger: Ledger):
    """Extrude along +X and tag caps/sides/lateral edges structurally."""
    mk = BRepPrimAPI_MakePrism(profile, gp_Vec(length, 0, 0))
    mk.Build()
    ledger.add(Tag(fid, "cap", "START"), [mk.FirstShape()])
    ledger.add(Tag(fid, "cap", "END"), [mk.LastShape()])
    for name, e in edges.items():
        ledger.add(Tag(fid, "side", name), topo.occ_list(mk.Generated(e)))
    for name, v in verts.items():
        ledger.add(Tag(fid, "lateral_edge", name), topo.occ_list(mk.Generated(v)))
    return mk.Shape()


def _step(build: Build, fid: str, new_shape, expected_dh: int, algo=None):
    h0 = topo.genus(build.shape) if build.shape is not None else 0
    if algo is not None:
        build.ledger.propagate(fid, algo, new_shape)
    h1 = topo.genus(new_shape)
    build.log.append({"feature": fid, "H_before": h0, "H_after": h1,
                      "expected_dH": expected_dh, "ok": (h1 - h0) == expected_dh,
                      "valid": topo.is_valid(new_shape)})
    build.shape = new_shape


def _cut_tool(build, fid, tool_maker, role, expected_dh, parallel):
    tool_maker.Build()
    tool = tool_maker.Shape()
    lateral = tool_maker.Cylinder().LateralFace() if hasattr(tool_maker, "Cylinder") \
        else tool_maker.Cone().LateralFace()
    build.ledger.add(Tag(fid, role), [lateral])
    op = _boolean("cut", build.shape, tool, parallel)
    _step(build, fid, op.Shape(), expected_dh, op)


# ---------------------------------------------------------------- the bracket

def wall_hole_z(p: Params):
    """Layout for the wall screw pattern (A.P) and cable hole (A.3)."""
    gusset_bottom = p.leg - p.t - p.gusset
    z_lo = 2 * p.screw_clear_d                    # edge distance >= 2x diameter
    z_hi = gusset_bottom - p.tool_access_r        # below gusset footprint (R.c4)
    assert z_hi - z_lo > p.cable_d + p.countersink_d, "no room for the pattern"
    return z_lo, z_hi, 0.5 * (z_lo + z_hi)


def build_bracket(p: Params = Params(), stop_after: str | None = None) -> Build:
    BOPAlgo_Options.SetParallelMode_s(p.parallel)
    t, leg, arm, w, g = p.t, p.leg, p.arm, p.width, p.gusset
    b = Build(None, Ledger())

    # --- R skeleton: L profile, symmetric extrude (E)
    pts = {"wall_bot": (0, 0), "leg_bot": (t, 0), "inner": (t, leg - t),
           "arm_under_tip": (arm, leg - t), "arm_top_tip": (arm, leg), "wall_top": (0, leg)}
    loop = list(pts)
    prof, edges, verts = named_profile_yz(-w / 2, pts, loop)
    # human-meaningful names for the sketch edges
    alias = {"wall_bot-leg_bot": "leg_end", "leg_bot-inner": "mount",
             "inner-arm_under_tip": "arm_under", "arm_under_tip-arm_top_tip": "arm_tip",
             "arm_top_tip-wall_top": "shelf", "wall_top-wall_bot": "wall"}
    edges = {alias[k]: v for k, v in edges.items()}
    body = extrude_x("E", prof, edges, verts, w, b.ledger)
    _step(b, "E", body, 0)
    if stop_after == "E":
        return b

    # --- C gusset on the mid-plane at the inner corner (G)
    gpts = {"corner": (t, leg - t), "down": (t, leg - t - g), "out": (t + g, leg - t)}
    gprof, gedges, gverts = named_profile_yz(-t / 2, gpts, list(gpts))
    gedges = {{"corner-down": "on_mount", "down-out": "hypotenuse",
               "out-corner": "on_arm"}[k]: v for k, v in gedges.items()}
    gusset = extrude_x("G", gprof, gedges, gverts, t, b.ledger)
    op = _boolean("fuse", b.shape, gusset, p.parallel)
    _step(b, "G", op.Shape(), 0, op)
    if stop_after == "G":
        return b

    # --- A.P wall screw pattern (W1, W2) with countersinks (K1, K2), A.3 cable hole (C)
    z_lo, z_hi, z_mid = wall_hole_z(p)
    rc, rk = p.screw_clear_d / 2, p.countersink_d / 2
    for i, z in ((1, z_lo), (2, z_hi)):
        cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, -1, z), gp_Dir(0, 1, 0)), rc, t + 2)
        _cut_tool(b, f"W{i}", cyl, "wall", +1, p.parallel)
        cone = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, t + 1, z), gp_Dir(0, -1, 0)), rk + 1, 0, rk + 1)
        _cut_tool(b, f"K{i}", cone, "countersink", 0, p.parallel)
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, -1, z_mid), gp_Dir(0, 1, 0)), p.cable_d / 2, t + 2)
    _cut_tool(b, "C", cyl, "wall", +1, p.parallel)

    # --- B.1 shelf screw (S) through the arm, toward the front, centred across width
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, p.shelf_hole_u * arm, leg - t - 1), gp_Dir(0, 0, 1)), rc, t + 2)
    _cut_tool(b, "S", cyl, "wall", +1, p.parallel)
    if stop_after == "S":
        return b

    # --- R.c2 inner-corner fillet (F): the corner edge was split in two by the gusset
    corner_edges = b.ledger.resolve("E", "lateral_edge", "inner", exactly(2))
    mk = BRepFilletAPI_MakeFillet(b.shape)
    for e in corner_edges:
        mk.Add(t, TopoDS.Edge(e))
    mk.Build()
    if not mk.IsDone():
        raise RuntimeError("fillet failed")
    for e in corner_edges:
        b.ledger.add(Tag("F", "blend", "E.lateral_edge(inner)"), topo.occ_list(mk.Generated(e)))
    _step(b, "F", mk.Shape(), 0, mk)
    return b


# References the DSL would write, with declared cardinality.  Used by Q2.
FINAL_REFERENCES = [
    # (feature, role, source, cardinality)
    ("E", "cap", "START", one()),
    ("E", "cap", "END", one()),
    ("E", "side", "wall", one()),
    ("E", "side", "mount", one()),
    ("E", "side", "shelf", one()),
    ("E", "side", "arm_under", one()),
    ("E", "side", "arm_tip", one()),
    ("E", "side", "leg_end", one()),
    ("G", "side", "hypotenuse", one()),
    ("G", "cap", "START", one()),
    ("G", "cap", "END", one()),
    ("W1", "wall", None, one()),
    ("W2", "wall", None, one()),
    ("K1", "countersink", None, one()),
    ("K2", "countersink", None, one()),
    ("C", "wall", None, one()),
    ("S", "wall", None, one()),
    ("F", "blend", "E.lateral_edge(inner)", exactly(2)),
]
