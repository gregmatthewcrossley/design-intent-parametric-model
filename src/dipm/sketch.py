"""v0 sketch profiles: named points and edges whose coordinates are parameter expressions.

This is **not** the constructive solver of dsl.md §3.2 / §6.2 (that is the next piece of
work; see NOTES.md DECISIONS #6).  What v0 gives:

* a `Plane` (origin, in-plane x direction, normal) mapping 2D (u, v) to 3D;
* a `Profile`: a closed polygon of **named** points, each an (u, v) pair of expressions
  or a small *construction* (`midpoint`, `offset`, `line_line`, `between`) of earlier
  named points;
* **named edges** (`"a-b"` or an alias like `"mount"`) that become reference sources
  for the solid features built from the profile (`E.side(mount)`);
* checks on every evaluation: no zero-length edge, simple (non-self-intersecting)
  polygon, non-zero area, and an optional declared **winding branch tag**
  (`winding="ccw"`): if a parameter edit flips the winding, that is a branch flip and
  fails loudly instead of happening silently (dsl.md §3.2 "every step carries an
  explicit branch tag").  `on_side(...)` is a per-point branch tag.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakeVertex, BRepBuilderAPI_MakeWire)

from .errors import SketchError
from .expr import ev
from .kernel import Vec3, X, Y, Z, ORIGIN


# ---------------------------------------------------------------- planes

@dataclass(frozen=True)
class Plane:
    """A sketch plane.  (u, v) -> origin + u*x_dir + v*y_dir, with y_dir = normal x x_dir."""
    origin: tuple = (0.0, 0.0, 0.0)     # may hold expressions
    x_dir: Vec3 = X
    normal: Vec3 = Z
    name: str = ""

    def evaluate(self, env) -> "SolvedPlane":
        o = ev(self.origin, env)
        o = o if isinstance(o, Vec3) else Vec3(*map(float, o))
        n = self.normal.unit()
        x = self.x_dir.unit()
        if abs(n.dot(x)) > 1e-9:
            raise SketchError(f"plane {self.name or ''}: x_dir is not perpendicular to the normal")
        return SolvedPlane(o, x, n.cross(x), n)

    def offset(self, distance) -> "Plane":
        """A parallel plane `distance` along the normal (distance may be an expression)."""
        n = self.normal
        o = self.origin
        return Plane(tuple(_add(o[i], _mul(distance, c)) for i, c in enumerate((n.x, n.y, n.z))),
                     self.x_dir, self.normal, self.name + "+off")


def _add(a, b):
    return a + b


def _mul(a, c):
    return a * c if c != 0 else 0.0


@dataclass(frozen=True)
class SolvedPlane:
    origin: Vec3
    x_dir: Vec3
    y_dir: Vec3
    normal: Vec3

    def to3d(self, u: float, v: float) -> Vec3:
        return self.origin + self.x_dir * u + self.y_dir * v


XY = Plane((0.0, 0.0, 0.0), X, Z, "XY")
YZ = Plane((0.0, 0.0, 0.0), Y, X, "YZ")    # u = global Y, v = global Z, normal +X
XZ = Plane((0.0, 0.0, 0.0), X, -Y, "XZ")   # u = global X, v = global Z, normal -Y


# ---------------------------------------------------------------- constructions (tiny constructive helpers)

class Construction:
    """A point defined from earlier named points.  `solve(env, pts)` -> (u, v)."""
    branch: str | None = None

    def solve(self, env, pts: dict) -> tuple:  # pragma: no cover - abstract
        raise NotImplementedError


def _pt(x, env, pts) -> tuple:
    if isinstance(x, str):
        if x not in pts:
            raise SketchError(f"construction refers to point {x!r} before it is defined")
        return pts[x]
    if isinstance(x, Construction):
        return x.solve(env, pts)
    u, v = ev(x, env)
    return (float(u), float(v))


@dataclass(frozen=True)
class midpoint(Construction):
    """Midpoint of two points (names or (u, v) pairs): the canonical 'centered' relation."""
    a: object
    b: object

    def solve(self, env, pts):
        (ax, ay), (bx, by) = _pt(self.a, env, pts), _pt(self.b, env, pts)
        return (0.5 * (ax + bx), 0.5 * (ay + by))


@dataclass(frozen=True)
class between(Construction):
    """Point at fraction t from a to b (t may be an expression)."""
    a: object
    b: object
    t: object = 0.5

    def solve(self, env, pts):
        (ax, ay), (bx, by) = _pt(self.a, env, pts), _pt(self.b, env, pts)
        t = float(ev(self.t, env))
        return (ax + t * (bx - ax), ay + t * (by - ay))


@dataclass(frozen=True)
class offset(Construction):
    """Point `distance` from `base` along a 2D direction (du, dv) (normalised)."""
    base: object
    direction: tuple
    distance: object

    def solve(self, env, pts):
        bx, by = _pt(self.base, env, pts)
        du, dv = (float(c) for c in ev(self.direction, env))
        n = math.hypot(du, dv)
        if n < 1e-12:
            raise SketchError("offset direction has zero length")
        d = float(ev(self.distance, env))
        return (bx + d * du / n, by + d * dv / n)


@dataclass(frozen=True)
class line_line(Construction):
    """Intersection of line (a1, a2) with line (b1, b2).  Unique when it exists, so no branch;
    parallel lines fail loudly."""
    a1: object
    a2: object
    b1: object
    b2: object

    def solve(self, env, pts):
        (x1, y1), (x2, y2) = _pt(self.a1, env, pts), _pt(self.a2, env, pts)
        (x3, y3), (x4, y4) = _pt(self.b1, env, pts), _pt(self.b2, env, pts)
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-12:
            raise SketchError("line_line: lines are parallel (no intersection)")
        a = x1 * y2 - y1 * x2
        b = x3 * y4 - y3 * x4
        return ((a * (x3 - x4) - (x1 - x2) * b) / den, (a * (y3 - y4) - (y1 - y2) * b) / den)


@dataclass(frozen=True)
class on_side(Construction):
    """Branch tag as a construction: `point` must lie LEFT or RIGHT of directed line a->b.

    Returns `point` unchanged; raises a branch-flip error if the side is wrong.
    """
    point: object
    a: object
    b: object
    side: str = "left"

    def solve(self, env, pts):
        p = _pt(self.point, env, pts)
        (ax, ay), (bx, by) = _pt(self.a, env, pts), _pt(self.b, env, pts)
        cross = (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)
        got = "left" if cross > 0 else ("right" if cross < 0 else "on")
        if got != self.side:
            raise SketchError(f"branch flip: point is {got} of line, declared {self.side}",
                              invariant="branch tag (dsl.md §3.2)", expected=self.side, got=got)
        return p


# ---------------------------------------------------------------- profile

@dataclass(frozen=True)
class SolvedProfile:
    plane: SolvedPlane
    points2d: dict          # name -> (u, v)
    face: object            # TopoDS_Face
    edges: dict             # edge name -> TopoDS_Edge
    vertices: dict          # point name -> TopoDS_Vertex
    signed_area: float


@dataclass(frozen=True)
class Profile:
    """A closed polygon of named points on a plane.

    points:     {name: (u_expr, v_expr) | Construction}  -- evaluated in order
    loop:       point names in boundary order (default: the order of `points`)
    edge_names: aliases for edges, {"a-b": "mount"}; unaliased edges are named "a-b"
    winding:    "ccw" | "cw" | None -- declared branch tag (signed-area sign in (u, v))
    """
    plane: Plane
    points: dict
    loop: tuple | None = None
    edge_names: dict = field(default_factory=dict)
    winding: str | None = "ccw"
    name: str = ""

    def edge_list(self) -> list[tuple[str, str, str]]:
        loop = list(self.loop or self.points)
        out = []
        for a, b in zip(loop, loop[1:] + loop[:1]):
            raw = f"{a}-{b}"
            out.append((self.edge_names.get(raw, raw), a, b))
        return out

    def edge_names_all(self) -> list[str]:
        return [n for n, _, _ in self.edge_list()]

    def evaluate(self, env, shift: Vec3 | None = None) -> SolvedProfile:
        """Solve the profile; `shift` translates the plane (used by symmetric extrudes)."""
        pl = self.plane.evaluate(env)
        if shift is not None:
            pl = SolvedPlane(pl.origin + shift, pl.x_dir, pl.y_dir, pl.normal)
        pts: dict = {}
        for name, spec in self.points.items():
            try:
                pts[name] = _pt(spec, env, pts)
            except SketchError as e:
                raise SketchError(f"profile {self.name!r}, point {name!r}: {e.message}",
                                  invariant=e.invariant, expected=e.expected, got=e.got) from None
        edges = self.edge_list()
        loop = list(self.loop or self.points)
        if len(loop) < 3:
            raise SketchError(f"profile {self.name!r}: need >= 3 points")
        # zero-length edges
        for n, a, b in edges:
            if math.dist(pts[a], pts[b]) < 1e-9:
                raise SketchError(f"profile {self.name!r}: edge {n!r} has zero length")
        # simple polygon: no two non-adjacent edges intersect
        m = len(edges)
        for i in range(m):
            for j in range(i + 1, m):
                if j == i + 1 or (i == 0 and j == m - 1):
                    continue
                if _segments_intersect(pts[edges[i][1]], pts[edges[i][2]], pts[edges[j][1]], pts[edges[j][2]]):
                    raise SketchError(f"profile {self.name!r}: edges {edges[i][0]!r} and {edges[j][0]!r} "
                                      "intersect (self-intersecting profile)")
        area2 = sum(pts[a][0] * pts[b][1] - pts[b][0] * pts[a][1] for _, a, b in edges)
        if abs(area2) < 1e-9:
            raise SketchError(f"profile {self.name!r}: zero area")
        got = "ccw" if area2 > 0 else "cw"
        if self.winding is not None and got != self.winding:
            raise SketchError(f"profile {self.name!r}: winding flipped (branch flip)",
                              invariant="branch tag: winding (dsl.md §3.2)", expected=self.winding, got=got)
        verts = {n: BRepBuilderAPI_MakeVertex(pl.to3d(*pts[n]).pnt()).Vertex() for n in loop}
        mw = BRepBuilderAPI_MakeWire()
        emap = {}
        for n, a, b in edges:
            e = BRepBuilderAPI_MakeEdge(verts[a], verts[b]).Edge()
            emap[n] = e
            mw.Add(e)
        if not mw.IsDone():
            raise SketchError(f"profile {self.name!r}: wire construction failed")
        face = BRepBuilderAPI_MakeFace(mw.Wire(), True).Face()
        return SolvedProfile(pl, pts, face, emap, verts, area2 / 2)


def rect_points(u0, v0, u1, v1, names=("a", "b", "c", "d")) -> dict:
    """Convenience: CCW rectangle corners as a points dict."""
    a, b, c, d = names
    return {a: (u0, v0), b: (u1, v0), c: (u1, v1), d: (u0, v1)}


def _orient(p, q, r) -> float:
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def _segments_intersect(p1, p2, p3, p4) -> bool:
    d1, d2 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    d3, d4 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    if ((d1 > 1e-12 and d2 < -1e-12) or (d1 < -1e-12 and d2 > 1e-12)) and \
       ((d3 > 1e-12 and d4 < -1e-12) or (d3 < -1e-12 and d4 > 1e-12)):
        return True

    def on_seg(p, q, r):
        return min(p[0], q[0]) - 1e-12 <= r[0] <= max(p[0], q[0]) + 1e-12 and \
            min(p[1], q[1]) - 1e-12 <= r[1] <= max(p[1], q[1]) + 1e-12
    return any(abs(d) <= 1e-12 and on_seg(a, b, c) for d, a, b, c in
               ((d1, p3, p4, p1), (d2, p3, p4, p2), (d3, p1, p2, p3), (d4, p1, p2, p4)))


__all__ = ["Plane", "XY", "YZ", "XZ", "Profile", "SolvedProfile", "midpoint", "between", "offset",
           "line_line", "on_side", "rect_points", "ORIGIN", "Y", "Z"]
