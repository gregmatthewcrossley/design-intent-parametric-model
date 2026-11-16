"""Topological counting, Euler-Poincare, signatures and serialization on raw OCP shapes.

Counting convention (derived in Q1, see RESULTS.md):
  * sub-shapes are de-duplicated with TopTools_ShapeMapHasher, i.e. by (TShape, Location),
    ignoring orientation  -> a seam edge (used twice by one face, once per orientation) counts ONCE;
  * degenerated edges (BRep_Tool.Degenerated: sphere/cone poles) are NOT counted as edges;
  * the vertex at a degenerated edge IS counted (it is the pole);
  * R = sum over faces of (number of wires - 1);
  * S = number of shells; H solved from V - E + F - R = 2(S - H).
"""
from __future__ import annotations

import hashlib
import re
import os
import tempfile
from dataclasses import dataclass, asdict

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_SurfaceType, GeomAbs_CurveType
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.TopAbs import (TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE, TopAbs_WIRE,
                        TopAbs_SHELL, TopAbs_SOLID)
from OCP.TopExp import TopExp
from OCP.collections import (
    IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as TopTools_IndexedMapOfShape,
    IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as TopTools_IndexedDataMapOfShapeListOfShape,
)
from OCP.TopoDS import TopoDS
from OCP.Message import Message, Message_Gravity

for _p in Message.DefaultMessenger_s().Printers():   # silence STEP writer chatter
    _p.SetTraceLevel(Message_Gravity.Message_Fail)


# ---------------------------------------------------------------- basic maps

def occ_list(lst) -> list:
    """Convert an OCP List_TopoDS_Shape to a Python list.

    NB: plain `list(lst)` / `for x in lst` is ~2.5 ms PER LIST in OCP 8.0.1
    (pathologically slow iterator binding); copy-and-pop is ~500x faster.
    """
    from OCP.collections import List_TopoDS_Shape
    c = List_TopoDS_Shape()
    c.Assign(lst)
    out = []
    while c.Size():
        out.append(c.First())
        c.RemoveFirst()
    return out


def subshapes(shape, kind) -> list:
    """Distinct sub-shapes of a kind, keyed by (TShape, Location), orientation ignored."""
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, kind, m)
    return [m.FindKey(i) for i in range(1, m.Extent() + 1)]


def raw_occurrences(shape, kind) -> int:
    """Count every occurrence met while exploring (no de-duplication at all)."""
    from OCP.TopExp import TopExp_Explorer
    n, ex = 0, TopExp_Explorer(shape, kind)
    while ex.More():
        n += 1
        ex.Next()
    return n


def count_by_tshape(shape, kind) -> int:
    """De-duplicate by TShape only (IsPartner: ignores Location AND orientation).

    This is the 'shared TShape' trap: two placed copies of one TShape collapse to one.
    """
    from OCP.TopExp import TopExp_Explorer
    seen, ex = [], TopExp_Explorer(shape, kind)
    while ex.More():
        cur = ex.Current()
        if not any(cur.IsPartner(o) for o in seen):
            seen.append(cur)
        ex.Next()
    return len(seen)


def count_orientation_sensitive(shape, kind) -> int:
    """De-duplicate with IsEqual (TShape + Location + Orientation)."""
    from OCP.TopExp import TopExp_Explorer
    seen, ex = [], TopExp_Explorer(shape, kind)
    while ex.More():
        cur = ex.Current()
        if not any(cur.IsEqual(o) for o in seen):
            seen.append(cur)
        ex.Next()
    return len(seen)


def is_degenerated(edge) -> bool:
    return BRep_Tool.Degenerated_s(TopoDS.Edge(edge))


def seam_edges(shape) -> list:
    """Edges that are closed on some face (used twice by that face) -- periodic seams."""
    out = []
    efmap = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, efmap)
    for i in range(1, efmap.Extent() + 1):
        e = TopoDS.Edge(efmap.FindKey(i))
        faces = occ_list(efmap.FindFromIndex(i))
        for f in faces:
            if BRep_Tool.IsClosed_s(e, TopoDS.Face(f)) and not BRep_Tool.Degenerated_s(e):
                out.append(e)
                break
    return out


# ---------------------------------------------------------------- Euler

@dataclass(frozen=True)
class EulerCounts:
    V: int
    E: int
    F: int
    R: int
    S: int
    H: float           # solved genus; integer iff the check passes
    E_all: int         # edges including degenerated
    E_degen: int
    E_seam: int
    ok: bool           # H integral and >= 0

    def tuple6(self):
        return (self.V, self.E, self.F, self.R, self.S, int(self.H))


def euler_counts(shape, exclude_degenerated: bool = True) -> EulerCounts:
    V = len(subshapes(shape, TopAbs_VERTEX))
    edges = subshapes(shape, TopAbs_EDGE)
    degen = [e for e in edges if is_degenerated(e)]
    E = len(edges) - (len(degen) if exclude_degenerated else 0)
    faces = subshapes(shape, TopAbs_FACE)
    F = len(faces)
    R = sum(len(subshapes(f, TopAbs_WIRE)) - 1 for f in faces)
    S = len(subshapes(shape, TopAbs_SHELL))
    chi = V - E + F - R
    H = S - chi / 2
    ok = float(H).is_integer() and H >= 0
    return EulerCounts(V, E, F, R, S, H, len(edges), len(degen), len(seam_edges(shape)), ok)


def genus(shape) -> int:
    c = euler_counts(shape)
    if not c.ok:
        raise ValueError(f"Euler-Poincare check failed: {c}")
    return int(c.H)


def check_delta_h(before, after, expected_dh: int) -> tuple[bool, int]:
    dh = genus(after) - genus(before)
    return dh == expected_dh, dh


def is_valid(shape) -> bool:
    return BRepCheck_Analyzer(shape, True).IsValid()


def volume(shape) -> float:
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.Mass()


def area(face) -> float:
    p = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, p)
    return p.Mass()


def centroid(face):
    p = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, p)
    c = p.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def surface_type(face) -> str:
    return GeomAbs_SurfaceType(BRepAdaptor_Surface(TopoDS.Face(face)).GetType()).name.replace("GeomAbs_", "")


def curve_type(edge) -> str:
    e = TopoDS.Edge(edge)
    if BRep_Tool.Degenerated_s(e):
        return "Degenerated"
    return GeomAbs_CurveType(BRepAdaptor_Curve(e).GetType()).name.replace("GeomAbs_", "")


# ---------------------------------------------------------------- signature

def _q(x: float, sig: int = 6) -> str:
    """Round to `sig` significant digits; normalise -0."""
    s = f"{x:.{sig}g}"
    return "0" if s in ("-0", "0") else s


def adjacency_hash(shape, rounds: int = 4, geometric: bool = True) -> str:
    """Order-independent Weisfeiler-Lehman hash of the face adjacency graph.

    Node label: surface type, rounded area, wire count.
    Edge label: curve type of the shared edge (degenerated edges are skipped,
    seam edges become self-loops labelled 'seam').
    """
    faces = subshapes(shape, TopAbs_FACE)
    fidx = {}
    fm = TopTools_IndexedMapOfShape()
    for f in faces:
        fm.Add(f)
    labels = [f"{surface_type(f)}|{_q(area(f)) if geometric else ''}|w{len(subshapes(f, TopAbs_WIRE))}"
              for f in faces]
    efmap = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, efmap)
    nbrs = [[] for _ in faces]
    for i in range(1, efmap.Extent() + 1):
        e = efmap.FindKey(i)
        if is_degenerated(e):
            continue
        anc = list({fm.FindIndex(f) - 1 for f in occ_list(efmap.FindFromIndex(i))})
        ct = curve_type(e)
        if len(anc) == 1:
            nbrs[anc[0]].append(("seam:" + ct, anc[0]))
        else:
            for a in anc:
                for b in anc:
                    if a != b:
                        nbrs[a].append((ct, b))
    h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:16]
    cur = [h(l) for l in labels]
    for _ in range(rounds):
        cur = [h(cur[i] + "|" + ",".join(sorted(f"{el}>{cur[j]}" for el, j in nbrs[i])))
               for i in range(len(faces))]
    return hashlib.sha256(",".join(sorted(cur)).encode()).hexdigest()


def signature(shape) -> dict:
    c = euler_counts(shape)
    return {"VEFRSH": c.tuple6(), "adj": adjacency_hash(shape),
            "adj_topo": adjacency_hash(shape, geometric=False)}


# ---------------------------------------------------------------- serialization

def brep_bytes(shape) -> bytes:
    fd, path = tempfile.mkstemp(suffix=".brep")
    os.close(fd)
    try:
        BRepTools.Write_s(shape, path)
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def step_bytes(shape, strip_timestamp: bool = True) -> bytes:
    fd, path = tempfile.mkstemp(suffix=".step")
    os.close(fd)
    try:
        Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
        w = STEPControl_Writer()
        w.Transfer(shape, STEPControl_AsIs)
        assert w.Write(path) == IFSelect_RetDone
        with open(path, "rb") as fh:
            data = fh.read()
    finally:
        os.unlink(path)
    if strip_timestamp:
        # FILE_NAME('name','2026-11-15T12:00:00',...); may span several lines
        data = re.sub(rb"FILE_NAME\(.*?\);", b"FILE_NAME(<stripped>);", data, flags=re.S)
    return data


def canonical_step(data: bytes) -> bytes:
    """Timestamp stripped AND the per-process STEPControl_Writer product counter
    ('Open CASCADE STEP translator 8.0 <n>') normalised."""
    data = re.sub(rb"FILE_NAME\(.*?\);", b"FILE_NAME(<stripped>);", data, flags=re.S)
    return re.sub(rb"(Open CASCADE STEP translator [0-9.]+) [0-9]+", rb"\1 <n>", data)


def step_bytes_build123d(shape) -> bytes:
    """STEP via build123d.export_step (XCAF/STEPCAFControl path), timestamp stripped."""
    from build123d import Solid, export_step
    fd, path = tempfile.mkstemp(suffix=".step")
    os.close(fd)
    try:
        export_step(Solid(shape), path)
        with open(path, "rb") as fh:
            data = fh.read()
    finally:
        os.unlink(path)
    return re.sub(rb"FILE_NAME\(.*?\);", b"FILE_NAME(<stripped>);", data, flags=re.S)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
