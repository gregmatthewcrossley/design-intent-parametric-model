"""Shared helpers for spike 02.

Spike 01's `topo.py` (counting, Euler, signatures, serialization) and `refs.py`
(reference ledger) are imported, not copied: this module puts
../01-occt-feasibility on sys.path.  Everything here is spike-02-specific glue:
named sketch profiles, a result-presence map, a history *audit* that checks what
an OCCT maker reports against the result shape, and geometric descriptors.
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE01 = os.path.normpath(os.path.join(HERE, "..", "01-occt-feasibility"))
if SPIKE01 not in sys.path:
    # APPEND, not insert: spike 01 also has a q3_determinism.py; local modules must win name clashes.
    sys.path.append(SPIKE01)

import topo  # noqa: E402  (spike 01)
import refs  # noqa: E402,F401  (spike 01)

from OCP.BRep import BRep_Tool  # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_Surface  # noqa: E402
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,  # noqa: E402
                                BRepBuilderAPI_MakeVertex, BRepBuilderAPI_MakeWire)
from OCP.BRepLProp import BRepLProp_SLProps  # noqa: E402
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone  # noqa: E402
from OCP.TopAbs import (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_SOLID, TopAbs_SHELL,  # noqa: E402
                        TopAbs_REVERSED)
from OCP.TopExp import TopExp  # noqa: E402
from OCP.TopoDS import TopoDS  # noqa: E402
from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402

KIND_NAME = {TopAbs_FACE: "face", TopAbs_EDGE: "edge", TopAbs_VERTEX: "vertex", TopAbs_SOLID: "solid"}


# ---------------------------------------------------------------- sketch helpers

def named_polygon(pts: dict, loop: list[str] | None = None, closed: bool = True, make_face: bool = True):
    """Polygon through named 3D points.  Edge i is named '<a>-<b>'.

    Returns (face_or_wire, {edge_name: edge}, {vertex_name: vertex}).
    """
    loop = loop or list(pts)
    verts = {n: BRepBuilderAPI_MakeVertex(gp_Pnt(*pts[n])).Vertex() for n in loop}
    pairs = list(zip(loop, loop[1:] + loop[:1])) if closed else list(zip(loop, loop[1:]))
    edges, mw = {}, BRepBuilderAPI_MakeWire()
    for a, b in pairs:
        e = BRepBuilderAPI_MakeEdge(verts[a], verts[b]).Edge()
        edges[f"{a}-{b}"] = e
        mw.Add(e)
    w = mw.Wire()
    if closed and make_face:
        return BRepBuilderAPI_MakeFace(w, True).Face(), edges, verts
    return w, edges, verts


def rename(d: dict, alias: dict) -> dict:
    return {alias.get(k, k): v for k, v in d.items()}


# ---------------------------------------------------------------- presence / audit

def present_map(result) -> ShapeMap:
    m = ShapeMap()
    for k in (TopAbs_SOLID, TopAbs_SHELL, TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
        TopExp.MapShapes_s(result, k, m)
    return m


def in_result(shape, result_map) -> bool:
    return result_map.Contains(shape)


def audit_history(algo, inputs: dict, result, kinds=(TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX)) -> dict:
    """For every sub-shape of every input, compare the maker's history claims to the result.

    inputs: {name: shape}.  For each input sub-shape s:
      * present   = s itself is in the result (IsSame);
      * modified  = Modified(s) entries, and how many are actually in the result;
      * generated = Generated(s) entries, and how many are in the result;
      * kernel_deleted = IsDeleted(s);
      * inferred_deleted = not present and no Modified image in the result.
    Returns aggregated counters plus the list of disagreements.
    """
    P = present_map(result)
    stats = {"n": 0, "isdeleted_disagree": 0, "false_deleted": 0, "consumed": 0, "missed_delete": 0, "modified_not_in_result": 0,
             "generated_not_in_result": 0, "present_and_modified": 0,
             "deleted_inferred": 0, "deleted_kernel": 0}
    examples, dangling = [], []
    seen = ShapeMap()
    for name, shp in inputs.items():
        for k in kinds:
            for s in topo.subshapes(shp, k):
                if seen.Contains(s):
                    continue
                seen.Add(s)
                stats["n"] += 1
                mods = topo.occ_list(algo.Modified(s))
                gens = topo.occ_list(algo.Generated(s))
                mods_in = [m for m in mods if P.Contains(m)]
                gens_in = [g for g in gens if P.Contains(g)]
                pres = P.Contains(s)
                kdel = bool(algo.IsDeleted(s))
                idel = (not pres) and not mods_in
                stats["modified_not_in_result"] += len(mods) - len(mods_in)
                stats["generated_not_in_result"] += len(gens) - len(gens_in)
                if len(gens) != len(gens_in) and len(dangling) < 4:
                    dangling.append({"input": name, "kind": KIND_NAME[k],
                                     "generated": [KIND_NAME.get(g.ShapeType(), str(g.ShapeType())) + ":" + describe(g)
                                                   for g in gens if not P.Contains(g)]})
                stats["present_and_modified"] += int(pres and bool(mods_in))
                stats["deleted_inferred"] += int(idel)
                stats["deleted_kernel"] += int(kdel)
                # classify disagreements between IsDeleted and (presence + Modified):
                #   false_deleted : kernel says deleted, but the shape (or a Modified image) IS in the result -> kernel bug
                #   consumed      : absent, no Modified image, kernel says NOT deleted, but Generated images exist
                #                   (creator ops consume sketch entities) -> benign, by OCCT's definition
                #   missed_delete : absent, no Modified/Generated images in the result, kernel says not deleted
                if kdel and not idel:
                    cls = "false_deleted"
                elif idel and not kdel:
                    cls = "consumed" if gens_in else "missed_delete"
                else:
                    cls = None
                if cls:
                    stats[cls] = stats.get(cls, 0) + 1
                    stats["isdeleted_disagree"] += 1
                    if len(examples) < 4:
                        examples.append({"input": name, "kind": KIND_NAME[k], "class": cls, "present": pres,
                                         "mods_in_result": len(mods_in), "kernel_deleted": kdel})
    stats["disagree_examples"] = examples
    stats["dangling_generated_examples"] = dangling
    return stats


def coverage(result, roles: dict, ledger=None) -> dict:
    """Which result faces are reachable by at least one role (or a propagated ledger reference)?"""
    named = ShapeMap()
    roles = dict(roles)
    if ledger is not None:
        roles["__ledger__"] = [e.shape for e in ledger.items]
    for shapes in roles.values():
        for s in shapes:
            if s.ShapeType() == TopAbs_FACE:
                named.Add(s)
    faces = topo.subshapes(result, TopAbs_FACE)
    unnamed = [f for f in faces if not named.Contains(f)]
    return {"faces": len(faces), "named": len(faces) - len(unnamed),
            "unnamed": [describe(f, result) for f in unnamed]}


def role_table(roles: dict, result) -> dict:
    """{role: {n, n_in_result, kinds, desc}} -- desc is the sorted set of geometric descriptors."""
    P = present_map(result)
    out = {}
    for r, shapes in roles.items():
        out[r] = {"n": len(shapes), "in_result": sum(P.Contains(s) for s in shapes),
                  "desc": sorted({describe(s, result) for s in shapes})}
    return out


# ---------------------------------------------------------------- geometric descriptors

def _r(x, nd=3):
    v = round(x, nd)
    return 0.0 if v == 0 else v


def oriented_in(shape, result):
    """Return `shape` with the orientation it has inside `result` (history lists are orientation-free)."""
    from OCP.TopExp import TopExp_Explorer
    ex = TopExp_Explorer(result, shape.ShapeType())
    while ex.More():
        if ex.Current().IsSame(shape):
            return ex.Current()
        ex.Next()
    return shape


def describe(s, result=None) -> str:
    """Short geometric descriptor: surface type + outward normal (planes) or axis (cyl/cone)."""
    t = s.ShapeType()
    if t == TopAbs_FACE:
        f = TopoDS.Face(oriented_in(s, result) if result is not None else s)
        ad = BRepAdaptor_Surface(f)
        st = topo.surface_type(f)
        if ad.GetType() == GeomAbs_Plane:
            u = 0.5 * (ad.FirstUParameter() + ad.LastUParameter())
            v = 0.5 * (ad.FirstVParameter() + ad.LastVParameter())
            pr = BRepLProp_SLProps(ad, u, v, 1, 1e-6)
            n = pr.Normal()
            sgn = -1 if f.Orientation() == TopAbs_REVERSED else 1
            return f"Plane n=({_r(sgn*n.X(),2)},{_r(sgn*n.Y(),2)},{_r(sgn*n.Z(),2)})"
        if ad.GetType() in (GeomAbs_Cylinder, GeomAbs_Cone):
            ax = (ad.Cylinder() if ad.GetType() == GeomAbs_Cylinder else ad.Cone()).Axis().Direction()
            d = [ax.X(), ax.Y(), ax.Z()]
            # canonical sign
            for c in d:
                if abs(c) > 1e-9:
                    if c < 0:
                        d = [-x for x in d]
                    break
            return f"{st} axis=({_r(d[0],2)},{_r(d[1],2)},{_r(d[2],2)})"
        return st
    if t == TopAbs_EDGE:
        return topo.curve_type(s)
    if t == TopAbs_VERTEX:
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(s))
        return f"V({_r(p.X(),2)},{_r(p.Y(),2)},{_r(p.Z(),2)})"
    return str(t)


def checks(shape) -> dict:
    c = topo.euler_counts(shape)
    return {"VEFRSH": list(c.tuple6()), "H": c.H, "euler_ok": c.ok, "valid": topo.is_valid(shape),
            "E_degen": c.E_degen, "E_seam": c.E_seam, "solids": len(topo.subshapes(shape, TopAbs_SOLID)),
            "volume": round(topo.volume(shape), 4)}


def deg(x):
    return math.radians(x)


# ---------------------------------------------------------------- ledger extension

class HistoryAdapter:
    """Give a BRepTools_History (e.g. ShapeUpgrade_UnifySameDomain.History()) the maker interface
    that refs.Ledger.propagate expects (Modified / Generated / IsDeleted)."""

    def __init__(self, hist):
        self.h = hist

    def Modified(self, s):
        return self.h.Modified(s)

    def Generated(self, s):
        return self.h.Generated(s)

    def IsDeleted(self, s):
        return self.h.IsRemoved(s)


class Ledger2(refs.Ledger):
    """Spike-01 ledger plus two things spike 02 needed:

    * follow_generated: an entry with no Modified image and not present in the result is carried to
      its Generated images *of the same shape type* (event 'regenerated').  Needed for
      BRepOffsetAPI_DraftAngle, which reports drafted faces through Generated(), not Modified().
    * merge detection: when two or more distinct pre-op sub-shapes map to the same result sub-shape
      (UnifySameDomain, fuse of coplanar faces), every entry involved gets an event 'merged'.
      policy='error_on_merge' in resolve() rejects such references.
    """

    def propagate(self, op_id, algo, result, follow_generated: bool = False):
        present = ShapeMap()
        for kind in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
            TopExp.MapShapes_s(result, kind, present)
        new = []           # (old_shape, Entry)
        for e in self.items:
            mods = [m for m in topo.occ_list(algo.Modified(e.shape)) if present.Contains(m)]
            kernel_says_deleted = bool(algo.IsDeleted(e.shape))
            gone = False
            if mods:
                ev = (op_id, "modified" if len(mods) == 1 else f"split{len(mods)}")
                new.extend((e.shape, refs.Entry(m, e.tag, e.genealogy + (ev,))) for m in mods)
            elif present.Contains(e.shape):
                new.append((e.shape, e))
            else:
                gens = [g for g in topo.occ_list(algo.Generated(e.shape))
                        if present.Contains(g) and g.ShapeType() == e.shape.ShapeType()] if follow_generated else []
                if gens:
                    ev = (op_id, "regenerated" if len(gens) == 1 else f"regenerated{len(gens)}")
                    new.extend((e.shape, refs.Entry(g, e.tag, e.genealogy + (ev,))) for g in gens)
                else:
                    self.deleted.append((e.tag, op_id, e.genealogy))
                    gone = True
            if gone != kernel_says_deleted:
                self.isdeleted_disagreements.append((str(e.tag), op_id, gone, kernel_says_deleted))
        # merge detection: result shape reached from >= 2 distinct source shapes
        img = ShapeMap()
        sources: dict[int, ShapeMap] = {}
        for old, ent in new:
            i = img.Add(ent.shape)
            sources.setdefault(i, ShapeMap()).Add(old)
        out = []
        for old, ent in new:
            if sources[img.FindIndex(ent.shape)].Extent() > 1:
                ent = refs.Entry(ent.shape, ent.tag, ent.genealogy + ((op_id, "merged"),))
            out.append(ent)
        self.items = out

    def resolve(self, feature, role, source=None, card=("exactly", 1), policy="propagate_all"):
        shapes = super().resolve(feature, role, source, card,
                                 "propagate_all" if policy == "error_on_merge" else policy)
        if policy == "error_on_merge" and any(ev[1] == "merged" for e in self.entries(feature, role, source)
                                              for ev in e.genealogy):
            raise refs.CardinalityError(f"{feature}.{role}({source}) was merged (policy error_on_merge)")
        return shapes

    def count(self, feature, role, source=None) -> int:
        """Distinct result sub-shapes reachable from a tag (no cardinality check)."""
        m = ShapeMap()
        for e in self.entries(feature, role, source):
            m.Add(e.shape)
        return m.Extent()

    def tags(self):
        seen = []
        for e in self.items + [refs.Entry(None, t, g) for t, _, g in self.deleted]:
            if e.tag not in seen:
                seen.append(e.tag)
        return seen
