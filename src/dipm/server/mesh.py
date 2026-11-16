"""Deterministic tessellation with face and edge identity (docs/gui.md §2 item 2, §5).

Face id i is the i-th face of `Build.faces()` and edge id j the j-th edge of `Build.edges()`
(the same map order `why()` and the genealogy table use).  Fixed deflections and a
single-threaded mesher make the same build produce the same bytes.  The solid itself is
never meshed in place: OCCT stores triangulations on the shape, and BRep text (our canonical
form) would then include them, so a copy is meshed instead.

Binary layout (little-endian, every section 4-byte aligned):

    magic  b"DIPM"   u32 version (=1)
    u32 n_verts, n_tris, n_faces, n_edges, n_edge_pts
    f32 positions[n_verts*3]     f32 normals[n_verts*3]
    u32 indices[n_tris*3]
    u32 face_ranges[n_faces*2]   (first triangle, triangle count) per face id
    u32 edge_ranges[n_edges*2]   (first point, point count) per edge id; count 0 = degenerated
    f32 edge_points[n_edge_pts*3]

Vertices are per face (not shared across faces), so per-face colours need no splitting.
"""
from __future__ import annotations

import hashlib
import struct

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.BRepLib import BRepLib_ToolTriangulatedShape
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GCPnts import GCPnts_TangentialDeflection
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

from .. import kernel as K

MAGIC = b"DIPM"
VERSION = 1
LINEAR_DEFLECTION = 0.05     # mm
ANGULAR_DEFLECTION = 0.2     # rad (~11.5 degrees: a 5 mm hole gets ~32 segments)
EDGE_MIN_POINTS = 2


def tessellate(shape) -> dict:
    """{positions, normals, indices, face_ranges, edge_ranges, edge_points} as numpy arrays."""
    faces = K.subshapes(shape, K.KINDS["face"])
    edges = K.subshapes(shape, K.KINDS["edge"])
    copy = BRepBuilderAPI_Copy(shape, True, False).Shape()
    cfaces = K.subshapes(copy, K.KINDS["face"])
    if len(cfaces) != len(faces):     # pragma: no cover - the copy is structurally identical
        raise RuntimeError("mesh copy changed the face count")
    BRepMesh_IncrementalMesh(copy, LINEAR_DEFLECTION, False, ANGULAR_DEFLECTION, False)
    pos, nor, idx, franges = [], [], [], []
    nv = nt = 0
    for f in cfaces:
        face = TopoDS.Face(f)
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is None:
            franges.append((nt, 0))
            continue
        trsf = loc.Transformation()
        BRepLib_ToolTriangulatedShape.ComputeNormals_s(face, tri)
        rev = face.Orientation() == TopAbs_REVERSED
        n = tri.NbNodes()
        for i in range(1, n + 1):
            p = tri.Node(i).Transformed(trsf)
            pos.append((p.X(), p.Y(), p.Z()))
            d = tri.Normal(i).Transformed(trsf)       # surface normal; ignores face orientation
            sg = -1.0 if rev else 1.0
            nor.append((sg * d.X(), sg * d.Y(), sg * d.Z()))
        m = tri.NbTriangles()
        for i in range(1, m + 1):
            a, b, c = tri.Triangle(i).Get()
            if rev:
                b, c = c, b
            idx.append((nv + a - 1, nv + b - 1, nv + c - 1))
        franges.append((nt, m))
        nv += n
        nt += m
    eranges, epts = [], []
    for e in edges:
        if K.is_degenerated(e):
            eranges.append((len(epts), 0))
            continue
        curve = BRepAdaptor_Curve(TopoDS.Edge(e))
        disc = GCPnts_TangentialDeflection(curve, ANGULAR_DEFLECTION, LINEAR_DEFLECTION, EDGE_MIN_POINTS)
        start = len(epts)
        for i in range(1, disc.NbPoints() + 1):
            p = disc.Value(i)
            epts.append((p.X(), p.Y(), p.Z()))
        eranges.append((start, len(epts) - start))
    f32 = lambda a: np.asarray(a, dtype="<f4").reshape(-1, 3) if a else np.zeros((0, 3), "<f4")
    u32 = lambda a, w: np.asarray(a, dtype="<u4").reshape(-1, w) if a else np.zeros((0, w), "<u4")
    return {"positions": f32(pos), "normals": f32(nor), "indices": u32(idx, 3), "face_ranges": u32(franges, 2),
            "edge_ranges": u32(eranges, 2), "edge_points": f32(epts)}


def encode(m: dict) -> bytes:
    head = MAGIC + struct.pack("<6I", VERSION, len(m["positions"]), len(m["indices"]), len(m["face_ranges"]),
                               len(m["edge_ranges"]), len(m["edge_points"]))
    return head + b"".join(m[k].astype(m[k].dtype.newbyteorder("<")).tobytes()
                           for k in ("positions", "normals", "indices", "face_ranges", "edge_ranges", "edge_points"))


def decode(data: bytes) -> dict:
    """Inverse of `encode` (tests and tooling; the browser has its own decoder)."""
    if data[:4] != MAGIC:
        raise ValueError("not a dipm mesh")
    ver, nv, nt, nf, ne, nep = struct.unpack_from("<6I", data, 4)
    if ver != VERSION:
        raise ValueError(f"mesh version {ver}")
    off = 28
    out = {}
    for k, n, w, dt in (("positions", nv, 3, "<f4"), ("normals", nv, 3, "<f4"), ("indices", nt, 3, "<u4"),
                        ("face_ranges", nf, 2, "<u4"), ("edge_ranges", ne, 2, "<u4"), ("edge_points", nep, 3, "<f4")):
        cnt = n * w
        out[k] = np.frombuffer(data, dtype=dt, count=cnt, offset=off).reshape(n, w)
        off += cnt * 4
    if off != len(data):
        raise ValueError("trailing bytes in mesh")
    return out


def mesh_bytes(shape) -> tuple[str, bytes]:
    """(mesh id, encoded mesh).  The id is a content hash, so equal builds share an id."""
    data = encode(tessellate(shape))
    return hashlib.sha256(data).hexdigest()[:20], data
