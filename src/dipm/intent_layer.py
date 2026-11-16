"""Minimal intent layer (dsl.md §4): relations and the `hole` composite.

Relations are **computed from resolved references and parameters at build time**, never
stored as literals (architecture §1 principle 1).  Each placement is a lazy object whose
`evaluate(ctx)` reads the current solid through structural references:

  centered_on(face)                       face area centroid (exact for symmetric faces)
  face_point(face, along=(dir, u), across=(dir, v))
                                          fractional position over the face's extent
  centerline(face, direction)             segment through centered_on(face), spanning the face
    .before(ref, clearance)               ... truncated before a referenced entity
    .midpoint()                           its midpoint (a relation, not a number)
  midpoint(a, b)                          midpoint of two placements
  distribute(along, count, inset)         `count` points evenly along a segment, inset
                                          (a number or (start, end)) from its ends
  linear_pattern / circular_pattern       pattern placements with *declared* indices k

`hole(...)` is a semantic composite (dsl.md §4.2): it lowers to ONE core boolean cut with
a **tool list** (one cylinder per instance, plus a cone per countersink), never a compound.
Instance k is a declared index, not a kernel ordinal (dsl.md §3.4).  Its expected ΔH is
computed from interaction (spike 01 §1.4): +1 per through instance only if its tool is
disjoint from every other hole tool; an undeclared crossing is an error, because a
crossing through-hole changes H by +2, not +1.

Fastener rules (`clearance`, `countersink`, `tool_access_radius`, `edge_distance`) are a
v0 stand-in for a `fasteners` rule pack (architecture §4.6); values in DECISIONS #9.

**Ambiguous slots** (architecture §10 item 2; `interpret.py`).  Two intent words declare
readings here, each with a rationale, a package prior rank and an MDL proxy:

  hole extent            through_plate (default) | through_all | up_to_next
                         (`through(t)` and `blind(depth)` are explicit-only: given by the author)
  centered_on(face)      face_centroid (default) | exposed_region_midpoint
                         | between_siblings (opt-in: `consider=("between_siblings",)`)

The lowering of each reading is the function of the same name below.  Which reading a
build uses comes from `Context.interpret` (lock file, resolution or ranked default).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
from OCP.TopAbs import TopAbs_IN
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2

from . import kernel as K
from .errors import InteractionError, SketchError
from .expr import Func, ev
from .interpret import READING_SETS, Reading, ReadingSet, register
from .kernel import Vec3
from .ops import TOUCH_TOL, Expect, Feature
from .program import IntentTag, StepOut
from .refs import Ref, Tag, at_least, one


# ---------------------------------------------------------------- fastener rule table (v0 "pack")

# Clearance-hole diameters (mm), "normal fit".  Countersink head diameters for 82/90° flat heads,
# rounded.  Source: general ASME B18.6.3 / ISO 273 knowledge, NOT a cited pack (DECISIONS #9).
SCREWS = {
    "#6":  {"clearance": 3.7, "head": 7.2},
    "#8":  {"clearance": 4.5, "head": 8.6},
    "#10": {"clearance": 5.2, "head": 9.8},
    "M3":  {"clearance": 3.4, "head": 6.3},
    "M4":  {"clearance": 4.5, "head": 8.4},
    "M5":  {"clearance": 5.5, "head": 10.4},
}
TOOL_ACCESS_DIAMETER = 30.0   # architecture §8.1 R.c4: Ø30 straight driver access cylinder


def _screw(s: str) -> dict:
    try:
        return SCREWS[s]
    except KeyError:
        raise ValueError(f"unknown screw {s!r}; known: {sorted(SCREWS)}") from None


def clearance_diameter(screw) -> Func:
    """Lazy: clearance-hole Ø for a screw size (a rule, rung 1)."""
    return Func("clearance", lambda s: _screw(s)["clearance"], (screw,))


def head_diameter(screw) -> Func:
    return Func("head_diameter", lambda s: _screw(s)["head"], (screw,))


def edge_distance(diameter) -> Func:
    """Tear-out rule from architecture §8.2: hole centre >= 2 x Ø from any edge."""
    return Func("edge_distance", lambda d: 2.0 * d, (diameter,))


def tool_access_radius(screw=None) -> float:
    """R.c4: radius of the straight screwdriver access cylinder (independent of size in v0)."""
    return TOOL_ACCESS_DIAMETER / 2


@dataclass(frozen=True)
class HoleSpec:
    """What the hole is (lazy).  kind: 'plain' | 'clearance' | 'countersink'."""
    kind: str
    diameter: object
    head: object = None
    screw: object = None

    def evaluate(self, env) -> "HoleSpec":
        return HoleSpec(self.kind, float(ev(self.diameter, env)),
                        None if self.head is None else float(ev(self.head, env)), ev(self.screw, env))

    def __str__(self):
        return f"{self.kind}({self.screw if self.screw is not None else self.diameter})"


def plain(diameter) -> HoleSpec:
    return HoleSpec("plain", diameter)


def clearance(screw) -> HoleSpec:
    return HoleSpec("clearance", clearance_diameter(screw), None, screw)


def countersink(screw) -> HoleSpec:
    """Clearance bore plus a 90° countersink sized to the screw head."""
    return HoleSpec("countersink", clearance_diameter(screw), head_diameter(screw), screw)


@dataclass(frozen=True)
class Extent:
    """An extent the author states explicitly (made_by: author; not interpreted).

    kind: 'through_all' (tool spans the body), 'through' (through a plate of `depth`),
    'blind' (to `depth`).  'through' is the intent "through this plate": if something backs
    the plate, the hole turns blind and ΔH catches it (spike 01 §2.3 negative control).
    Leave the extent out (None) to let the interpretations mechanism choose."""
    kind: str
    depth: object = None

    def __str__(self):
        return self.kind if self.depth is None else f"{self.kind}({self.depth!r})"


THROUGH_ALL = Extent("through_all")


def through(thickness) -> Extent:
    return Extent("through", thickness)


def blind(depth) -> Extent:
    return Extent("blind", depth)


# ---------------------------------------------------------------- readings of ambiguous slots (arch §10.2)

HOLE_EXTENT = register(ReadingSet("hole", "extent", (
    Reading("through_plate", "through the plate the face belongs to: the face and its nearest opposing "
            "parallel face; turns blind (caught by ΔH) if more material backs the plate", prior=1, complexity=2),
    Reading("through_all", "through all material along the axis, however many layers", prior=2, complexity=1),
    Reading("up_to_next", "through the first run of material along the axis, stopping where it exits",
            prior=3, complexity=3),
), explicit_only=("through(thickness)", "blind(depth)"),
    doc="hole extent: what 'through' means when the author did not say"))

CENTERED_ON = register(ReadingSet("centered_on", "point", (
    Reading("face_centroid", "the area centroid of the face as it now is", prior=1, complexity=1),
    Reading("exposed_region_midpoint", "the middle of the face's exposed region: the longest material chord "
            "through its bounding centre, bridging holes but stopped by material attached to the face",
            prior=2, complexity=2),
    Reading("between_siblings", "the mean centre of the earlier holes on the same face (couples this "
            "feature to them)", prior=3, complexity=3, opt_in=True),
), doc="centered_on(face): which 'centre'"))


def reading_set(word: str, slot: str) -> ReadingSet:
    return READING_SETS[(word, slot)]


def _plane_axes(n: Vec3) -> tuple:
    """Two in-plane axes for a face with normal n: the global axes most perpendicular to n,
    orthogonalised (exact for axis-aligned faces; deterministic tie-break X, Y, Z)."""
    cands = sorted((Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)), key=lambda a: abs(a.dot(n)))
    u = (cands[0] - n * cands[0].dot(n)).unit()
    return u, n.cross(u).unit()


UP_TO_NEXT_RAYS = 16  # lines around the bore sampled for an "up to next" exit (deterministic, approximate)
EXPOSED_EPS = 0.01   # mm: probe offset above a gap in a face to test for attached material


def face_centroid(ctx, face) -> Vec3:
    return K.centroid(face)


def exposed_region_midpoint(ctx, face) -> Vec3:
    """Midpoint of the face's exposed region (NOTES DECISIONS #24).

    The exposed region is the face minus the footprint of material attached to it.  Holes
    and slots in the face are voids, not cover, so they are bridged.  Through the centre of
    the face's bounding rectangle (in-plane axes u, v), take the material chords of the
    face along u and along v.  A gap between two chords is bridged when the point just
    above it (outside, along the normal) is *not* inside the solid, i.e. nothing covers it.
    The longest bridged chord wins (u before v on a tie), and its midpoint is the point.
    For a plain rectangle this is the centre; for the bracket's mount face it is the middle
    of the plate below the gusset footprint.
    """
    n = K.face_normal(face, ctx.shape)
    c = K.centroid(face)
    best = None
    axes = _plane_axes(n)
    ext = [K.extent_along(face, a) for a in axes]
    c0 = c + axes[0] * (0.5 * sum(ext[0]) - c.dot(axes[0])) + axes[1] * (0.5 * sum(ext[1]) - c.dot(axes[1]))
    for a, (lo, hi) in zip(axes, ext):
        start = c0 + a * (lo - 1.0 - c0.dot(a))
        segs = K.segments_along(face, start, a, hi - lo + 2.0)
        chords = []
        for s0, s1 in segs:
            if chords:
                q = start + a * (0.5 * (chords[-1][1] + s0)) + n * EXPOSED_EPS
                if not K.inside_solid(ctx.shape, q):
                    chords[-1] = (chords[-1][0], s1)      # a void (hole): bridge it
                    continue
            chords.append((s0, s1))
        for s0, s1 in chords:
            if best is None or (s1 - s0) > best[0] + 1e-9:
                best = (s1 - s0, start + a * (0.5 * (s0 + s1)), (start + a * s0, start + a * s1))
    if best is None:
        raise SketchError("exposed_region_midpoint: the face has no material chord through its centre")
    ctx.note_read("exposed region bounded by", _features_bounding(ctx, face, best[2]))
    return best[1]


def _features_bounding(ctx, face, points) -> list:
    """Features that made the faces meeting `face` at the given boundary points (what bounds a
    chord of the face).  Deterministic: edges in map order, tags sorted."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    out = []
    edges = K.subshapes(face, K.KINDS["edge"])
    for p in points:
        v = BRepBuilderAPI_MakeVertex(p.pnt()).Vertex()
        for e in edges:
            if K.distance(v, e) > 1e-5:
                continue
            for g in K.faces_of_edge(ctx.shape, e):
                if g.IsSame(face):
                    continue
                for t in sorted({en.tag for en in ctx.ledger.who(g)}):
                    if t.feature not in out:
                        out.append(t.feature)
    return out


def between_siblings(ctx, face_ref) -> Vec3:
    sib = [p for (_fid, _k, on, p) in ctx.hole_centres if on == str(face_ref)]
    if len(sib) < 2:
        raise SketchError(f"between_siblings: needs >= 2 earlier holes on {face_ref}, found {len(sib)}",
                          invariant="reading precondition")
    s = sib[0]
    for p in sib[1:]:
        s = s + p
    return s * (1.0 / len(sib))


# ---------------------------------------------------------------- placements

class Placement:
    """Lazy point set.  `evaluate(ctx) -> list[Vec3]`.  Indexable: `pts[0]` is a placement."""
    intent: IntentTag | None = None

    def evaluate(self, ctx) -> list:  # pragma: no cover - abstract
        raise NotImplementedError

    def __getitem__(self, k: int) -> "Placement":
        return _Pick(self, k)


@dataclass(frozen=True)
class _Pick(Placement):
    of: Placement
    k: int

    def evaluate(self, ctx):
        pts = ev(self.of, ctx)
        if not (-len(pts) <= self.k < len(pts)):
            raise SketchError(f"placement index {self.k} out of range ({len(pts)} points)")
        return [pts[self.k]]

    def __repr__(self):
        return f"{self.of!r}[{self.k}]"


def _one_face(ctx, face_ref: Ref):
    fs = ctx.resolve(face_ref)
    if len(fs) != 1:
        raise SketchError(f"{face_ref} must resolve to one face for a placement")
    return fs[0]


@dataclass(frozen=True)
class centered_on(Placement):
    """'Centred on this face.'  Ambiguous (architecture §10.2): which centre is resolved by
    the interpretations mechanism from CENTERED_ON's readings, unless the author names one
    with `reading=`.  `consider=` opts in to extra readings (e.g. "between_siblings")."""
    face: Ref
    reading: str | None = None
    consider: tuple = ()

    def evaluate(self, ctx):
        f = _one_face(ctx, self.face)
        if self.reading is not None and CENTERED_ON.get(self.reading) is None:
            raise SketchError(f"centered_on: unknown reading {self.reading!r}")
        rd = ctx.interpret(CENTERED_ON, explicit=self.reading, consider=tuple(self.consider), key=str(self.face))
        if rd.name == "face_centroid":
            return [face_centroid(ctx, f)]
        if rd.name == "exposed_region_midpoint":
            return [exposed_region_midpoint(ctx, f)]
        return [between_siblings(ctx, self.face)]

    def __repr__(self):
        return f"centered_on({self.face})"


@dataclass(frozen=True)
class face_point(Placement):
    """Point at fraction u of the face's extent along `along[0]`, fraction v along `across[0]`,
    lying on the face plane.  e.g. face_point(shelf_face, along=(Y, 0.75), across=(X, 0.5))."""
    face: Ref
    along: tuple
    across: tuple

    def evaluate(self, ctx):
        f = _one_face(ctx, self.face)
        c = K.centroid(f)
        n = K.face_normal(f, ctx.shape)
        da, fa = _v(self.along[0]).unit(), float(ev(self.along[1], ctx))
        dc, fc = _v(self.across[0]).unit(), float(ev(self.across[1], ctx))
        a0, a1 = K.extent_along(f, da)
        c0, c1 = K.extent_along(f, dc)
        p = c + da * ((a0 + fa * (a1 - a0)) - c.dot(da)) + dc * ((c0 + fc * (c1 - c0)) - c.dot(dc))
        return [p - n * (p - c).dot(n)]

    def __repr__(self):
        return f"face_point({self.face}, along={self.along!r}, across={self.across!r})"


@dataclass(frozen=True)
class Segment:
    """Lazy directed segment.  evaluate -> (start, end) as Vec3."""
    base: object                      # callable(ctx) -> (Vec3, Vec3)
    desc: str

    def evaluate(self, ctx):
        return self.base(ctx)

    def __repr__(self):
        return self.desc

    def before(self, ref, clearance=0.0) -> "Segment":
        """Truncate the end at the projection of `ref`'s nearest point minus `clearance`.

        e.g. the mount-face centerline *below the gusset footprint* (architecture §8.4a)."""
        def f(ctx):
            s, e = self.evaluate(ctx)
            d = (e - s).unit()
            shapes = ctx.resolve(ref)
            t_ref = min(_project_min(sh, s, d) for sh in shapes)
            t_end = min((e - s).dot(d), t_ref - float(ev(clearance, ctx)))
            if t_end <= 0:
                raise SketchError(f"{self.desc}.before({ref}): nothing left of the segment",
                                  expected="> 0 length", got=f"{t_end:.4g}")
            return s, s + d * t_end
        return Segment(f, f"{self.desc}.before({ref}, clearance={clearance!r})")

    def midpoint(self) -> "Placement":
        return _SegMid(self)

    def length(self) -> Func:
        return Func("length", lambda se: (se[1] - se[0]).length(), (self,))


def _project_min(shape, origin: Vec3, d: Vec3) -> float:
    """Smallest projection of a shape's vertices (or centroid) onto the line origin + t*d."""
    vs = K.subshapes(shape, K.KINDS["vertex"])
    pts = [K.centroid(v) for v in vs] or [K.centroid(shape)]
    return min((p - origin).dot(d) for p in pts)


@dataclass(frozen=True)
class _SegMid(Placement):
    seg: Segment

    def evaluate(self, ctx):
        s, e = ev(self.seg, ctx)
        return [(s + e) * 0.5]

    def __repr__(self):
        return f"{self.seg!r}.midpoint()"


def centerline(face: Ref, direction) -> Segment:
    """Segment through centered_on(face) along `direction`, spanning the face's extent."""
    def f(ctx):
        fc = _one_face(ctx, face)
        d = _v(direction).unit()
        c = K.centroid(fc)
        lo, hi = K.extent_along(fc, d)
        base = c - d * c.dot(d)
        return base + d * lo, base + d * hi
    return Segment(f, f"centerline({face}, {direction!r})")


@dataclass(frozen=True)
class midpoint(Placement):
    """Midpoint of two single-point placements: 'centered between a and b'."""
    a: Placement
    b: Placement

    def evaluate(self, ctx):
        (pa,), (pb,) = ev(self.a, ctx), ev(self.b, ctx)
        return [(pa + pb) * 0.5]

    def __repr__(self):
        return f"midpoint({self.a!r}, {self.b!r})"


@dataclass(frozen=True)
class distribute(Placement):
    """`count` points evenly spaced along a segment, inset from its ends.

    inset: a number (both ends) or (start_inset, end_inset).  count=1 gives the midpoint
    of the inset segment.  Spread "as far apart as the insets allow" (architecture §8.3)."""
    along: Segment
    count: object
    inset: object = 0.0

    def evaluate(self, ctx):
        s, e = ev(self.along, ctx)
        n = int(ev(self.count, ctx))
        ins = ev(self.inset, ctx)
        i0, i1 = (float(ins[0]), float(ins[1])) if isinstance(ins, tuple) else (float(ins), float(ins))
        L = (e - s).length()
        d = (e - s).unit()
        a, b = i0, L - i1
        if b < a - 1e-9:
            raise SketchError(f"distribute: insets {i0:.4g}+{i1:.4g} exceed segment length {L:.4g}",
                              invariant="relation precondition", expected="room for the pattern", got=f"L={L:.4g}")
        if n < 1:
            raise SketchError("distribute: count must be >= 1")
        if n == 1:
            return [s + d * (0.5 * (a + b))]
        return [s + d * (a + (b - a) * k / (n - 1)) for k in range(n)]

    def __repr__(self):
        return f"distribute({self.along!r}, count={self.count!r}, inset={self.inset!r})"


@dataclass(frozen=True)
class linear_pattern(Placement):
    """k = 0..count-1 at start + k * pitch * direction (k is a declared index)."""
    start: Placement
    direction: object
    count: object
    pitch: object

    def evaluate(self, ctx):
        (p0,) = ev(self.start, ctx)
        d = _v(ev(self.direction, ctx)).unit()
        n, pitch = int(ev(self.count, ctx)), float(ev(self.pitch, ctx))
        return [p0 + d * (pitch * k) for k in range(n)]


@dataclass(frozen=True)
class circular_pattern(Placement):
    """k = 0..count-1 on a circle of `radius` about `center` and `axis`, starting along
    `start_dir`, spaced 360/count degrees (or `step` degrees if given)."""
    center: Placement
    axis: object
    count: object
    radius: object
    start_dir: object
    step: object = None

    def evaluate(self, ctx):
        (c,) = ev(self.center, ctx)
        ax = _v(ev(self.axis, ctx)).unit()
        u = _v(ev(self.start_dir, ctx))
        u = (u - ax * u.dot(ax)).unit()
        w = ax.cross(u)
        n, r = int(ev(self.count, ctx)), float(ev(self.radius, ctx))
        step = math.radians(float(ev(self.step, ctx))) if self.step is not None else 2 * math.pi / n
        return [c + u * (r * math.cos(k * step)) + w * (r * math.sin(k * step)) for k in range(n)]


@dataclass(frozen=True)
class at(Placement):
    """Escape hatch: explicit points (lazy expressions allowed).  Counts as literals in an
    idiomatic score; prefer relations."""
    points: tuple

    def evaluate(self, ctx):
        return [_v(ev(p, ctx)) for p in self.points]


def _v(x) -> Vec3:
    return x if isinstance(x, Vec3) else Vec3(*map(float, x))


# ---------------------------------------------------------------- the hole composite

@dataclass(frozen=True)
class Hole(Feature):
    """`hole(on=face, at=placement, spec, extent)`: intent-layer composite (dsl.md §4.2).

    Lowers to one core `cut` with a tool list: per instance k a cylinder (Ø spec.diameter)
    along the inward face normal, plus a 90° cone if spec is a countersink.
    Roles (spike 02 §6 'pattern'):
      wall(k)        Cut.Modified(instance k cylinder lateral face)   one()
      countersink(k) Cut.Modified(instance k cone lateral face)        one()
      floor(k)       blind holes only: the cylinder end face            one()
    Extent: explicit (`through(t)`, `blind(d)`, `THROUGH_ALL`; made_by author) or None, in
    which case a HOLE_EXTENT reading is lowered (architecture §10.2):
      through_plate  depth = distance to the face's nearest opposing parallel face (+ overshoot)
      through_all    depth = body diagonal; one tunnel per material layer the axis crosses
      up_to_next     depth = the first run of material along the axis, per instance
    Expected: ΔH = number of tunnels (1 per through instance, or per layer for through_all;
    each disjoint from all other hole tools, else InteractionError); ΔS = 0; volume decreases.
    Checks: the face is planar, each centre lies on the face plane and inside the face.
    """
    id: str
    tags: tuple
    on: Ref
    at: object
    spec: HoleSpec
    extent: Extent | None = None          # None: interpreted (HOLE_EXTENT readings)
    instance_tags: tuple | None = None
    expect: dict | None = None
    op_name = "cut"
    failure_classes = ("silently wrong but valid (blind instead of through: caught by ΔH)",)

    @property
    def lowered_from(self):
        return f"hole({self.spec.kind}, {self.extent.kind if self.extent else 'interpreted'})"

    def wall(self, k: int = 0, card=None) -> Ref:
        return Ref(self.id, "wall", str(k), card or one(), kind="face")

    def walls(self) -> Ref:
        return self.created("wall")

    def countersink(self, k: int = 0) -> Ref:
        return Ref(self.id, "countersink", str(k), one(), kind="face")

    def floor(self, k: int = 0) -> Ref:
        return Ref(self.id, "floor", str(k), one(), kind="face")

    OVERSHOOT = 1.0   # mm: tools start this far outside the face (DECISIONS #11)

    def apply(self, ctx) -> StepOut:
        face = _one_face(ctx, self.on)
        if not K.is_planar(face):
            raise SketchError(f"hole on {self.on}: v0 holes need a planar face")
        n = K.face_normal(face, ctx.shape)      # outward
        c = K.centroid(face)
        spec = ev(self.spec, ctx)
        pts = _flatten(ev(self.at, ctx))
        if not pts:
            raise SketchError("hole: placement produced no points")
        for k, p in enumerate(pts):
            off = (p - c).dot(n)
            if abs(off) > 1e-6:
                raise SketchError(f"hole instance {k}: centre is {off:.4g} mm off the face plane of {self.on}",
                                  invariant="relation: centre on face", expected=0, got=f"{off:.4g}")
            cls = BRepClass_FaceClassifier(TopoDS.Face(face), p.pnt(), 1e-6)
            if cls.State() != TopAbs_IN:
                raise InteractionError(f"hole instance {k}: centre {p!r} is not inside face {self.on}",
                                       invariant="relation: centre inside face")
        r = spec.diameter / 2
        if r <= 0:
            raise SketchError("hole diameter must be > 0")
        ov = self.OVERSHOOT
        if self.extent is None:
            kind = ctx.interpret(HOLE_EXTENT).name
            label = kind
        else:
            ctx.interpret(HOLE_EXTENT, explicit=str(self.extent))
            kind, label = self.extent.kind, self.extent.kind
        depths, tunnels = self._depths(ctx, kind, face, n, pts, ov)
        tools, per_instance = [], []
        led = ctx.ledger
        for k, p in enumerate(pts):
            start = p + n * ov
            depth = depths[k]
            cm = BRepPrimAPI_MakeCylinder(gp_Ax2(start.pnt(), (-n).dir()), r, depth)
            cm.Build()
            cyl = cm.Shape()
            led.add(Tag(self.id, "wall", str(k)), [cm.Cylinder().LateralFace()])
            if kind == "blind":
                led.add(Tag(self.id, "floor", str(k)), [cm.Cylinder().TopFace()])
            inst = [cyl]
            # interaction-check shapes start AT the face: the overshoot above it meets no material
            # and must not count as a clash between neighbouring tools
            probe = [BRepPrimAPI_MakeCylinder(gp_Ax2(p.pnt(), (-n).dir()), r, depth - ov).Shape()]
            if spec.kind == "countersink":
                if spec.head is None or spec.head <= spec.diameter:
                    raise SketchError("countersink head Ø must exceed the bore Ø")
                rk = spec.head / 2 + ov                  # 90° included: radius shrinks 1:1 with depth
                km = BRepPrimAPI_MakeCone(gp_Ax2(start.pnt(), (-n).dir()), rk, 0.0, rk)
                km.Build()
                led.add(Tag(self.id, "countersink", str(k)), [km.Cone().LateralFace()])
                inst.append(km.Shape())
                probe.append(BRepPrimAPI_MakeCone(gp_Ax2(p.pnt(), (-n).dir()), spec.head / 2, 0.0,
                                                  spec.head / 2).Shape())
            tools += inst
            per_instance.append(probe)
        # interaction: instances vs each other and vs earlier holes (spike 01 §1.4)
        declared = self.expect is not None and "dH" in self.expect
        clashes = []
        for k, inst in enumerate(per_instance):
            for j in range(k):
                if _min_dist(inst, per_instance[j]) <= TOUCH_TOL:
                    clashes.append(f"instance {k} meets instance {j}")
            for (fid, kk, prev, node) in ctx.hole_tools:
                if _min_dist(inst, prev) <= TOUCH_TOL:
                    clashes.append(f"instance {k} meets {fid} instance {kk}" + (f" ({node})" if node else ""))
        if clashes and not declared:
            raise InteractionError("hole tools interact with other holes; ΔH would not be the simple count",
                                   invariant="interaction: holes disjoint (spike 01 §1.4)",
                                   expected="disjoint hole tools, or expect={'dH': ...} declared",
                                   got="; ".join(clashes))
        algo = K.boolean("cut", ctx.shape, tools)
        shape = algo.Shape()
        led.propagate(self.id, algo, shape)
        inst_tags = {}
        for k in range(len(pts)):
            node = None
            if self.instance_tags and k < len(self.instance_tags):
                inst_tags[str(k)] = tuple(self.instance_tags[k])
                node = self.instance_tags[k][0].node if self.instance_tags[k] else None
            ctx.hole_tools.append((self.id, k, per_instance[k], node))
            ctx.hole_centres.append((self.id, k, str(self.on), pts[k]))
        n_through = sum(tunnels)
        exp = Expect(n_through, 0, "-",
                     (f"{n_through} tunnel(s) ({label}), each hole disjoint from other hole tools"
                      if kind != "blind" else "blind holes make no tunnel"),
                     "a hole must not split the part")
        return StepOut(shape, exp.override(self.expect), op="cut", lowered_from=f"hole({spec.kind}, {label})",
                       instance_tags=inst_tags,
                       detail={"diameter": spec.diameter, "head": spec.head,
                               "extent": label if self.extent is None else str(self.extent),
                               "depths": depths, "centres": [p for p in pts], "tools": len(tools)})

    def _depths(self, ctx, kind, face, n, pts, ov) -> tuple:
        """Tool depth per instance (measured from `ov` above the face) and expected tunnels."""
        lo, hi = K.bbox(ctx.shape)
        diag = (hi - lo).length()
        m = len(pts)
        if kind == "through_all":
            # each separate layer of material the axis crosses becomes its own tunnel
            layers = [len(K.segments_along(ctx.shape, p + n * ov, -n, diag + 2 * ov)) for p in pts]
            return [diag + 2 * ov] * m, layers
        if kind == "through":                      # explicit through(thickness)
            return [float(ev(self.extent.depth, ctx)) + 2 * ov] * m, [1] * m
        if kind == "blind":
            return [float(ev(self.extent.depth, ctx)) + ov] * m, [0] * m
        if kind == "through_plate":
            return [_plate_thickness(ctx, face, n, self.on) + 2 * ov] * m, [1] * m
        if kind == "up_to_next":
            # the first run of material, measured on the axis AND on UP_TO_NEXT_RAYS lines around
            # the bore, so an oblique exit face is cleared across the whole diameter
            r = float(ev(self.spec, ctx).diameter) / 2
            u, v = _plane_axes(n)
            out = []
            for k, p in enumerate(pts):
                segs = K.segments_along(ctx.shape, p + n * ov, -n, diag + 2 * ov)
                if not segs or segs[0][0] > ov + 1e-6:
                    raise SketchError(f"up_to_next: no material under instance {k} of {self.id}",
                                      invariant="reading precondition")
                end, nxt = segs[0][1], segs[1][0] if len(segs) > 1 else math.inf
                for j in range(UP_TO_NEXT_RAYS):
                    a = 2 * math.pi * j / UP_TO_NEXT_RAYS
                    q = p + (u * math.cos(a) + v * math.sin(a)) * r
                    rs = K.segments_along(ctx.shape, q + n * ov, -n, diag + 2 * ov)
                    if rs and rs[0][0] <= ov + 1e-6:
                        end = max(end, rs[0][1])
                        if len(rs) > 1:
                            nxt = min(nxt, rs[1][0])
                out.append(end + (min(ov, 0.5 * (nxt - end)) if nxt > end else ov))
            return out, [1] * m
        raise ValueError(f"unknown extent {kind!r}")


def _plate_thickness(ctx, face, n: Vec3, on) -> float:
    """'The plate' of a planar face: the face plus its nearest opposing parallel face whose
    extent overlaps it (in-plane axes from `_plane_axes`).  Returns their distance."""
    c = K.centroid(face)
    axes = _plane_axes(n)
    ext = [K.extent_along(face, a) for a in axes]
    best = math.inf
    for g in K.subshapes(ctx.shape, K.KINDS["face"]):
        if not K.is_planar(g) or K.face_normal(g, ctx.shape).dot(n) > -1 + 1e-9:
            continue
        dist = (c - K.centroid(g)).dot(n)
        if dist <= 1e-6 or dist >= best:
            continue
        if all(min(e[1], ge[1]) - max(e[0], ge[0]) > 1e-6
               for e, ge in zip(ext, (K.extent_along(g, a) for a in axes))):
            best = dist
    if best is math.inf:
        raise SketchError(f"through_plate: {on} has no opposing parallel face (not a plate)",
                          invariant="reading precondition")
    return best


def _flatten(x) -> list:
    """A placement or a list of placements -> flat list of Vec3 (instance order = declared order)."""
    out = []
    for p in x:
        out.extend(_flatten(p) if isinstance(p, (list, tuple)) else [p])
    return out


def _min_dist(a: list, b: list) -> float:
    """Minimum distance between two tool groups; bounding boxes first (exact distance is slow)."""
    best = math.inf
    for x in a:
        bx = K.bbox(x)
        for y in b:
            by = K.bbox(y)
            gap = max(bx[0].x - by[1].x, by[0].x - bx[1].x, bx[0].y - by[1].y, by[0].y - bx[1].y,
                      bx[0].z - by[1].z, by[0].z - bx[1].z)
            if gap > 10 * TOUCH_TOL:
                best = min(best, gap)      # lower bound is enough: clearly apart
                continue
            best = min(best, K.distance(x, y))
    return best


__all__ = ["SCREWS", "clearance", "countersink", "plain", "clearance_diameter", "head_diameter", "edge_distance",
           "tool_access_radius", "through", "blind", "THROUGH_ALL", "Extent", "HoleSpec", "Placement",
           "centered_on", "face_point", "centerline", "Segment", "midpoint", "distribute", "linear_pattern",
           "circular_pattern", "at", "Hole", "at_least", "HOLE_EXTENT", "CENTERED_ON", "reading_set"]
