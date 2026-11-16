"""One parametric test model per operation, built on raw OCP so every maker's history is in hand.

Each builder returns an OpRun:
  * shape / before        result solid and the solid the op acted on (None for creator ops);
  * roles                 {role_name: [sub-shapes]} captured straight from the maker's history
                          (the candidate DSL role vocabulary);
  * expected_card         declared cardinality per role, as a DSL author would declare it for this
                          parameter point (the *intent*; the harness compares it to what the kernel gives);
  * expected_dH/dS        declared topological deltas;
  * ledger                spike-01-style reference ledger for the pre-existing body references,
                          propagated through the op;
  * algo, audit_inputs    so q1 can audit Generated/Modified/IsDeleted against the result.

Conventions: mm, degrees.  Base body = "E": a 40 x 30 x 20 block extruded along +Z from a named
rectangle a(0,0) b(40,0) c(40,30) d(0,30); its sides are E.side(a-b) (-Y), (b-c) (+X), (c-d) (+Y),
(d-a) (-X), caps E.cap(START) (z=0) and E.cap(END) (z=20), lateral edges E.lateral_edge(a..d).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from common import (HistoryAdapter, Ledger2, ShapeMap, deg, describe, named_polygon, present_map, rename, topo)
from refs import Tag

from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform)
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer
from OCP.BRepOffsetAPI import (BRepOffsetAPI_DraftAngle, BRepOffsetAPI_MakeOffsetShape, BRepOffsetAPI_MakePipe,
                               BRepOffsetAPI_MakePipeShell, BRepOffsetAPI_MakeThickSolid,
                               BRepOffsetAPI_ThruSections)
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GC import GC_MakeArcOfCircle
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.collections import List_TopoDS_Shape
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pln, gp_Pnt, gp_Trsf, gp_Vec


@dataclass
class OpRun:
    op: str
    variant: str
    params: dict
    shape: object
    before: object
    roles: dict
    expected_card: dict
    expected_dH: int
    expected_dS: int
    algo: object = None
    audit_inputs: dict = field(default_factory=dict)
    ledger: Ledger2 | None = None
    base_expected: dict = field(default_factory=dict)   # {(feature, role, source): expected count}
    notes: list = field(default_factory=list)


def L(lst):
    return topo.occ_list(lst)


def faces_in(shapes):
    return [s for s in shapes if s.ShapeType() == TopAbs_FACE]


def edges_between(f1, f2):
    """Derived structural reference: edges shared by two referenced faces."""
    m = ShapeMap()
    for e in topo.subshapes(f1, TopAbs_EDGE):
        m.Add(e)
    return [e for e in topo.subshapes(f2, TopAbs_EDGE) if m.Contains(e)]


# ---------------------------------------------------------------- base block "E"

SIDES = ("a-b", "b-c", "c-d", "d-a")


def block(Lx=40.0, Wy=30.0, Hz=20.0, ledger: Ledger2 | None = None, fid="E"):
    f, es, vs = named_polygon({"a": (0, 0, 0), "b": (Lx, 0, 0), "c": (Lx, Wy, 0), "d": (0, Wy, 0)})
    mk = BRepPrimAPI_MakePrism(f, gp_Vec(0, 0, Hz))
    mk.Build()
    led = ledger if ledger is not None else Ledger2()
    led.add(Tag(fid, "cap", "START"), [mk.FirstShape()])
    led.add(Tag(fid, "cap", "END"), [mk.LastShape()])
    for n, e in es.items():
        led.add(Tag(fid, "side", n), L(mk.Generated(e)))
    for n, v in vs.items():
        led.add(Tag(fid, "lateral_edge", n), L(mk.Generated(v)))
    return mk.Shape(), led


ADJ = {"a": ("d-a", "a-b"), "b": ("a-b", "b-c"), "c": ("b-c", "c-d"), "d": ("c-d", "d-a")}


def derived_lateral_edges(led) -> dict:
    """Re-derive E.lateral_edge(v) as edges_between(E.side(prev), E.side(next)) from the *face* references.

    Used where an op gives no edge history (draft, offset): returns {v: count}.
    """
    out = {}
    for v, (s1, s2) in ADJ.items():
        f1, f2 = led.entries("E", "side", s1), led.entries("E", "side", s2)
        out[v] = len(edges_between(f1[0].shape, f2[0].shape)) if (len(f1) == 1 and len(f2) == 1) else None
    return out


def base_expect_all(fid="E", faces=1, lateral=1, over=None):
    d = {(fid, "cap", "START"): faces, (fid, "cap", "END"): faces}
    for s in SIDES:
        d[(fid, "side", s)] = faces
    for v in "abcd":
        d[(fid, "lateral_edge", v)] = lateral
    d.update(over or {})
    return d


# ---------------------------------------------------------------- 1. revolve

def revolve(angle=180.0, r_in=5.0, r_out=10.0, h=4.0, top_slant=0.0):
    """Rectangle (r_in..r_out) x (0..h) in the XZ plane revolved about Z.  top_slant tilts the top edge."""
    pts = {"ib": (r_in, 0, 0), "ob": (r_out, 0, 0), "ot": (r_out, 0, h + top_slant), "it": (r_in, 0, h)}
    prof, es, vs = named_polygon(pts)
    es = rename(es, {"ib-ob": "bottom", "ob-ot": "outer", "ot-it": "top", "it-ib": "inner"})
    ax = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    full = angle >= 360.0
    mk = BRepPrimAPI_MakeRevol(prof, ax) if full else BRepPrimAPI_MakeRevol(prof, ax, deg(angle))
    mk.Build()
    s = mk.Shape()
    P = present_map(s)
    roles, notes, fallback = {}, [], []
    if not full:
        roles["cap(START)"] = [mk.FirstShape()]
        roles["cap(END)"] = [mk.LastShape()]
    for n, e in es.items():
        g = faces_in(L(mk.Generated(e)))
        if not g:
            # WORKAROUND: a full revolve drops Generated() for edges perpendicular to the axis
            # although the swept face IS in the result; the low-level sweep still knows it.
            alt = mk.Revol().Shape(e)
            if not alt.IsNull() and alt.ShapeType() == TopAbs_FACE and P.Contains(alt):
                g = [alt]
                fallback.append(n)
        roles[f"side({n})"] = g
    for n, v in vs.items():
        roles[f"circle_edge({n})"] = [x for x in L(mk.Generated(v)) if x.ShapeType() == TopAbs_EDGE]
    if fallback:
        notes.append(f"Generated() empty in result for {fallback}; resolved via MakeRevol.Revol().Shape(edge)")
    on_axis = r_in <= 0
    exp = {r: 1 for r in roles}
    if on_axis:
        exp["side(inner)"] = 0
        exp["circle_edge(ib)"] = exp["circle_edge(it)"] = 0
    dH = 1 if (full and not on_axis) else 0
    return OpRun("revolve", "full" if full else "partial", dict(angle=angle, r_in=r_in, r_out=r_out, h=h,
                 top_slant=top_slant), s, None, roles, exp, dH, 1, mk, {"profile": prof}, notes=notes)


# ---------------------------------------------------------------- 2. chamfer

def chamfer(d=3.0, which="lat_a+top_ab", d2=None):
    """Chamfer on block E.  which: lat_a+top_ab | ridge (top_ab + top_cd) | all12."""
    s0, led = block()
    lat_a = led.resolve("E", "lateral_edge", "a")[0]
    top = lambda side: edges_between(led.resolve("E", "side", side)[0], led.resolve("E", "cap", "END")[0])[0]
    sel = {"lat_a+top_ab": {"E.lateral_edge(a)": lat_a, "edge(E.side(a-b),E.cap(END))": top("a-b")},
           "ridge": {"edge(E.side(a-b),E.cap(END))": top("a-b"), "edge(E.side(c-d),E.cap(END))": top("c-d")},
           "all12": {f"e{i}": e for i, e in enumerate(topo.subshapes(s0, TopAbs_EDGE))}}[which]
    mk = BRepFilletAPI_MakeChamfer(s0)
    for e in sel.values():
        if d2 is None:
            mk.Add(d, TopoDS.Edge(e))
        else:  # two-distance chamfer: needs a reference face; use any face adjacent to the edge
            mk.Add(d, d2, TopoDS.Edge(e), TopoDS.Face(_adjacent_face(s0, e)))
    mk.Build()
    if not mk.IsDone():
        raise RuntimeError("chamfer failed")
    s = mk.Shape()
    roles = {f"face(from={n})": faces_in(L(mk.Generated(e))) for n, e in sel.items()}
    for v in topo.subshapes(s0, TopAbs_VERTEX):          # corner patches where >= 3 chamfers meet
        g = faces_in(L(mk.Generated(v)))
        if g:
            roles[f"corner(at={describe(v)})"] = g
    led.propagate("CH", mk, s)
    exp = {r: 1 for r in roles}
    if which == "lat_a+top_ab":
        bexp = base_expect_all(over={("E", "lateral_edge", "a"): 0})
    elif which == "ridge":
        bexp = base_expect_all(over={("E", "cap", "END"): 1 if d < 15 - 1e-9 else 0})
    else:
        bexp = base_expect_all(lateral=0)
    return OpRun("chamfer", which, dict(d=d, which=which, d2=d2), s, s0, roles, exp, 0, 0, mk,
                 {"base": s0}, led, bexp)


def _adjacent_face(shape, edge):
    for f in topo.subshapes(shape, TopAbs_FACE):
        if any(e.IsSame(edge) for e in topo.subshapes(f, TopAbs_EDGE)):
            return f
    raise ValueError("no adjacent face")


# ---------------------------------------------------------------- 3. shell / thick solid

def shell(t=-2.0, openings=("cap(END)",), body="block"):
    """MakeThickSolidByJoin on block E (or a cylinder cup, body='cylinder').  t<0: inward."""
    if body == "block":
        s0, led = block()
    else:
        s0, led = cylinder_body()
    names = {"cap(END)": ("E", "cap", "END"), "side(a-b)": ("E", "side", "a-b")}
    open_faces = {o: led.resolve(*names[o])[0] for o in openings}
    lst = List_TopoDS_Shape()
    for f in open_faces.values():
        lst.Append(f)
    mk = BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidByJoin(s0, lst, t, 1e-3)
    mk.Build()
    if not mk.IsDone():
        raise RuntimeError("shell failed")
    s = mk.Shape()
    roles = {}
    for e in list(led.items):
        if e.shape.ShapeType() != TopAbs_FACE:
            continue
        nm = f"{e.tag.role}({e.tag.source})"
        if nm in open_faces:
            roles[f"rim(opening={nm})"] = faces_in(L(mk.Modified(e.shape)))
        else:
            roles[f"offset(from={nm})"] = faces_in(L(mk.Generated(e.shape)))
    # outward offsets (t > 0) and offsets with no openings create arc-join faces at convex edges / corners:
    # they are Generated(edge) / Generated(vertex).  Name an edge by its two adjacent face references.
    face_tags = [(e.shape, f"{e.tag.role}({e.tag.source})") for e in led.items if e.shape.ShapeType() == TopAbs_FACE]
    for ed in topo.subshapes(s0, TopAbs_EDGE):
        g = faces_in(L(mk.Generated(ed)))
        if g:
            adj = sorted(n for f, n in face_tags if any(x.IsSame(ed) for x in topo.subshapes(f, TopAbs_EDGE)))
            roles[f"join(from=edge({','.join(adj)}))"] = g
    for v in topo.subshapes(s0, TopAbs_VERTEX):
        g = faces_in(L(mk.Generated(v)))
        if g:
            roles[f"join(at={describe(v)})"] = g
    # follow_generated: with NO openings MakeThickSolid degenerates to an offset solid whose faces are
    # reachable only through Generated() (see shell_void for a real hollow)
    led.propagate("SH", mk, s, follow_generated=True)
    exp = {r: 1 for r in roles}
    dS = 0
    bexp = base_expect_all(over={names[o]: 1 for o in openings}) if body == "block" else \
        {k: 1 for k in _cyl_tags()}
    notes = [{"derived_lateral_edges": derived_lateral_edges(led)}] if body == "block" else []
    return OpRun("shell", f"{body}:{'+'.join(openings) or 'no_openings'}", dict(t=t, openings=list(openings), body=body),
                 s, s0, roles, exp, 0, dS, mk, {"base": s0}, led, bexp, notes)


def shell_void(t=2.0):
    """Closed hollow (internal void): offset the block inward by t, then cut the offset from the block.

    Roles: void(from=E.x) = image of Generated(E.x) under the offset, carried through the cut.
    Expected: dS = +1 (void shell), dH = 0.
    """
    s0, led = block()
    off = BRepOffsetAPI_MakeOffsetShape()
    off.PerformByJoin(s0, -t, 1e-3)
    if not off.IsDone():
        raise RuntimeError("offset failed")
    inner = off.Shape()
    for e in list(led.items):
        if e.shape.ShapeType() == TopAbs_FACE:
            led.add(Tag("V", "void", f"{e.tag.role}({e.tag.source})"), faces_in(L(off.Generated(e.shape))))
    cut = BRepAlgoAPI_Cut(s0, inner)
    s = cut.Shape()
    led.propagate("V", cut, s)
    roles = {f"void(from=E.{t_.source})": led.resolve("V", "void", t_.source, ("at_least", 0))
             for t_ in led.tags() if t_.feature == "V"}
    exp = {r: 1 for r in roles}
    return OpRun("shell", "block:closed_void(offset+cut)", dict(t=t), s, s0, roles, exp, 0, 1, cut,
                 {"base": s0, "tool": inner}, led, base_expect_all())


def cylinder_body(r=15.0, h=20.0):
    led = Ledger2()
    c = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r)).Edge()
    f = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(c).Wire()).Face()
    mk = BRepPrimAPI_MakePrism(f, gp_Vec(0, 0, h))
    mk.Build()
    led.add(Tag("E", "cap", "START"), [mk.FirstShape()])
    led.add(Tag("E", "cap", "END"), [mk.LastShape()])
    led.add(Tag("E", "side", "circle"), L(mk.Generated(c)))
    return mk.Shape(), led


def _cyl_tags():
    return [("E", "cap", "START"), ("E", "cap", "END"), ("E", "side", "circle")]


# ---------------------------------------------------------------- 4. loft

def loft(s1=16.0, z1=15.0, ruled=False, third="none", twist=0.0):
    """ThruSections: square 20 at z=0 -> square s1 (rotated `twist` deg) at z1 [-> third section at 2*z1].

    third: none | square | circle (circle has 1 edge -> OCCT splits edges to make sections compatible).
    """
    def square(size, z, rot=0.0):
        c, hs = 10.0, size / 2
        pts = {}
        for nm, (x, y) in zip("abcd", ((-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs))):
            ca, sa = math.cos(deg(rot)), math.sin(deg(rot))
            pts[nm] = (c + ca * x - sa * y, c + sa * x + ca * y, z)
        return named_polygon(pts, make_face=False)
    w0, e0, _ = square(20, 0)
    w1, e1, _ = square(s1, z1, twist)
    secs = [("s0", w0, e0), ("s1", w1, e1)]
    if third == "square":
        w2, e2, _ = square(12, 2 * z1)
        secs.append(("s2", w2, e2))
    elif third == "circle":
        ce = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(10, 10, 2 * z1), gp_Dir(0, 0, 1)), 6)).Edge()
        secs.append(("s2", BRepBuilderAPI_MakeWire(ce).Wire(), {"circle": ce}))
    mk = BRepOffsetAPI_ThruSections(True, ruled, 1e-6)
    for _, w, _ in secs:
        mk.AddWire(w)
    mk.Build()
    if not mk.IsDone():
        raise RuntimeError("loft failed")
    s = mk.Shape()
    roles = {"cap(START)": [mk.FirstShape()], "cap(END)": [mk.LastShape()]}
    for sn, _, es in secs:
        for n, e in es.items():
            roles[f"side(from={sn}.{n})"] = faces_in(L(mk.Generated(e)))
    spans = len(secs) - 1 if ruled else 1
    exp = {r: 1 for r in roles}
    for r in roles:
        if r.startswith("side"):
            exp[r] = spans
    if third == "circle":
        # the circle is split to match 4 edges and edge b-c is split once more: declared as at_least
        for r in roles:
            if r.startswith("side"):
                exp[r] = None   # None = 'at_least(1)', checked separately
    return OpRun("loft", f"{len(secs)}sec{'-ruled' if ruled else ''}{'-' + third if third != 'none' else ''}",
                 dict(s1=s1, z1=z1, ruled=ruled, third=third, twist=twist), s, None, roles, exp, 0, 1, mk,
                 {s: w for s, w, _ in secs})


# ---------------------------------------------------------------- 5. sweep

def _spine(kind, length=40.0, bend_r=20.0):
    if kind == "closed":
        e = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), 30)).Edge()
        return BRepBuilderAPI_MakeWire(e).Wire()
    p0, p1 = gp_Pnt(0, 0, 0), gp_Pnt(0, 0, length)
    mw = BRepBuilderAPI_MakeWire()
    mw.Add(BRepBuilderAPI_MakeEdge(p0, p1).Edge())
    arc = GC_MakeArcOfCircle(p1, gp_Vec(0, 0, 1), gp_Pnt(bend_r, 0, length + bend_r)).Value()
    mw.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
    return mw.Wire()


def wire_edges(w):
    """Edges in wire order -- take them FROM the wire (MakeWire may copy input edges)."""
    out, wx = [], BRepTools_WireExplorer(w)
    while wx.More():
        out.append(wx.Current())
        wx.Next()
    return out


def sweep(spine="open", length=40.0, bend_r=20.0, pw=6.0, ph=4.0, profile="rect", builder="pipe"):
    """Sweep a profile along a line+arc spine (open) or a circle (closed).

    profile: rect (named edges a-b.. ) | circle.  builder: pipe (BRepOffsetAPI_MakePipe) | pipeshell.
    """
    sp = _spine(spine, length, bend_r)
    x0 = 30.0 if spine == "closed" else 0.0
    if profile == "rect":
        w, es, _ = named_polygon({"a": (x0 - pw / 2, -ph / 2, 0), "b": (x0 + pw / 2, -ph / 2, 0),
                                  "c": (x0 + pw / 2, ph / 2, 0), "d": (x0 - pw / 2, ph / 2, 0)}, make_face=False)
    else:
        ce = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(x0, 0, 0), gp_Dir(0, 0, 1)), pw / 2)).Edge()
        w, es = BRepBuilderAPI_MakeWire(ce).Wire(), {"circle": ce}
    spine_edges = {f"spine{i}": e for i, e in enumerate(wire_edges(sp))}
    if builder == "pipe":
        mk = BRepOffsetAPI_MakePipe(sp, BRepBuilderAPI_MakeFace(w, True).Face())
        mk.Build()
    else:
        mk = BRepOffsetAPI_MakePipeShell(sp)
        mk.SetMode(False)   # corrected Frenet
        mk.Add(w)
        mk.Build()
        mk.MakeSolid()
    if not mk.IsDone():
        raise RuntimeError("sweep failed")
    s = mk.Shape()
    P = present_map(s)
    roles = {}
    closed = spine == "closed"
    if not closed:
        roles["cap(START)"] = [mk.FirstShape()]
        roles["cap(END)"] = [mk.LastShape()]
    for n, e in es.items():
        roles[f"side(from={n})"] = faces_in(L(mk.Generated(e)))
        if builder == "pipe":
            for sn, se in spine_edges.items():
                g = mk.Generated(se, e)
                roles[f"side(from={n}, along={sn})"] = [g] if (not g.IsNull() and P.Contains(g)) else []
    exp = {r: 1 for r in roles}
    for n in es:
        exp[f"side(from={n})"] = len(spine_edges)
    dH = 1 if closed else 0
    return OpRun("sweep", f"{builder}:{spine}:{profile}", dict(spine=spine, length=length, bend_r=bend_r, pw=pw,
                 ph=ph, profile=profile, builder=builder), s, None, roles, exp, dH, 1, mk, {"profile": w})


# ---------------------------------------------------------------- 6. draft

def draft(angle=5.0, faces=SIDES):
    """Draft the listed sides of block E about the neutral plane z=0, pull direction +Z."""
    s0, led = block()
    mk = BRepOffsetAPI_DraftAngle(s0)
    pln = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    srcs = {}
    for side in faces:
        f = led.resolve("E", "side", side)[0]
        srcs[side] = f
        mk.Add(TopoDS.Face(f), gp_Dir(0, 0, 1), deg(angle), pln)
        if not mk.AddDone():
            raise RuntimeError(f"draft Add failed on {side}")
    mk.Build()
    if not mk.IsDone():
        raise RuntimeError("draft failed")
    s = mk.Shape()
    roles = {f"drafted(from=E.side({k}))": faces_in(L(mk.Generated(f))) for k, f in srcs.items()}
    roles.update({f"modified(E.side({k}))": faces_in(L(mk.Modified(f))) for k, f in srcs.items()})
    # spike-01 ledger (Modified + presence only) vs Ledger2(follow_generated)
    naive = Ledger2()
    naive.items = list(led.items)
    refs_Ledger = __import__("refs").Ledger
    refs_Ledger.propagate(naive, "DR", mk, s)
    led.propagate("DR", mk, s, follow_generated=True)
    # Draft gives NO edge/vertex history: lateral edges are re-derived from the drafted face references
    for v, (s1, s2) in ADJ.items():
        f1, f2 = led.entries("E", "side", s1), led.entries("E", "side", s2)
        roles[f"derived lateral_edge({v}) = edges_between(E.side({s1}), E.side({s2}))"] = \
            edges_between(f1[0].shape, f2[0].shape) if (len(f1) == 1 and len(f2) == 1) else []
    exp = {r: (0 if r.startswith("modified") else 1) for r in roles}
    bexp = base_expect_all(lateral=0)
    op = OpRun("draft", f"{len(faces)}sides", dict(angle=angle, faces=list(faces)), s, s0, roles, exp, 0, 0, mk,
               {"base": s0}, led, bexp)
    op.notes.append({"spike01_ledger_counts": {str(t): naive.count(t.feature, t.role, t.source) for t in led.tags()}})
    op.notes.append({"derived_lateral_edges": derived_lateral_edges(led)})
    return op


# ---------------------------------------------------------------- 7. patterns

def _transformed(shape, trsf):
    tr = BRepBuilderAPI_Transform(shape, trsf, False)     # copy=False: instances share the TShape
    return tr


def _boolean_list(kind, arg, tools):
    """Boolean with each tool as a SEPARATE tool argument (not one compound): overlapping instances are
    legal between tools, but a compound with overlapping members is a self-interfering argument."""
    op = BRepAlgoAPI_Cut() if kind == "cut" else BRepAlgoAPI_Fuse()
    a, t = List_TopoDS_Shape(), List_TopoDS_Shape()
    a.Append(arg)
    for x in tools:
        t.Append(x)
    op.SetArguments(a)
    op.SetTools(t)
    op.Build()
    if not op.IsDone():
        raise RuntimeError(f"boolean {kind} failed")
    return op


def _compound(shapes):
    c, bb = TopoDS_Compound(), BRep_Builder()
    bb.MakeCompound(c)
    for x in shapes:
        bb.Add(c, x)
    return c


def pattern_holes(kind="linear", n=3, pitch=12.0, d=6.0, radius=10.0, combine="tool_list"):
    """Hole tool patterned n times and cut from a body.

    linear: block E, holes along X starting at x=8, y=15.  circular: disc r=20 h=5, holes at `radius`.
    combine: tool_list (one boolean, each instance a separate tool) | compound (one boolean, instances
    packed in ONE compound tool -- negative control) | sequential (one cut per instance).
    Instance k of the tool is a placed copy (shared TShape, own Location) of the seed tool.
    """
    if kind == "linear":
        s0, led = block()
        seed_ax = gp_Ax2(gp_Pnt(8, 15, -1), gp_Dir(0, 0, 1))
        hz = 22
    else:
        s0, led = cylinder_body(20.0, 5.0)
        seed_ax = gp_Ax2(gp_Pnt(radius, 0, -1), gp_Dir(0, 0, 1))
        hz = 7
    cm = BRepPrimAPI_MakeCylinder(seed_ax, d / 2, hz)
    cm.Build()
    seed, seed_wall = cm.Shape(), cm.Cylinder().LateralFace()
    inst = []
    for k in range(n):
        t = gp_Trsf()
        if kind == "linear":
            t.SetTranslation(gp_Vec(k * pitch, 0, 0))
        else:
            t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 2 * math.pi * k / n)
        tr = _transformed(seed, t)
        inst.append((tr.Shape(), tr.ModifiedShape(seed_wall)))
    s, algo = s0, None
    if combine in ("tool_list", "compound"):
        for k, (_, w) in enumerate(inst):
            led.add(Tag("P", "wall", f"instance{k}"), [w])
        if combine == "compound":
            algo = BRepAlgoAPI_Cut(s0, _compound([sh for sh, _ in inst]))
        else:
            algo = _boolean_list("cut", s0, [sh for sh, _ in inst])
        s = algo.Shape()
        led.propagate("P", algo, s)
        audit = {"base": s0, **{f"tool{k}": sh for k, (sh, _) in enumerate(inst)}}
    else:
        for k, (sh, w) in enumerate(inst):
            led.add(Tag("P", "wall", f"instance{k}"), [w])    # tag each tool just before its own cut
            algo = BRepAlgoAPI_Cut(s, sh)
            s = algo.Shape()
            led.propagate(f"P{k}", algo, s)
        audit = {}
    roles = {f"instance({k}).wall": led.resolve("P", "wall", f"instance{k}", ("at_least", 0)) for k in range(n)}
    exp = {r: 1 for r in roles}
    # declared intent: holes are disjoint and fully inside the body
    dH = n
    bexp = base_expect_all() if kind == "linear" else {k: 1 for k in _cyl_tags()}
    return OpRun("pattern", f"{kind}-holes:{combine}", dict(kind=kind, n=n, pitch=pitch, d=d, radius=radius,
                 combine=combine), s, s0, roles, exp, dH, 0, algo, audit, led, bexp)


def pattern_bosses(n=3, pitch=12.0, d=6.0, combine="tool_list"):
    """Linear pattern of cylindrical bosses fused on E.cap(END) in one fuse (tool_list | compound)."""
    s0, led = block()
    cm = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(8, 15, 20), gp_Dir(0, 0, 1)), d / 2, 5)
    cm.Build()
    seed, seed_side = cm.Shape(), cm.Cylinder().LateralFace()
    seed_top = cm.Cylinder().TopFace()
    insts = []
    for k in range(n):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(k * pitch, 0, 0))
        tr = _transformed(seed, t)
        insts.append(tr.Shape())
        led.add(Tag("B", "side", f"instance{k}"), [tr.ModifiedShape(seed_side)])
        led.add(Tag("B", "top", f"instance{k}"), [tr.ModifiedShape(seed_top)])
    algo = BRepAlgoAPI_Fuse(s0, _compound(insts)) if combine == "compound" else _boolean_list("fuse", s0, insts)
    s = algo.Shape()
    led.propagate("B", algo, s)
    roles = {}
    for k in range(n):
        roles[f"instance({k}).side"] = led.resolve("B", "side", f"instance{k}", ("at_least", 0))
        roles[f"instance({k}).top"] = led.resolve("B", "top", f"instance{k}", ("at_least", 0))
    exp = {r: 1 for r in roles}
    return OpRun("pattern", f"linear-bosses:{combine}", dict(n=n, pitch=pitch, d=d, combine=combine), s, s0, roles,
                 exp, 0, 0, algo, {"base": s0, **{f"tool{k}": x for k, x in enumerate(insts)}}, led, base_expect_all())


# ---------------------------------------------------------------- 8. mirror

def l_body(fid="E"):
    """Asymmetric L-shaped prism (so a mirror image is distinguishable): profile in XY, extruded +Z 10."""
    pts = {"o": (0, 0, 0), "p": (30, 0, 0), "q": (30, 8, 0), "r": (8, 8, 0), "s": (8, 25, 0), "t": (0, 25, 0)}
    f, es, vs = named_polygon(pts)
    mk = BRepPrimAPI_MakePrism(f, gp_Vec(0, 0, 10))
    mk.Build()
    led = Ledger2()
    led.add(Tag(fid, "cap", "START"), [mk.FirstShape()])
    led.add(Tag(fid, "cap", "END"), [mk.LastShape()])
    for n, e in es.items():
        led.add(Tag(fid, "side", n), L(mk.Generated(e)))
    return mk.Shape(), led, list(es)


def mirror(gap=0.0, join=True, clean=False):
    """Mirror the L body across the plane x = 30 + gap and (optionally) fuse with the original.

    gap = 0: the mirror plane contains E.side(p-q) -> the two halves touch along it.
    gap > 0: disjoint -> 2 solids.  gap < 0: the halves overlap.
    clean: run ShapeUpgrade_UnifySameDomain (build123d settings) after the fuse.
    """
    s0, led, side_names = l_body()
    t = gp_Trsf()
    t.SetMirror(gp_Ax2(gp_Pnt(30 + gap, 0, 0), gp_Dir(1, 0, 0)))
    tr = BRepBuilderAPI_Transform(s0, t, True)
    img = tr.Shape()
    for e in list(led.items):
        led.add(Tag("M", e.tag.role, e.tag.source), [tr.ModifiedShape(e.shape)])
    s, algo, audit = img, tr, {"base": s0}
    if join:
        algo = BRepAlgoAPI_Fuse(s0, img)
        s = algo.Shape()
        led.propagate("J", algo, s)
        audit = {"base": s0, "image": img}
    if clean:
        u = ShapeUpgrade_UnifySameDomain(s, True, True, True)
        u.AllowInternalEdges(False)
        u.Build()
        fused = s
        s = u.Shape()
        algo = HistoryAdapter(u.History())
        audit = {"fused": fused}
        led.propagate("clean", algo, s)
    roles = {}
    for nm in ["cap(START)", "cap(END)"] + [f"side({n})" for n in side_names]:
        r, src = nm[:-1].split("(")
        roles[f"image(of=E.{nm})"] = led.resolve("M", r, src, ("at_least", 0))
    exp = {r: 1 for r in roles}
    if join and gap <= 0:
        exp["image(of=E.side(p-q))"] = 0 if gap == 0 else 1
    bexp = {(t_.feature, t_.role, t_.source): 1 for t_ in led.tags() if t_.feature == "E"}
    if join and gap == 0:
        bexp[("E", "side", "p-q")] = 0
    s_count = 1 if (join and gap <= 0) else 2
    dS = s_count - 1 + (0 if join else 0)
    return OpRun("mirror", f"{'fuse' if join else 'image'}{'+clean' if clean else ''}",
                 dict(gap=gap, join=join, clean=clean), s, s0, roles, exp, 0, dS, algo, audit, led, bexp)


# ---------------------------------------------------------------- registry of default models

DEFAULTS = {
    "revolve.partial": lambda: revolve(180),
    "revolve.full": lambda: revolve(360),
    "revolve.full_on_axis": lambda: revolve(360, r_in=0.0),
    "chamfer.two_edges": lambda: chamfer(3.0),
    "chamfer.all12": lambda: chamfer(2.0, "all12"),
    "chamfer.two_distances": lambda: chamfer(3.0, d2=1.0),
    "shell.open_top": lambda: shell(-2.0),
    "shell.open_top_outward": lambda: shell(2.0),
    "shell.two_openings": lambda: shell(-2.0, ("cap(END)", "side(a-b)")),
    "shell.no_openings": lambda: shell(-2.0, ()),
    "shell.closed_void": lambda: shell_void(2.0),
    "shell.cylinder_cup": lambda: shell(-2.0, ("cap(END)",), body="cylinder"),
    "loft.2sec": lambda: loft(),
    "loft.3sec_ruled": lambda: loft(ruled=True, third="square"),
    "loft.square_to_circle": lambda: loft(third="circle"),
    "sweep.pipe_open": lambda: sweep(),
    "sweep.pipeshell_open": lambda: sweep(builder="pipeshell"),
    "sweep.pipe_closed": lambda: sweep("closed"),
    "sweep.pipe_closed_circle": lambda: sweep("closed", profile="circle"),
    "draft.4sides": lambda: draft(5.0),
    "pattern.linear_holes": lambda: pattern_holes("linear"),
    "pattern.circular_holes": lambda: pattern_holes("circular", n=6),
    "pattern.linear_holes_seq": lambda: pattern_holes("linear", combine="sequential"),
    "pattern.linear_bosses": lambda: pattern_bosses(),
    "pattern.overlap_tool_list": lambda: pattern_holes("linear", n=2, pitch=5),
    "pattern.overlap_compound(neg)": lambda: pattern_holes("linear", n=2, pitch=5, combine="compound"),
    "mirror.fuse": lambda: mirror(0.0),
    "mirror.disjoint": lambda: mirror(5.0),
    "mirror.fuse_clean": lambda: mirror(0.0, clean=True),
}
