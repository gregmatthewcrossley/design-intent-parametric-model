"""Thin helpers over raw OCP (OpenCascade).  This module is the *backend boundary*.

Everything that touches OCCT directly lives here or in `ops.py` / `invariants.py`.
The rest of the package talks in terms of shapes, `Vec3`, and the helpers below.
See docs/dsl.md §6 (engine: borrow the kernel, own the solver) and the OCCT
gotchas in CLAUDE.md.  Ported from spikes/01-occt-feasibility/topo.py and
spikes/02-operation-history/common.py.

Conventions: millimetres, degrees at the API surface (radians only inside OCP calls).

Hard-won rules respected here:
  * identity is `IsSame` / `TopTools_ShapeMapHasher` (TShape + Location, orientation
    ignored); never `IsPartner` (an extrude's END cap shares its START cap's TShape);
  * iterate OCP lists with `occ_list` (copy-and-pop), never `list(lst)`, which costs
    ~2.5 ms per list in OCP 8.0.1;
  * booleans always take a *list* of tools, never a compound that might self-overlap
    (spike 02 §1.7: that silently cuts nothing yet passes BRepCheck and Euler).
"""
from __future__ import annotations

import math
import os
import re
import tempfile
from dataclasses import dataclass

from OCP.BOPAlgo import BOPAlgo_Options
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_Transform
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepTools import BRepTools
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_CurveType, GeomAbs_Plane, GeomAbs_SurfaceType
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.Message import Message, Message_Gravity
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopAbs import (TopAbs_EDGE, TopAbs_IN, TopAbs_FACE, TopAbs_REVERSED, TopAbs_SHELL, TopAbs_SOLID,
                        TopAbs_VERTEX, TopAbs_WIRE)
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.collections import (
    IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeAncestorMap,
    IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap,
    List_TopoDS_Shape,
)
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

for _p in Message.DefaultMessenger_s().Printers():  # silence STEP writer chatter
    _p.SetTraceLevel(Message_Gravity.Message_Fail)

# Determinism: spike 01 found BRep output byte-identical with parallel BOP on and off, but only
# on one machine.  v0 pins it OFF so cross-platform runs have one fewer variable (DECISIONS #10).
BOPAlgo_Options.SetParallelMode_s(False)

KINDS = {"face": TopAbs_FACE, "edge": TopAbs_EDGE, "vertex": TopAbs_VERTEX, "wire": TopAbs_WIRE}
KIND_NAME = {TopAbs_FACE: "face", TopAbs_EDGE: "edge", TopAbs_VERTEX: "vertex",
             TopAbs_SOLID: "solid", TopAbs_SHELL: "shell", TopAbs_WIRE: "wire"}


# ---------------------------------------------------------------- small vector type

@dataclass(frozen=True)
class Vec3:
    """Immutable 3-vector (points and directions).  Plain floats; no kernel objects."""
    x: float
    y: float
    z: float

    def __add__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, k: float) -> "Vec3":
        return Vec3(self.x * k, self.y * k, self.z * k)

    __rmul__ = __mul__

    def __neg__(self) -> "Vec3":
        return Vec3(-self.x, -self.y, -self.z)

    def dot(self, o: "Vec3") -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o: "Vec3") -> "Vec3":
        return Vec3(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x)

    def length(self) -> float:
        return math.sqrt(self.dot(self))

    def unit(self) -> "Vec3":
        n = self.length()
        if n < 1e-12:
            raise ValueError("cannot normalise a zero-length vector")
        return self * (1.0 / n)

    def pnt(self) -> gp_Pnt:
        return gp_Pnt(self.x, self.y, self.z)

    def dir(self) -> gp_Dir:
        return gp_Dir(self.x, self.y, self.z)

    def vec(self) -> gp_Vec:
        return gp_Vec(self.x, self.y, self.z)

    def rounded(self, nd: int = 6) -> tuple:
        return tuple(_r(c, nd) for c in (self.x, self.y, self.z))

    def __repr__(self) -> str:
        return "(" + ", ".join(f"{c:g}" for c in self.rounded(4)) + ")"


X = Vec3(1, 0, 0)
Y = Vec3(0, 1, 0)
Z = Vec3(0, 0, 1)
ORIGIN = Vec3(0, 0, 0)


def _r(x: float, nd: int = 6) -> float:
    v = round(x, nd)
    return 0.0 if v == 0 else v


def vec_of(p) -> Vec3:
    return Vec3(p.X(), p.Y(), p.Z())


# ---------------------------------------------------------------- lists, maps, sub-shapes

def occ_list(lst) -> list:
    """Convert an OCP List_TopoDS_Shape to a Python list (copy-and-pop: ~500x faster than iterating)."""
    c = List_TopoDS_Shape()
    c.Assign(lst)
    out = []
    while c.Size():
        out.append(c.First())
        c.RemoveFirst()
    return out


def tool_list(shapes) -> List_TopoDS_Shape:
    lst = List_TopoDS_Shape()
    for s in shapes:
        lst.Append(s)
    return lst


def subshapes(shape, kind) -> list:
    """Distinct sub-shapes of a kind, de-duplicated by (TShape, Location), orientation ignored."""
    m = ShapeMap()
    TopExp.MapShapes_s(shape, kind, m)
    return [m.FindKey(i) for i in range(1, m.Extent() + 1)]


def presence_map(shape) -> ShapeMap:
    """One map of every face/edge/vertex of `shape`, for O(1) `Contains` presence tests."""
    m = ShapeMap()
    for k in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
        TopExp.MapShapes_s(shape, k, m)
    return m


def oriented_in(sub, whole):
    """Return `sub` with the orientation it has inside `whole`.

    History lists return sub-shapes in arbitrary orientation; outward normals must be read
    from the occurrence inside the solid (spike 01 RESULTS §4 'Add').
    """
    ex = TopExp_Explorer(whole, sub.ShapeType())
    while ex.More():
        if ex.Current().IsSame(sub):
            return ex.Current()
        ex.Next()
    return sub


def shared_edges(f1, f2) -> list:
    """Edges common to two faces (identity by IsSame).  Basis of `edges_between` (dsl.md §3.4)."""
    m = ShapeMap()
    for e in subshapes(f1, TopAbs_EDGE):
        m.Add(e)
    return [e for e in subshapes(f2, TopAbs_EDGE) if m.Contains(e)]


def faces_of_edge(shape, edge) -> list:
    """Faces of `shape` adjacent to `edge` (de-duplicated)."""
    amap = ShapeAncestorMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, amap)
    i = amap.FindIndex(edge)
    if i == 0:
        return []
    out = []
    for f in occ_list(amap.FindFromIndex(i)):
        if not any(f.IsSame(o) for o in out):
            out.append(f)
    return out


# ---------------------------------------------------------------- measures

def volume(shape) -> float:
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.Mass()


def area(face) -> float:
    p = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, p)
    return p.Mass()


def length(edge) -> float:
    p = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, p)
    return p.Mass()


def centroid(shape) -> Vec3:
    """Centroid of a face (area), edge (length) or vertex (its point)."""
    t = shape.ShapeType()
    if t == TopAbs_VERTEX:
        return vec_of(BRep_Tool.Pnt_s(TopoDS.Vertex(shape)))
    p = GProp_GProps()
    if t == TopAbs_EDGE:
        BRepGProp.LinearProperties_s(shape, p)
    elif t == TopAbs_FACE:
        BRepGProp.SurfaceProperties_s(shape, p)
    else:
        BRepGProp.VolumeProperties_s(shape, p)
    return vec_of(p.CentreOfMass())


def measure(shape) -> float:
    """Area for faces, length for edges, 0 for vertices (used in fingerprints)."""
    t = shape.ShapeType()
    if t == TopAbs_FACE:
        return area(shape)
    if t == TopAbs_EDGE:
        return length(shape)
    return 0.0


def bbox(shape) -> tuple[Vec3, Vec3]:
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    return vec_of(b.CornerMin()), vec_of(b.CornerMax())


def distance(a, b) -> float:
    """Minimum distance between two shapes (0 if they touch or overlap)."""
    d = BRepExtrema_DistShapeShape(a, b)
    if not d.IsDone():
        raise RuntimeError("BRepExtrema_DistShapeShape failed")
    return d.Value()


def common_volume(a, b) -> float:
    op = BRepAlgoAPI_Common(a, b)
    return volume(op.Shape()) if op.IsDone() else 0.0


def surface_type(face) -> str:
    return GeomAbs_SurfaceType(BRepAdaptor_Surface(TopoDS.Face(face)).GetType()).name.replace("GeomAbs_", "")


def curve_type(edge) -> str:
    e = TopoDS.Edge(edge)
    if BRep_Tool.Degenerated_s(e):
        return "Degenerated"
    return GeomAbs_CurveType(BRepAdaptor_Curve(e).GetType()).name.replace("GeomAbs_", "")


def is_degenerated(edge) -> bool:
    return BRep_Tool.Degenerated_s(TopoDS.Edge(edge))


def face_normal(face, whole=None) -> Vec3:
    """Outward unit normal of a face at its parametric middle (planes: everywhere).

    Pass `whole` (the solid) so the face's orientation inside the solid is used.
    """
    f = TopoDS.Face(oriented_in(face, whole) if whole is not None else face)
    ad = BRepAdaptor_Surface(f)
    u = 0.5 * (ad.FirstUParameter() + ad.LastUParameter())
    v = 0.5 * (ad.FirstVParameter() + ad.LastVParameter())
    if ad.GetType() == GeomAbs_Plane:
        d = ad.Plane().Axis().Direction()
        n = Vec3(d.X(), d.Y(), d.Z())
    else:
        pr = BRepLProp_SLProps(ad, u, v, 1, 1e-6)
        if not pr.IsNormalDefined():
            raise ValueError("face normal undefined at parametric centre")
        d = pr.Normal()
        n = Vec3(d.X(), d.Y(), d.Z())
    return -n if f.Orientation() == TopAbs_REVERSED else n


def is_planar(face) -> bool:
    return BRepAdaptor_Surface(TopoDS.Face(face)).GetType() == GeomAbs_Plane


def describe(sub, whole=None) -> str:
    """Short, human-readable geometric descriptor (surface type + normal/axis, or curve type)."""
    t = sub.ShapeType()
    if t == TopAbs_FACE:
        st = surface_type(sub)
        if st == "Plane":
            return f"Plane n={face_normal(sub, whole)!r}"
        ad = BRepAdaptor_Surface(TopoDS.Face(sub))
        if st in ("Cylinder", "Cone"):
            g = ad.Cylinder() if st == "Cylinder" else ad.Cone()
            d = g.Axis().Direction()
            ax = Vec3(d.X(), d.Y(), d.Z())
            for c in (ax.x, ax.y, ax.z):  # canonical sign
                if abs(c) > 1e-9:
                    ax = ax if c > 0 else -ax
                    break
            if st == "Cylinder":
                return f"Cylinder axis={ax!r} r={g.Radius():g}"
            return f"Cone axis={ax!r} half-angle={math.degrees(g.SemiAngle()):g}deg"
        return st
    if t == TopAbs_EDGE:
        return f"{curve_type(sub)} L={length(sub):.4g}"
    if t == TopAbs_VERTEX:
        return f"Vertex {centroid(sub)!r}"
    return KIND_NAME.get(t, str(t))


def extent_along(face, direction: Vec3, samples: int = 16) -> tuple[float, float]:
    """(min, max) of the projection of a face's outer boundary onto `direction`.

    Lines are exact at their endpoints; curved edges are sampled (`samples` per edge),
    which is deterministic but approximate for arcs.  Used by face-relative placements.
    """
    d = direction.unit()
    w = BRepTools.OuterWire_s(TopoDS.Face(face))
    lo, hi = math.inf, -math.inf
    ex = TopExp_Explorer(w, TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge(ex.Current())
        if not BRep_Tool.Degenerated_s(e):
            c = BRepAdaptor_Curve(e)
            a, b = c.FirstParameter(), c.LastParameter()
            n = 1 if c.GetType() == GeomAbs_CurveType.GeomAbs_Line else samples
            for i in range(n + 1):
                p = vec_of(c.Value(a + (b - a) * i / n))
                s = p.dot(d)
                lo, hi = min(lo, s), max(hi, s)
        ex.Next()
    return lo, hi


def segments_along(shape, origin: Vec3, direction: Vec3, length: float, nd: int = 6) -> list[tuple[float, float]]:
    """Where the segment origin + t*direction (0 <= t <= length) lies inside `shape`.

    Exact: a regularized `common` of the segment's edge with the shape (a solid, or a
    face the segment lies in).  Returns sorted, rounded (t0, t1) intervals.  Used by the
    interpretations mechanism (architecture §10.2) for "up to next", "through the
    plate", and the material chords that define a face's exposed region.
    """
    d = direction.unit()
    edge = BRepBuilderAPI_MakeEdge(origin.pnt(), (origin + d * length).pnt()).Edge()
    out = []
    for e in subshapes(boolean("common", edge, [shape]).Shape(), TopAbs_EDGE):
        ts = sorted((centroid(v) - origin).dot(d) for v in subshapes(e, TopAbs_VERTEX))
        if ts and ts[-1] - ts[0] > 1e-9:
            out.append((_r(ts[0], nd), _r(ts[-1], nd)))
    out.sort()
    merged: list = []                    # adjacent pieces (split at a vertex of the shape) join up
    for a, b in out:
        if merged and a <= merged[-1][1] + 1e-9:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def inside_solid(shape, p: Vec3, tol: float = 1e-7) -> bool:
    """Is point `p` strictly inside the solid `shape`?"""
    return BRepClass3d_SolidClassifier(shape, p.pnt(), tol).State() == TopAbs_IN


# ---------------------------------------------------------------- kernel operations used by ops.py

def boolean(kind: str, arg, tools: list):
    """Regularized boolean with tools passed as a LIST (never one compound).  Returns the maker.

    kind: 'cut' | 'fuse' | 'common'.  dsl.md §3.1, §4.3 (failure class 'silently wrong but valid').
    """
    op = {"cut": BRepAlgoAPI_Cut, "fuse": BRepAlgoAPI_Fuse, "common": BRepAlgoAPI_Common}[kind]()
    op.SetArguments(tool_list([arg]))
    op.SetTools(tool_list(tools))
    op.SetRunParallel(False)
    op.Build()
    if not op.IsDone():
        raise RuntimeError(f"boolean {kind} failed")
    return op


def transform(shape, trsf: gp_Trsf, copy: bool = True):
    """Apply a gp_Trsf; returns the maker (its ModifiedShape/Modified give history)."""
    tr = BRepBuilderAPI_Transform(shape, trsf, copy)
    tr.Build()
    return tr


def trsf_translate(v: Vec3) -> gp_Trsf:
    t = gp_Trsf()
    t.SetTranslation(v.vec())
    return t


def trsf_rotate(origin: Vec3, axis: Vec3, angle_deg: float) -> gp_Trsf:
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(origin.pnt(), axis.dir()), math.radians(angle_deg))
    return t


def trsf_mirror(origin: Vec3, normal: Vec3) -> gp_Trsf:
    t = gp_Trsf()
    t.SetMirror(gp_Ax2(origin.pnt(), normal.dir()))
    return t


# ---------------------------------------------------------------- serialization

def brep_bytes(shape) -> bytes:
    """OCCT BRep text: the canonical serialization (byte-identical across builds, spike 01 §3)."""
    fd, path = tempfile.mkstemp(suffix=".brep")
    os.close(fd)
    try:
        BRepTools.Write_s(shape, path)
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def write_brep(shape, path: str) -> None:
    BRepTools.Write_s(shape, path)


def write_step(shape, path: str) -> None:
    """Interchange only.  STEP embeds a timestamp and a per-process product counter;
    compare with `canonical_step`, never raw bytes (spike 01 §3)."""
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    w = STEPControl_Writer()
    w.Transfer(shape, STEPControl_AsIs)
    if w.Write(path) != IFSelect_RetDone:
        raise RuntimeError(f"STEP write failed: {path}")


def canonical_step(data: bytes) -> bytes:
    """Strip the FILE_NAME timestamp and normalise the 'Open CASCADE STEP translator N' counter."""
    data = re.sub(rb"FILE_NAME\(.*?\);", b"FILE_NAME(<stripped>);", data, flags=re.S)
    return re.sub(rb"(Open CASCADE STEP translator [0-9.]+) [0-9]+", rb"\1 <n>", data)
