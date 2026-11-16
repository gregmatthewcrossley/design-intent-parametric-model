"""Core and trusted operations (dsl.md §3.1, §3.3, §4.3), all on raw OCP so history is available.

Every op declares three things (spike 02 §2, §6; dsl.md §4.3):

* **roles** - the structural references it creates, e.g. `E.cap(START)`,
  `E.side(mount)`, `F.blend(<edge ref>)`, `M.image(<tag>)`.  Each op class has accessor
  methods returning lazy `Ref`s; the role table is in the class docstring.
* **expected ΔH / ΔS / volume sign** (`Expect`), computed from how the op interacts with
  existing geometry where the spikes showed that matters (revolve vs. axis, mirror
  disjoint vs. touching, holes crossing holes).  Authors may override with
  `expect={"dH": ...}` when they *intend* an interaction.
* **failure classes** - loud (raises), silently invalid (BRepCheck), silently wrong but
  valid (only ΔS/volume/cardinality catch it).  Recorded on the class for reports.

The ledger is carried through every op with that op's own maker; `IsDeleted` is never
trusted.  Booleans always pass tools as a list.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax1

from . import kernel as K
from .errors import InteractionError, KernelError, SketchError
from .expr import ev
from .kernel import Vec3
from .program import StepOut
from .refs import EdgesBetween, Ref, Tag, at_least, one

LOUD = "fails loudly (kernel raises)"
SILENT_INVALID = "silently invalid (caught by BRepCheck/Euler)"
SILENT_WRONG = "silently wrong but valid (caught only by ΔS/volume/cardinality)"

TOUCH_TOL = 1e-6   # mm: shapes closer than this are considered touching


# ---------------------------------------------------------------- expectations

@dataclass(frozen=True)
class Expect:
    """Expected topological deltas of one feature (dsl.md §5.3) plus the volume sign (§4.3).

    volume_sign: '+' adds material, '-' removes, '0' unchanged (rigid), 'any' nonzero.
    """
    dH: int
    dS: int
    volume_sign: str
    why_dH: str = ""
    why_dS: str = ""

    def override(self, over) -> "Expect":
        if not over:
            return self
        over = dict(over)
        why = over.pop("why", "declared by author")
        return Expect(over.get("dH", self.dH), over.get("dS", self.dS), over.get("volume_sign", self.volume_sign),
                      why if "dH" in over else self.why_dH, why if "dS" in over else self.why_dS)


# ---------------------------------------------------------------- base

class Feature:
    """Base class.  Subclasses are frozen dataclasses with `id` and `tags` first."""
    op_name = "?"
    failure_classes: tuple = ()
    lowered_from: str | None = None

    def apply(self, ctx) -> StepOut:  # pragma: no cover - abstract
        raise NotImplementedError

    def ref(self, role: str, source: str | None = None, card=None, kind: str | None = None) -> Ref:
        return Ref(self.id, role, source, card or one(), kind=kind)

    def created(self, role: str, card=None) -> Ref:
        """All sub-shapes of a role regardless of source (`F.created()` in dsl.md §3.4)."""
        return Ref(self.id, role, None, card or at_least(1), any_source=True)


def _resolve_edges(ctx, edges) -> list[tuple[str, object]]:
    """Resolve one or more edge references -> [(ref string, edge)]."""
    refs = edges if isinstance(edges, (list, tuple)) else [edges]
    out = []
    for r in refs:
        for e in ctx.resolve(r):
            if e.ShapeType() != TopAbs_EDGE:
                raise SketchError(f"{r} resolved to a non-edge")
            out.append((str(r), e))
    return out


def _combine(ctx, fid: str, mode: str, tool, expect_new: Expect, over) -> tuple[object, Expect]:
    """Shared new/add/cut logic for creator ops (extrude, revolve).

    The tool's tags are already in the ledger; this runs the boolean (tool as a list),
    propagates the ledger, and checks the intended interaction:
    'add' must touch the body; 'cut' must overlap it (else it removes nothing).
    """
    if mode == "new":
        if ctx.shape is not None:
            raise InteractionError("mode='new' but a body already exists (v0 designs are single-body)",
                                   details={"hint": "use mode='add' or mode='cut'"})
        return tool, expect_new.override(over)
    if ctx.shape is None:
        raise InteractionError(f"mode={mode!r} needs an existing body")
    if mode == "add":
        if K.distance(ctx.shape, tool) > TOUCH_TOL:
            raise InteractionError("add does not touch the existing body (it would create a second solid)",
                                   invariant="interaction: add must touch", expected="distance 0",
                                   got=f"{K.distance(ctx.shape, tool):.6g} mm")
        algo = K.boolean("fuse", ctx.shape, [tool])
        exp = Expect(0, 0, "+", "fuse of a touching body: no new tunnel unless declared",
                     "joins the existing shell")
    elif mode == "cut":
        if K.common_volume(ctx.shape, tool) <= 1e-9:
            raise InteractionError("cut tool does not overlap the body (it would remove nothing)",
                                   invariant="interaction: cut must overlap")
        algo = K.boolean("cut", ctx.shape, [tool])
        exp = Expect(0, 0, "-", "cut: declare dH if it makes a tunnel", "cut keeps one shell unless declared")
    else:
        raise ValueError(f"mode must be new|add|cut, got {mode!r}")
    shape = algo.Shape()
    ctx.ledger.propagate(fid, algo, shape)
    return shape, exp.override(over)


# ---------------------------------------------------------------- extrude

@dataclass(frozen=True)
class Extrude(Feature):
    """Planar-profile extrude (dsl.md §3.1).  `BRepPrimAPI_MakePrism`.

    Roles (spike 01 §2.1):
      cap(START|END)           FirstShape / LastShape                 one()
      side(<edge name>)        Generated(sketch edge)                 one()
      lateral_edge(<pt name>)  Generated(sketch vertex)               one()
    symmetric=True extrudes distance/2 each side of the sketch plane.
    mode: new | add (fuse) | cut.  ΔH=0, ΔS=+1 for new; add/cut: 0/0 unless declared.
    """
    id: str
    tags: tuple
    profile: object
    distance: object
    symmetric: bool = False
    mode: str = "new"
    expect: dict | None = None
    op_name = "extrude"
    failure_classes = (LOUD, SILENT_WRONG)

    def cap(self, which: str) -> Ref:
        return self.ref("cap", which.upper(), kind="face")

    def side(self, edge: str) -> Ref:
        return self.ref("side", edge, kind="face")

    def lateral_edge(self, point: str, card=None) -> Ref:
        return self.ref("lateral_edge", point, card, kind="edge")

    def apply(self, ctx) -> StepOut:
        d = float(ev(self.distance, ctx))
        if d <= 0:
            raise SketchError(f"extrude distance must be > 0, got {d}")
        n = self.profile.plane.normal.unit()
        shift = n * (-d / 2) if self.symmetric else None
        sp = self.profile.evaluate(ctx, shift)
        mk = BRepPrimAPI_MakePrism(sp.face, (sp.plane.normal * d).vec())
        mk.Build()
        if not mk.IsDone():
            raise KernelError("MakePrism failed")
        led = ctx.ledger
        led.add(Tag(self.id, "cap", "START"), [mk.FirstShape()])
        led.add(Tag(self.id, "cap", "END"), [mk.LastShape()])
        for name, e in sp.edges.items():
            led.add(Tag(self.id, "side", name), [f for f in K.occ_list(mk.Generated(e)) if f.ShapeType() == TopAbs_FACE])
        for name, v in sp.vertices.items():
            led.add(Tag(self.id, "lateral_edge", name),
                    [x for x in K.occ_list(mk.Generated(v)) if x.ShapeType() == TopAbs_EDGE])
        shape, exp = _combine(ctx, self.id, self.mode, mk.Shape(),
                              Expect(0, 1, "+", "single-loop planar profile: no tunnel", "new solid"), self.expect)
        return StepOut(shape, exp, op=f"extrude[{self.mode}]",
                       detail={"distance": d, "symmetric": self.symmetric, "profile_area": abs(sp.signed_area)})


# ---------------------------------------------------------------- revolve

@dataclass(frozen=True)
class Revolve(Feature):
    """Planar-profile revolve (dsl.md §3.1: must not cross its own axis).  `BRepPrimAPI_MakeRevol`.

    axis: two profile point names, or two (u, v) pairs, in the profile's plane.
    Roles (spike 02 §1.1, §6):
      cap(START|END)          FirstShape/LastShape   one(); absent on a full revolve
      side(<edge name>)       Generated(edge); full-revolve fallback Revol().Shape(edge)   one()
      circle_edge(<pt name>)  Generated(vertex)      one(); none for a point on the axis
    Expected ΔH: +1 for a full revolve of a region disjoint from the axis, else 0.  ΔS=+1 (new).
    """
    id: str
    tags: tuple
    profile: object
    axis: tuple
    angle: object = 360.0
    mode: str = "new"
    expect: dict | None = None
    op_name = "revolve"
    failure_classes = (LOUD, SILENT_INVALID)

    def cap(self, which: str) -> Ref:
        return self.ref("cap", which.upper(), kind="face")

    def side(self, edge: str) -> Ref:
        return self.ref("side", edge, kind="face")

    def circle_edge(self, point: str) -> Ref:
        return self.ref("circle_edge", point, kind="edge")

    def apply(self, ctx) -> StepOut:
        sp = self.profile.evaluate(ctx)
        a, b = self.axis
        pa = sp.points2d[a] if isinstance(a, str) else tuple(map(float, ev(a, ctx)))
        pb = sp.points2d[b] if isinstance(b, str) else tuple(map(float, ev(b, ctx)))
        o3, b3 = sp.plane.to3d(*pa), sp.plane.to3d(*pb)
        axis_dir = (b3 - o3).unit()
        # side test in 2D: signed distance of each profile point from the axis line
        du, dv = pb[0] - pa[0], pb[1] - pa[1]
        nrm = math.hypot(du, dv)
        sd = {n: ((du * (p[1] - pa[1]) - dv * (p[0] - pa[0])) / nrm) for n, p in sp.points2d.items()}
        if min(sd.values()) < -1e-9 and max(sd.values()) > 1e-9:
            raise SketchError("revolve profile crosses its axis (dsl.md §3.1)", invariant="profile vs axis")
        on_axis = {n for n, s in sd.items() if abs(s) <= 1e-9}
        on_axis_edges = {name for name, p, q in self.profile.edge_list() if p in on_axis and q in on_axis}
        angle = float(ev(self.angle, ctx))
        full = angle >= 360.0 - 1e-9
        ax = gp_Ax1(o3.pnt(), axis_dir.dir())
        mk = BRepPrimAPI_MakeRevol(sp.face, ax) if full else BRepPrimAPI_MakeRevol(sp.face, ax, math.radians(angle))
        mk.Build()
        if not mk.IsDone():
            raise KernelError("MakeRevol failed")
        tool = mk.Shape()
        present = K.presence_map(tool)
        led = ctx.ledger
        fallbacks = []
        if not full:
            led.add(Tag(self.id, "cap", "START"), [mk.FirstShape()])
            led.add(Tag(self.id, "cap", "END"), [mk.LastShape()])
        for name, e in sp.edges.items():
            g = [f for f in K.occ_list(mk.Generated(e)) if f.ShapeType() == TopAbs_FACE and present.Contains(f)]
            if not g and full and name not in on_axis_edges:
                alt = mk.Revol().Shape(e)   # spike 02 §1.1 workaround
                if not alt.IsNull() and alt.ShapeType() == TopAbs_FACE and present.Contains(alt):
                    g = [alt]
                    fallbacks.append(name)
            led.add(Tag(self.id, "side", name), g)
        for name, v in sp.vertices.items():
            led.add(Tag(self.id, "circle_edge", name),
                    [x for x in K.occ_list(mk.Generated(v)) if x.ShapeType() == TopAbs_EDGE and present.Contains(x)])
        dH = 1 if (full and not on_axis_edges) else 0
        why = ("full revolve of a region disjoint from the axis" if dH else
               "partial revolve" if not full else "full revolve of a region touching the axis")
        shape, exp = _combine(ctx, self.id, self.mode, tool, Expect(dH, 1, "+", why, "new solid"), self.expect)
        return StepOut(shape, exp, op=f"revolve[{self.mode}]",
                       detail={"angle": angle, "full": full, "revol_fallback": fallbacks})


# ---------------------------------------------------------------- fillet / chamfer

@dataclass(frozen=True)
class Fillet(Feature):
    """Constant-radius fillet: trusted primitive (dsl.md §4.3).  `BRepFilletAPI_MakeFillet`.

    Roles: blend(<edge ref>) = Generated(edge), one face per input edge;
           corner = Generated(vertex) where blends meet (set-level role; untested in spikes).
    ΔH=0, ΔS=0, volume changes (sign depends on convexity).  IsDeleted is wrong here.
    """
    id: str
    tags: tuple
    edges: object
    radius: object
    op_name = "fillet"
    failure_classes = (LOUD, SILENT_INVALID)

    def blend(self, of=None, card=None) -> Ref:
        if of is None:
            return self.created("blend", card)
        return self.ref("blend", str(of), card or at_least(1), kind="face")

    def apply(self, ctx) -> StepOut:
        r = float(ev(self.radius, ctx))
        edges = _resolve_edges(ctx, self.edges)
        mk = BRepFilletAPI_MakeFillet(ctx.shape)
        for _, e in edges:
            mk.Add(r, TopoDS.Edge(e))
        mk.Build()
        if not mk.IsDone():
            raise KernelError(f"fillet r={r} failed on {len(edges)} edge(s)")
        shape = mk.Shape()
        present = K.presence_map(shape)
        for src, e in edges:
            ctx.ledger.add(Tag(self.id, "blend", src),
                           [f for f in K.occ_list(mk.Generated(e)) if f.ShapeType() == TopAbs_FACE and present.Contains(f)])
        _tag_corners(ctx, self.id, mk, edges, present)
        ctx.ledger.propagate(self.id, mk, shape)
        return StepOut(shape, Expect(0, 0, "any", "fillet: no tunnel", "fillet: one shell"),
                       detail={"radius": r, "edges": len(edges)})


@dataclass(frozen=True)
class Chamfer(Feature):
    """Equal-distance chamfer: trusted primitive.  `BRepFilletAPI_MakeChamfer`.

    Roles (spike 02 §1.2): face(<edge ref>) = Generated(edge); corner = Generated(vertex)
    where >= 3 chamfers meet.  ΔH=0, ΔS=0.  Overreach raises (loud).
    """
    id: str
    tags: tuple
    edges: object
    distance: object
    op_name = "chamfer"
    failure_classes = (LOUD,)

    def face(self, of=None, card=None) -> Ref:
        if of is None:
            return self.created("face", card)
        return self.ref("face", str(of), card or at_least(1), kind="face")

    def apply(self, ctx) -> StepOut:
        d = float(ev(self.distance, ctx))
        edges = _resolve_edges(ctx, self.edges)
        mk = BRepFilletAPI_MakeChamfer(ctx.shape)
        for _, e in edges:
            mk.Add(d, TopoDS.Edge(e))
        mk.Build()
        if not mk.IsDone():
            raise KernelError(f"chamfer d={d} failed")
        shape = mk.Shape()
        present = K.presence_map(shape)
        for src, e in edges:
            ctx.ledger.add(Tag(self.id, "face", src),
                           [f for f in K.occ_list(mk.Generated(e)) if f.ShapeType() == TopAbs_FACE and present.Contains(f)])
        _tag_corners(ctx, self.id, mk, edges, present)
        ctx.ledger.propagate(self.id, mk, shape)
        return StepOut(shape, Expect(0, 0, "any", "chamfer: no tunnel", "chamfer: one shell"),
                       detail={"distance": d, "edges": len(edges)})


def _tag_corners(ctx, fid, mk, edges, present):
    seen = K.ShapeMap()
    for _, e in edges:
        for v in K.subshapes(e, TopAbs_VERTEX):
            if seen.Contains(v):
                continue
            seen.Add(v)
            g = [f for f in K.occ_list(mk.Generated(v)) if f.ShapeType() == TopAbs_FACE and present.Contains(f)]
            if g:
                ctx.ledger.add(Tag(fid, "corner", None), g)


# ---------------------------------------------------------------- rigid transforms and mirror

@dataclass(frozen=True)
class Transform(Feature):
    """Rigid motion of the whole body (dsl.md §3.3).  translate=(x,y,z); rotate=(origin, axis, deg).

    No new roles; every tag is carried through `BRepBuilderAPI_Transform.Modified`.
    ΔH=0, ΔS=0, volume unchanged.
    """
    id: str
    tags: tuple
    translate: object = None
    rotate: object = None
    op_name = "transform"
    failure_classes = ()

    def apply(self, ctx) -> StepOut:
        from OCP.gp import gp_Trsf
        t = gp_Trsf()
        if self.rotate is not None:
            o, axis, deg = ev(self.rotate, ctx)
            t = K.trsf_rotate(_v(o), _v(axis), float(deg))
        if self.translate is not None:
            tt = K.trsf_translate(_v(ev(self.translate, ctx)))
            t = tt.Multiplied(t)
        mk = K.transform(ctx.shape, t, True)
        shape = mk.Shape()
        ctx.ledger.propagate(self.id, mk, shape)
        return StepOut(shape, Expect(0, 0, "0", "rigid motion", "rigid motion"))


def _v(x) -> Vec3:
    return x if isinstance(x, Vec3) else Vec3(*map(float, x))


@dataclass(frozen=True)
class Mirror(Feature):
    """Mirror the body across a plane and fuse the image with it (dsl.md §3.3).

    Roles (spike 02 §1.8): image(<tag>) = Transform.ModifiedShape(original), carried
    through the fuse.  A reference lying on the mirror plane vanishes when the halves touch.
    ΔS from interaction: +1 if the image is disjoint, else 0.  ΔH=0 unless declared.
    clean=True runs UnifySameDomain afterwards, history-chained, so coplanar halves merge
    and the ledger records `merged` events (spike 02 §4).
    """
    id: str
    tags: tuple
    origin: object
    normal: object
    clean: bool = True
    expect: dict | None = None
    op_name = "mirror"
    failure_classes = (SILENT_WRONG,)

    def image(self, of, card=None) -> Ref:
        key = str(of.tag) if isinstance(of, Ref) else str(of)
        return Ref(self.id, "image", key, card or one(), kind=getattr(of, "kind", None))

    def apply(self, ctx) -> StepOut:
        o, n = _v(ev(self.origin, ctx)), _v(ev(self.normal, ctx))
        mk = K.transform(ctx.shape, K.trsf_mirror(o, n), True)
        img = mk.Shape()
        for e in list(ctx.ledger.items):
            ctx.ledger.add(Tag(self.id, "image", str(e.tag)), [mk.ModifiedShape(e.shape)])
        gap = K.distance(ctx.shape, img)
        dS = 1 if gap > TOUCH_TOL else 0
        algo = K.boolean("fuse", ctx.shape, [img])
        shape = algo.Shape()
        ctx.ledger.propagate(self.id, algo, shape)
        if self.clean:
            shape = _clean(ctx, self.id, shape)
        exp = Expect(0, dS, "+", "mirror of a body: no new tunnel unless declared",
                     "image disjoint: second shell" if dS else "image touches/overlaps: one shell")
        return StepOut(shape, exp.override(self.expect), op="mirror+fuse" + ("+clean" if self.clean else ""),
                       detail={"gap": gap})


# ---------------------------------------------------------------- clean (UnifySameDomain)

class _HistoryAdapter:
    """Give a BRepTools_History the maker interface the ledger expects."""

    def __init__(self, hist):
        self.h = hist

    def Modified(self, s):
        return self.h.Modified(s)

    def Generated(self, s):
        return self.h.Generated(s)

    def IsDeleted(self, s):
        return self.h.IsRemoved(s)


def _clean(ctx, fid: str, shape):
    u = ShapeUpgrade_UnifySameDomain(shape, True, True, True)
    u.AllowInternalEdges(False)
    u.Build()
    out = u.Shape()
    ctx.ledger.propagate(fid + ":clean", _HistoryAdapter(u.History()), out)
    return out


@dataclass(frozen=True)
class Clean(Feature):
    """Explicit `clean()` (ShapeUpgrade_UnifySameDomain), history-chained (spike 02 §4).

    Merges coplanar/cocylindrical neighbours; references that now alias one face get a
    `merged` event (`error_on_merge` rejects them).  ΔH=0, ΔS=0, volume unchanged.
    """
    id: str
    tags: tuple
    op_name = "clean"

    def apply(self, ctx) -> StepOut:
        u = ShapeUpgrade_UnifySameDomain(ctx.shape, True, True, True)
        u.AllowInternalEdges(False)
        u.Build()
        out = u.Shape()
        ctx.ledger.propagate(self.id, _HistoryAdapter(u.History()), out)
        return StepOut(out, Expect(0, 0, "0", "clean: no topology change in genus", "clean: shells unchanged"))


# ---------------------------------------------------------------- shell (optional trusted primitive)

@dataclass(frozen=True)
class Shell(Feature):
    """Hollow the body leaving `openings` open, wall `thickness` (> 0, inward).
    `BRepOffsetAPI_MakeThickSolid.MakeThickSolidByJoin` with a negative offset.

    Roles (spike 02 §1.3): offset(<tag>) = Generated(face) inner wall per kept face;
    rim(<opening tag>) = Modified(opening): references to the opening continue onto the rim.
    ΔH=0, ΔS=0, volume decreases.  v0 supports inward shells *with* openings only: those
    are byte-deterministic.  Outward / no-opening shells use BRepOffset join mode, which is
    not (spike 02 §3); they are refused here (TODO: offset + cut, fingerprint canonical form).
    Collapse returns invalid/null shapes silently, so the invariants are essential.
    """
    id: str
    tags: tuple
    openings: tuple
    thickness: object
    op_name = "shell"
    failure_classes = (SILENT_INVALID,)

    def offset(self, of) -> Ref:
        return Ref(self.id, "offset", str(of.tag) if isinstance(of, Ref) else str(of), kind="face")

    def rim(self, opening) -> Ref:
        return Ref(opening.feature, opening.role, opening.source, kind="face")

    def apply(self, ctx) -> StepOut:
        t = float(ev(self.thickness, ctx))
        if t <= 0:
            raise SketchError("shell thickness must be > 0 (inward)")
        if not self.openings:
            raise SketchError("v0 shell needs >= 1 opening (closed hollows use non-deterministic join mode)")
        opening_faces = []
        for r in self.openings:
            opening_faces += ctx.resolve(r)
        mk = BRepOffsetAPI_MakeThickSolid()
        mk.MakeThickSolidByJoin(ctx.shape, K.tool_list(opening_faces), -t, 1e-3)
        mk.Build()
        if not mk.IsDone():
            raise KernelError("MakeThickSolid failed")
        shape = mk.Shape()
        if shape.IsNull():
            return StepOut(shape, Expect(0, 0, "-"))
        present = K.presence_map(shape)
        for e in list(ctx.ledger.items):
            if e.shape.ShapeType() == TopAbs_FACE:
                g = [f for f in K.occ_list(mk.Generated(e.shape)) if f.ShapeType() == TopAbs_FACE and present.Contains(f)]
                if g:
                    ctx.ledger.add(Tag(self.id, "offset", str(e.tag)), g)
        ctx.ledger.propagate(self.id, mk, shape)
        return StepOut(shape, Expect(0, 0, "-", "shell with openings: no tunnel", "shell with openings: one shell"),
                       byte_deterministic=True, detail={"thickness": t, "openings": len(opening_faces)})


# ---------------------------------------------------------------- draft (exercises follow-Generated)

@dataclass(frozen=True)
class Draft(Feature):
    """Draft faces by `angle` degrees about a neutral plane, pulling along `pull`.
    `BRepOffsetAPI_DraftAngle` (trusted primitive).

    Spike 02 §1.6: drafted faces come back through **Generated, not Modified**, and there is
    **no edge or vertex history**.  So the ledger is propagated with `follow_generated=True`
    (opt-in, same-type only), and edges must afterwards be named with `edges_between`.
    Roles: none new; the drafted faces keep their creator tags (event `regenerated`).
    ΔH=0, ΔS=0.  Overreach raises (loud).
    """
    id: str
    tags: tuple
    faces: tuple
    angle: object
    neutral_origin: object = (0.0, 0.0, 0.0)
    pull: object = (0.0, 0.0, 1.0)
    op_name = "draft"
    failure_classes = (LOUD,)

    def apply(self, ctx) -> StepOut:
        from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
        from OCP.gp import gp_Pln
        ang = float(ev(self.angle, ctx))
        o, pull = _v(ev(self.neutral_origin, ctx)), _v(ev(self.pull, ctx)).unit()
        mk = BRepOffsetAPI_DraftAngle(ctx.shape)
        pln = gp_Pln(o.pnt(), pull.dir())
        for r in self.faces:
            for f in ctx.resolve(r):
                mk.Add(TopoDS.Face(f), pull.dir(), math.radians(ang), pln)
                if not mk.AddDone():
                    raise KernelError(f"draft Add failed on {r}")
        mk.Build()
        if not mk.IsDone():
            raise KernelError(f"draft {ang} deg failed")
        shape = mk.Shape()
        ctx.ledger.propagate(self.id, mk, shape, follow_generated=True)
        return StepOut(shape, Expect(0, 0, "any", "draft: no tunnel", "draft: one shell"), detail={"angle": ang})


__all__ = ["Draft", "Expect", "Feature", "Extrude", "Revolve", "Fillet", "Chamfer", "Transform", "Mirror", "Clean",
           "Shell", "EdgesBetween", "LOUD", "SILENT_INVALID", "SILENT_WRONG"]
