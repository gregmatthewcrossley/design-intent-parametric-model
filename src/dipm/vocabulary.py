"""The check vocabulary: computable forms for intent-file checks (NOTES TODO 4;
docs/purpose-loop.md §3 step 3).

A check in `<design>.intent.yaml` is either bound to one of a small, fixed set of **forms** or
explicitly marked descriptive (and so *not run*):

    - {id: R.c5, kind: relation, statement: "Holds a Ø6–14 mm rod blank", priority: must,
       binding: {form: holds_cylinder, component: rod, seat: cradle_seat, axis: X,
                 made_by: model, status: proposed}}
    - {id: R.c6, kind: rule, statement: "No sharp edge touches the blank",
       binding: {form: descriptive, reason: "no computable form for edge sharpness yet"}}

The model writes the binding; dipm evaluates it.  Binding values are text (the file's rule):
references (`cradle_seat` or `export:cradle_seat` = a named export; `A.P.holes` = a feature;
`R.body.side(wall)` = a structural reference), numbers and ranges (`"12"`, `"6..14"`, a
parameter expression such as `"6*t"`), vectors (`X`, `-Z`, `"0,0,1"`) and component ids.

Every form evaluates to the same record as the DSL-bound checks (checks.CheckResult): terms
with nominal, worst case, limit and margin, a state (ample | thin | failing), the method's
assumptions, and the faces and features involved.  A binding whose references or components
do not resolve in a build is **not run** with the reason, never passed (B1).  A binding is
model-made (hatched) until the designer accepts it (`status: accepted`).

Families (`FORMS`): relations (coincident, centered_on, symmetric_about, parallel,
distance_between, inside_face), pack rules (min_wall, overhang, hole_edge_distance, bridging),
fit against component envelopes (holds_cylinder, retention, clears_box), hand calculations from
packs (load, bending, anchor_pullout) and tool access.

**Fit forms use the part's projection along the cylinder axis** (a long rod spans the whole
part): the deterministic display tessellation is projected onto the plane perpendicular to the
axis, a disk of the rod's diameter is lowered from above the seat until it rests (settling
sideways under gravity), and the *escape lift* is the least height the rod must rise before it
can slide out sideways (lift-then-slide, which equals the minimax height for a cradle with a
lip).  Approximations are listed in each result's method assumptions.
"""
from __future__ import annotations

import ast
import difflib
import math
import operator
from dataclasses import dataclass, field

from . import packs
from .checks import (CheckResult, Env, IntentCheck, Overhang, ToolAccess, anchor_sf, anchor_term, bending_term,
                     material_sf, term)
from .components import Component, ComponentError, parse_range
from .quantity import Quantity

META_KEYS = ("form", "made_by", "status", "note")
BINDING_STATUS = ("proposed", "accepted", "challenged")
CONTACT_TOL = 0.05      # mm: a rod "touches" a face within this gap (tessellation chord error ≈ 0.05)
RELATION_TOL = 0.01     # mm: geometric relations are exact up to modelling tolerance


class BindingError(ValueError):
    """A binding cannot be evaluated in this build (unresolved reference, missing component).
    Reported as *not run* with the message."""


# ---------------------------------------------------------------- forms

@dataclass
class P:
    """One binding parameter."""
    name: str
    type: str            # ref | refs | holes | number | range | vector | component | text | enum
    required: bool = True
    default: str | None = None
    doc: str = ""
    choices: tuple = ()


@dataclass
class Form:
    name: str
    family: str
    kind: str            # architecture §4.1 check kind
    rung: int
    doc: str
    params: list
    example: dict
    plain: str           # plain-language template ({param} placeholders)
    fn: object = None

    def as_dict(self) -> dict:
        return {"form": self.name, "family": self.family, "kind": self.kind, "rung": self.rung, "doc": self.doc,
                "params": [{"name": p.name, "type": p.type, "required": p.required, "default": p.default,
                            "doc": p.doc, **({"choices": list(p.choices)} if p.choices else {})} for p in self.params],
                "example": self.example, "reads_as": self.plain}


FORMS: dict = {}


def form(name, family, kind, rung, doc, params, example, plain):
    def deco(fn):
        FORMS[name] = Form(name, family, kind, rung, doc, params, {"form": name, **example}, plain, fn)
        return fn
    return deco


# ---------------------------------------------------------------- value parsing

_ALLOWED_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
                ast.Pow: operator.pow}
_FUNCS = {"min": min, "max": max, "abs": abs, "sqrt": math.sqrt}


def _eval_expr(text: str, names: dict) -> float:
    """A tiny, safe arithmetic evaluator: numbers, + − × ÷ **, parentheses, parameter names,
    min/max/abs/sqrt."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _ALLOWED_BIN:
            return _ALLOWED_BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        if isinstance(n, ast.Name):
            if n.id not in names:
                raise ValueError(f"unknown name '{n.id}'")
            v = names[n.id]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"'{n.id}' is not a number")
            return float(v)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return float(_FUNCS[n.func.id](*[ev(a) for a in n.args]))
        raise ValueError("only numbers, parameters and + - * / ** min max abs sqrt are allowed")
    return ev(ast.parse(str(text).strip(), mode="eval"))


def _strip_unit(text: str) -> str:
    t = str(text).strip()
    for u in ("mm", "kg", "deg", "°", "N"):
        if t.endswith(u) and not t[:-len(u)].rstrip().endswith(("*", "/", "+", "-")):
            t = t[:-len(u)].strip()
            break
    return t


def number(text, params: dict | None = None, label: str = "") -> float:
    t = _strip_unit(text)
    try:
        return float(t)
    except ValueError:
        pass
    try:
        return _eval_expr(t, params or {})
    except (ValueError, SyntaxError) as e:
        raise BindingError(f"{label or 'value'}: '{text}' is not a number or expression ({e})") from None


def range_q(text, params: dict | None = None, label: str = "", unit: str = "mm", source: str = "binding",
            made_by: str = "model") -> Quantity:
    t = str(text).strip()
    if ".." in t:
        try:
            return parse_range(t, unit, label, source, made_by)
        except ComponentError as e:
            raise BindingError(str(e)) from None
    v = number(t, params, label)
    return Quantity(v, v, v, unit, source, made_by, label)


_AXES = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}


def vector(text, label: str = "") -> tuple:
    t = str(text).strip().upper().replace(" ", "")
    sign = 1.0
    if t[:1] in "+-" and t[1:] in _AXES:
        sign, t = (-1.0 if t[0] == "-" else 1.0), t[1:]
    if t in _AXES:
        return tuple(sign * c for c in _AXES[t])
    try:
        v = tuple(float(x) for x in t.split(","))
    except ValueError:
        raise BindingError(f"{label or 'vector'}: '{text}' is not an axis (X, -Z) or 'x,y,z'") from None
    n = math.sqrt(sum(c * c for c in v)) if len(v) == 3 else 0.0
    if n < 1e-12:
        raise BindingError(f"{label or 'vector'}: '{text}' must be three numbers, not all zero")
    return tuple(c / n for c in v)


def _syntax_check(p: P, value) -> str | None:
    if not isinstance(value, str):
        return f"{p.name}: must be text (quote it)"
    if not value.strip():
        return f"{p.name}: must not be empty"
    if p.type == "range" and value.startswith("component:"):
        return None
    try:
        if p.type == "vector":
            vector(value, p.name)
        elif p.type in ("number", "range"):
            t = _strip_unit(value)
            if ".." in t and p.type == "range":
                parse_range(value, "", p.name)
            else:
                try:
                    float(t)
                except ValueError:
                    ast.parse(t, mode="eval")      # names are checked at evaluation (parameters)
        elif p.type == "enum" and value not in p.choices:
            return f"{p.name}: must be one of {', '.join(p.choices)}; got '{value}'"
    except (BindingError, ComponentError, SyntaxError) as e:
        return f"{p.name}: {e}"
    return None


def validate_binding(binding, components: dict | None = None, check_id: str = "") -> list:
    """Readable errors for one binding (empty = valid).  References are checked for syntax only;
    whether they resolve depends on the geometry (unresolved = not run at evaluation)."""
    where = f"{check_id}.binding" if check_id else "binding"
    if not isinstance(binding, dict):
        return [f"{where}: must be a mapping with a 'form'"]
    f = binding.get("form")
    if f == "descriptive":
        errs = []
        if not str(binding.get("reason") or "").strip():
            errs.append(f"{where}: a descriptive check needs a 'reason' (why it cannot be computed)")
        for k in binding:
            if k not in META_KEYS + ("reason",):
                errs.append(f"{where}: unknown key '{k}' for a descriptive check")
        return errs
    if f not in FORMS:
        return [f"{where}.form: unknown form '{f}'"
                + (f" (did you mean '{m[0]}'?)" if (m := difflib.get_close_matches(str(f), list(FORMS), 1, 0.5)) else "")
                + f"; forms: {', '.join(sorted(FORMS))}, descriptive"]
    fm = FORMS[f]
    errs = []
    names = {p.name for p in fm.params}
    for k in binding:
        if k not in names and k not in META_KEYS:
            m = difflib.get_close_matches(k, list(names), 1)
            errs.append(f"{where}: unknown parameter '{k}' for {f}" + (f" (did you mean '{m[0]}'?)" if m else "")
                        + f"; parameters: {', '.join(p.name for p in fm.params)}")
    for p in fm.params:
        if p.name not in binding:
            if p.required:
                errs.append(f"{where}: {f} needs '{p.name}' ({p.doc})")
            continue
        e = _syntax_check(p, binding[p.name])
        if e:
            errs.append(f"{where}.{e}")
        if p.type == "component" and components is not None and binding[p.name] not in components:
            errs.append(f"{where}.{p.name}: no component '{binding[p.name]}' in the intent file's components "
                        f"({', '.join(sorted(components)) or 'none declared'})")
        if p.type == "range" and str(binding[p.name]).startswith("component:"):
            cid = str(binding[p.name])[len("component:"):]
            if components is not None and cid not in components:
                errs.append(f"{where}.{p.name}: no component '{cid}'")
    if "made_by" in binding and binding["made_by"] not in ("model", "user", "pack default", "author"):
        errs.append(f"{where}.made_by: must be model, user, pack default or author")
    if "status" in binding and binding["status"] not in BINDING_STATUS:
        errs.append(f"{where}.status: must be one of {', '.join(BINDING_STATUS)}")
    return errs


def describe(binding: dict, components: dict | None = None) -> str:
    """The binding in plain language, for review ("Rests in the cradle: a Ø6–14 mm cylinder …")."""
    if not isinstance(binding, dict):
        return ""
    f = binding.get("form")
    if f == "descriptive":
        return f"Descriptive, not run: {binding.get('reason', '')}"
    fm = FORMS.get(f)
    if fm is None:
        return f"unknown form {f}"
    vals = {p.name: binding.get(p.name, p.default if p.default is not None else ("" if p.required else "the pack's"))
            for p in fm.params}
    types = {p.name: p.type for p in fm.params}
    for k, v in list(vals.items()):
        if isinstance(v, str) and types.get(k) == "range" and ".." in v and not v.startswith("component:"):
            vals[k] = v.replace("..", "–")
        if isinstance(v, str) and v.startswith("component:"):
            cid = v[len("component:"):]
            c = (components or {}).get(cid)
            if k == "load":
                vals[k] = (f"the {cid}'s mass ({_rng(c.mass)})" if c is not None and c.mass is not None
                           else f"the {cid}'s mass")
            else:
                vals[k] = f"the {cid}"
    comp = (components or {}).get(vals.get("component"))
    if comp is not None:
        if comp.shape == "cylinder":
            d = comp.dims["diameter"]
            vals["component"] = f"{comp.id} (Ø{_rng(d)} mm cylinder)"
        else:
            vals["component"] = f"{comp.id} ({' × '.join(_rng(comp.dims[k]) for k in ('along', 'across', 'down'))} mm box)"
    try:
        return fm.plain.format(**{k: (v if v not in (None, "") else "—") for k, v in vals.items()})
    except (KeyError, IndexError):
        return fm.doc


def _rng(q: Quantity) -> str:
    return f"{q.nominal:g}" if not q.ranged else f"{q.lo:g}–{q.hi:g}"


def vocabulary() -> list:
    """The forms, their parameters and an example each (MCP `get_check_vocabulary`)."""
    out = [fm.as_dict() for fm in FORMS.values()]
    out.append({"form": "descriptive", "family": "descriptive", "kind": "any", "rung": 0,
                "doc": "The check cannot be computed with this vocabulary.  It is shown as 'descriptive, not run' "
                       "and never counts as passing.", "params": [{"name": "reason", "type": "text", "required": True,
                                                                   "doc": "why it cannot be computed"}],
                "example": {"form": "descriptive", "reason": "proportions need a learned scorer (rung 3)"},
                "reads_as": "Descriptive, not run: {reason}"})
    return out


# ---------------------------------------------------------------- geometry targets

@dataclass
class Target:
    text: str
    shapes: list = field(default_factory=list)
    points: list = field(default_factory=list)       # Vec3
    normal: object = None                            # Vec3 (holes: drilling normal)
    diameters: list = field(default_factory=list)    # holes
    features: list = field(default_factory=list)
    hole_feature: str | None = None
    face_ref: str | None = None


def _parse_ref(text: str, design):
    """'R.body.side(wall)' -> Ref; feature ids contain dots, so the longest id prefix wins."""
    from .refs import Ref, at_least
    t = text.strip()
    ids = sorted((f.id for f in design.features), key=len, reverse=True)
    for fid in ids:
        if t.startswith(fid + "."):
            rest = t[len(fid) + 1:]
            if "(" in rest and rest.endswith(")"):
                role, src = rest[:rest.index("(")], rest[rest.index("(") + 1:-1]
            else:
                role, src = rest, None
            if not role or not role.replace("_", "").isalnum():
                break
            if src == "*":
                return Ref(fid, role, None, at_least(1), any_source=True)
            return Ref(fid, role, src, at_least(1))
    return None


def resolve(env: Env, text) -> Target:
    """A binding reference -> shapes / points on the build (raises BindingError)."""
    from . import kernel as K
    design, b = env.design, env.build
    t = str(text or "").strip()
    if not t:
        raise BindingError("empty reference")
    name = t[len("export:"):] if t.startswith("export:") else t
    if name in design.exports:
        try:
            shapes = b.resolve(design.exports[name])
        except Exception as e:   # noqa: BLE001
            raise BindingError(f"export '{name}' does not resolve: {e}") from None
        return _target_from_shapes(env, t, shapes)
    if t.startswith("export:"):
        raise BindingError(f"no export '{name}' in this design (exports: {', '.join(sorted(design.exports)) or 'none'})")
    ids = [f.id for f in design.features]
    if t in ids:
        try:
            rec = b.record(t)
        except KeyError:
            raise BindingError(f"feature '{t}' was not built") from None
        det = rec.detail or {}
        if det.get("centres"):
            n = det.get("normal")
            tg = Target(t, [], [c if isinstance(c, K.Vec3) else K.Vec3(*c) for c in det["centres"]],
                        n if isinstance(n, K.Vec3) or n is None else K.Vec3(*n),
                        [float(det.get("diameter") or 0.0)] * len(det["centres"]), [t], t, det.get("on"))
            tg.shapes = [b.faces()[i] for i in env.feature_faces(t)]
            return tg
        faces = [b.faces()[i] for i in env.feature_faces(t)]
        if not faces:
            raise BindingError(f"feature '{t}' has no faces in this build")
        return _target_from_shapes(env, t, faces, [t])
    ref = _parse_ref(t, design)
    if ref is None:
        raise BindingError(f"'{t}' is not an export ({', '.join(sorted(design.exports)) or 'none'}), a feature id "
                           f"({', '.join(ids)}) or a reference like R.body.side(wall)")
    try:
        shapes = b.resolve(ref)
    except Exception as e:   # noqa: BLE001
        raise BindingError(f"reference '{t}' does not resolve: {type(e).__name__}: {e}") from None
    return _target_from_shapes(env, t, shapes, [ref.feature])


def _target_from_shapes(env, text, shapes, features=None) -> Target:
    from . import kernel as K
    pts = [K.centroid(s) for s in shapes]
    feats = list(features or [])
    for s in shapes:
        for e in env.build.ledger.who(s):
            if e.tag.feature not in feats:
                feats.append(e.tag.feature)
    return Target(text, list(shapes), pts, None, [], feats)


def _mean(points):
    from . import kernel as K
    n = len(points)
    return K.Vec3(sum(p.x for p in points) / n, sum(p.y for p in points) / n, sum(p.z for p in points) / n)


def _face_ids(env: Env, shapes) -> list:
    from . import kernel as K
    smap = K.ShapeMap()
    for f in env.faces:
        smap.Add(f)
    out = []
    for s in shapes:
        i = smap.FindIndex(s) - 1
        if i >= 0 and i not in out:
            out.append(i)
    return sorted(out)


def _direction(shape):
    """Unit direction of a planar face (normal), a line edge, or a cylinder/cone face (axis)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Line, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopoDS import TopoDS

    from . import kernel as K
    if shape.ShapeType() == TopAbs_FACE:
        s = BRepAdaptor_Surface(TopoDS.Face(shape))
        t = s.GetType()
        if t == GeomAbs_Plane:
            return K.face_normal(shape)
        if t in (GeomAbs_Cylinder, GeomAbs_Cone):
            d = (s.Cylinder() if t == GeomAbs_Cylinder else s.Cone()).Axis().Direction()
            return K.Vec3(d.X(), d.Y(), d.Z())
    if shape.ShapeType() == TopAbs_EDGE:
        c = BRepAdaptor_Curve(TopoDS.Edge(shape))
        if c.GetType() == GeomAbs_Line:
            d = c.Line().Direction()
            return K.Vec3(d.X(), d.Y(), d.Z())
    raise BindingError("parallel needs planar faces, straight edges, cylinders or holes")


def _dir_of(tg: Target):
    if tg.normal is not None:
        return tg.normal.unit()
    if len(tg.shapes) != 1:
        raise BindingError(f"'{tg.text}' must resolve to one face or edge for a direction (got {len(tg.shapes)})")
    return _direction(tg.shapes[0]).unit()


def _outer_face(face):
    """The face bounded by its outer wire only (holes in it ignored)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS
    w = BRepTools.OuterWire_s(TopoDS.Face(face))
    return BRepBuilderAPI_MakeFace(w, True).Face(), w


def _inside_and_edge_distance(face, p) -> tuple[bool, float]:
    """(p projected onto the face lies inside its outer boundary, distance to that boundary)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON
    from OCP.gp import gp_Pnt
    of, w = _outer_face(face)
    cl = BRepClass_FaceClassifier(of, gp_Pnt(p.x, p.y, p.z), 1e-6)
    inside = cl.State() in (TopAbs_IN, TopAbs_ON)
    d = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(p.x, p.y, p.z)).Vertex(), w)
    d.Perform()
    return inside, float(d.Value())


def _face_of_hole(env: Env, tg: Target):
    if not tg.face_ref:
        raise BindingError(f"'{tg.text}' is not a hole feature (no drilled face)")
    return resolve(env, tg.face_ref).shapes[0]


def _plane_axes(n):
    from . import kernel as K
    ref = K.Vec3(1, 0, 0) if abs(n.x) < 0.9 else K.Vec3(0, 1, 0)
    u = (ref - n * ref.dot(n)).unit()
    return u, n.cross(u).unit()


def _q_exact(v, unit, label):
    return Quantity.exact(v, unit, "geometry", label)


def _pos_q(env, v, label, distance=None):
    t = env.tol("position_tolerance", abs(v) if distance is None else distance)
    return Quantity(v, v + t.lo, v + t.hi, "mm", t.source, "pack default", label, t.placeholder)


def _result(env, spec, fm: Form, plain, terms, **kw) -> CheckResult:
    return IntentCheck._result(_FormCheck(fm), spec, env, plain, terms, **kw)


class _FormCheck(IntentCheck):
    def __init__(self, fm: Form):
        self.kind, self.rung = fm.kind, fm.rung


# ---------------------------------------------------------------- relations

@form("coincident", "relation", "relation", 1, "Two points coincide (face centroids, hole centres, vertices).",
      [P("a", "ref", doc="first point"), P("b", "ref", doc="second point"),
       P("tolerance", "number", False, str(RELATION_TOL), "mm")],
      {"a": "A.3.cable", "b": "export:mount_face"}, "{a} coincides with {b} (within {tolerance} mm)")
def _coincident(env, spec, bd, comps):
    a, b = resolve(env, bd["a"]), resolve(env, bd["b"])
    tol = number(bd.get("tolerance", RELATION_TOL), env.params, "tolerance")
    pa, pb = _mean(a.points), _mean(b.points)
    d = (pa - pb).length()
    t = term("distance between the points", f"{a.text} coincides with {b.text}", "mm", "<=", lambda d: d,
             lambda d: tol, {"d": _q_exact(d, "mm", "distance")}, formula=f"|a − b| ≤ {tol:g} mm")
    return _result(env, spec, FORMS["coincident"], t.plain, [t], features=a.features + b.features,
                   faces=_face_ids(env, a.shapes + b.shapes),
                   method_assumptions=["Points are centroids (faces) or centres (holes); several points are averaged",
                                       "Design geometry (relations are exact; print tolerance does not apply)"])


@form("centered_on", "relation", "relation", 1,
      "A feature's centre (a hole pattern's mean centre) lies on a face's centre, optionally only along some axes.",
      [P("item", "ref", doc="hole feature, face or export"), P("on", "ref", doc="planar face"),
       P("axes", "text", False, None, "e.g. X or X,Z (default: both in-plane directions)"),
       P("center", "enum", False, "centroid", "centroid | bbox", ("centroid", "bbox")),
       P("tolerance", "number", False, str(RELATION_TOL), "mm")],
      {"item": "A.3.cable", "on": "mount_face", "axes": "X"}, "{item} is centred on {on} (along {axes})")
def _centered_on(env, spec, bd, comps):
    from . import kernel as K
    it, on = resolve(env, bd["item"]), resolve(env, bd["on"])
    if len(on.shapes) != 1:
        raise BindingError(f"'{on.text}' must be one face")
    tol = number(bd.get("tolerance", RELATION_TOL), env.params, "tolerance")
    if bd.get("center", "centroid") == "bbox":
        lo, hi = K.bbox(on.shapes[0])
        c = (lo + hi) * 0.5
    else:
        c = K.centroid(on.shapes[0])
    off = _mean(it.points) - c
    axes = [vector(a) for a in str(bd.get("axes") or "").split(",") if a.strip()] if bd.get("axes") else None
    if axes is None:
        n = K.face_normal(on.shapes[0])
        off = off - n * off.dot(n)
        d = off.length()
    else:
        d = math.sqrt(sum((off.x * a[0] + off.y * a[1] + off.z * a[2]) ** 2 for a in axes))
    t = term("offset from the face centre", f"{it.text} is centred on {on.text}", "mm", "<=", lambda d: d,
             lambda d: tol, {"d": _q_exact(d, "mm", "offset")}, formula=f"|centre − face centre| ≤ {tol:g} mm")
    return _result(env, spec, FORMS["centered_on"], t.plain, [t], features=it.features,
                   faces=_face_ids(env, it.shapes + on.shapes),
                   method_assumptions=[f"Face centre = {'bounding-box centre' if bd.get('center') == 'bbox' else 'area centroid'}",
                                       "Design geometry (exact relation)"])


@form("symmetric_about", "relation", "relation", 1,
      "Points (hole centres) are mirror-symmetric about a plane through a reference, with a given normal.",
      [P("items", "ref", doc="hole feature or faces"), P("about", "ref", doc="face/point the plane passes through"),
       P("normal", "vector", doc="plane normal, e.g. X"), P("tolerance", "number", False, str(RELATION_TOL), "mm")],
      {"items": "A.P.holes", "about": "mount_face", "normal": "X"}, "{items} are symmetric about the {normal} plane through {about}")
def _symmetric(env, spec, bd, comps):
    from . import kernel as K
    it, ab = resolve(env, bd["items"]), resolve(env, bd["about"])
    n = K.Vec3(*vector(bd["normal"], "normal"))
    o = _mean(ab.points)
    tol = number(bd.get("tolerance", RELATION_TOL), env.params, "tolerance")
    worst = 0.0
    for p in it.points:
        m = p - n * (2 * (p - o).dot(n))
        worst = max(worst, min((m - q).length() for q in it.points))
    t = term("mirror mismatch", f"{it.text} mirror onto each other", "mm", "<=", lambda d: d, lambda d: tol,
             {"d": _q_exact(worst, "mm", "largest mirror mismatch")}, formula=f"max |mirror(p) − nearest q| ≤ {tol:g} mm")
    return _result(env, spec, FORMS["symmetric_about"], t.plain, [t], features=it.features,
                   faces=_face_ids(env, it.shapes), method_assumptions=["Design geometry (exact relation)"])


@form("parallel", "relation", "relation", 1, "Two planar faces, straight edges, cylinders or holes are parallel.",
      [P("a", "ref"), P("b", "ref"), P("tolerance_deg", "number", False, "0.1", "degrees")],
      {"a": "wall_face", "b": "mount_face"}, "{a} is parallel to {b}")
def _parallel(env, spec, bd, comps):
    a, b = resolve(env, bd["a"]), resolve(env, bd["b"])
    da, db = _dir_of(a), _dir_of(b)
    ang = math.degrees(math.acos(min(1.0, abs(da.dot(db)))))
    tol = number(bd.get("tolerance_deg", 0.1), env.params, "tolerance_deg")
    t = term("angle between", f"{a.text} ∥ {b.text}", "deg", "<=", lambda x: x, lambda x: tol,
             {"x": _q_exact(round(ang, 6), "deg", "angle")}, formula=f"angle ≤ {tol:g}°")
    return _result(env, spec, FORMS["parallel"], t.plain, [t], features=a.features + b.features,
                   faces=_face_ids(env, a.shapes + b.shapes), method_assumptions=["Directions ignore sense (lines)"])


@form("distance_between", "relation", "relation", 1,
      "The least distance between two references is within [min, max] (either may be omitted).",
      [P("a", "ref"), P("b", "ref"), P("min", "range", False, None, "mm"), P("max", "range", False, None, "mm")],
      {"a": "A.3.cable", "b": "A.P.holes", "min": "8"}, "{a} and {b} are between {min} and {max} mm apart")
def _distance(env, spec, bd, comps):
    from . import kernel as K
    a, b = resolve(env, bd["a"]), resolve(env, bd["b"])
    if "min" not in bd and "max" not in bd:
        raise BindingError("distance_between needs min and/or max")
    sa = a.shapes or []
    sb = b.shapes or []
    if sa and sb:
        d = min(K.distance(x, y) for x in sa for y in sb)
    else:
        d = min((p - q).length() for p in a.points for q in b.points)
    terms = []
    if "min" in bd:
        lim = range_q(bd["min"], env.params, "minimum distance")
        terms.append(term("distance ≥ min", f"{a.text} at least {_rng(lim)} mm from {b.text}", "mm", ">=",
                          lambda d, lim: d, lambda d, lim: lim, {"d": _pos_q(env, d, "distance"), "lim": lim},
                          formula="least distance ≥ min"))
    if "max" in bd:
        lim = range_q(bd["max"], env.params, "maximum distance")
        terms.append(term("distance ≤ max", f"{a.text} at most {_rng(lim)} mm from {b.text}", "mm", "<=",
                          lambda d, lim: d, lambda d, lim: lim, {"d": _pos_q(env, d, "distance"), "lim": lim},
                          formula="least distance ≤ max"))
    return _result(env, spec, FORMS["distance_between"], terms[0].plain, terms, features=a.features + b.features,
                   faces=_face_ids(env, sa + sb),
                   method_assumptions=["Least distance between the resolved shapes (or points)",
                                       "Worst case adds the process's positional tolerance (provisional)"])


@form("inside_face", "relation", "relation", 1,
      "Points (hole centres, with their radius) lie inside a face's outer boundary, at least `margin` from it.",
      [P("items", "ref"), P("face", "ref", False, None, "planar face (default: the face a hole is drilled in)"),
       P("margin", "range", False, "0", "mm beyond the hole edge")],
      {"items": "A.3.cable", "face": "mount_face", "margin": "2"}, "{items} lies inside {face}, {margin} mm from its edge")
def _inside_face(env, spec, bd, comps):
    it = resolve(env, bd["items"])
    face = resolve(env, bd["face"]).shapes[0] if bd.get("face") else _face_of_hole(env, it)
    lim = range_q(bd.get("margin", "0"), env.params, "margin")
    terms = []
    for k, p in enumerate(it.points):
        r = (it.diameters[k] / 2) if it.diameters else 0.0
        inside, d = _inside_and_edge_distance(face, p)
        v = (d - r) if inside else -(d + r)
        terms.append(term(f"point {k} edge margin", f"{it.text} {k} lies inside the face", "mm", ">=",
                          lambda v, lim: v, lambda v, lim: lim, {"v": _pos_q(env, v, "distance to the face edge"),
                                                                 "lim": lim},
                          formula="distance(centre, outer boundary) − r ≥ margin"))
    return _result(env, spec, FORMS["inside_face"], f"{it.text} lies inside the face", terms, features=it.features,
                   faces=_face_ids(env, [face] + it.shapes),
                   method_assumptions=["Outer boundary of the face only (its other holes are not counted)",
                                       "Worst case adds the process's positional tolerance (provisional)"])


# ---------------------------------------------------------------- pack rules

RAY_TMIN = 0.1   # mm: below twice the display mesh's chord error a start point may sit off the true surface


def _ray_thickness(it, origin, direction, tmax: float) -> float | None:
    """First exit of a ray from inside the material.  Starts on a tessellation facet, which can lie
    up to the chord error (0.05 mm) off the true surface, so crossings closer than RAY_TMIN are
    skipped (a measured wall is at most that much too thick)."""
    from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
    it.Perform(gp_Lin(gp_Pnt(*origin), gp_Dir(*direction)), RAY_TMIN, tmax)
    best = None
    for i in range(1, it.NbPnt() + 1):
        w = it.WParameter(i)
        if w > RAY_TMIN and (best is None or w < best):
            best = w
    return best


@form("min_wall", "pack rule", "rule", 1,
      "The thinnest wall (ray-cast inward from sampled surface facets) is at least the process minimum "
      "(two perimeters × extrusion width), as printed.",
      [P("scope", "text", False, "part", "part, or a comma-separated list of references"),
       P("min", "range", False, None, "mm (default: fdm_printing two perimeters)")],
      {"scope": "part"}, "Every wall of the {scope} is at least {min} minimum thickness (mm) as printed")
def _min_wall(env, spec, bd, comps):
    import numpy as np

    from .resolution import facet_table
    p = env.fdm()
    if bd.get("min"):
        lim = range_q(bd["min"], env.params, "minimum wall")
    else:
        if p is None:
            raise BindingError("no process pack for a default minimum wall")
        noz = packs.mm(env.context.get("nozzle", p["defaults"]["nozzle"]))
        w = noz * p["extrusion_width_factor"]["value"] * p["min_wall_perimeters"]["value"]
        lim = Quantity(w, w, w, "mm", "fdm_printing.min_wall_perimeters", "pack default", "two perimeters", True)
    area, nv, cen, face, P_ = env.mesh()
    scope = str(bd.get("scope") or "part")
    keep = np.ones(len(area), dtype=bool)
    feats = []
    if scope != "part":
        ids = set()
        for r in scope.split(","):
            tg = resolve(env, r.strip())
            ids |= set(_face_ids(env, tg.shapes))
            feats += tg.features
        keep = np.array([f in ids for f in face])
    idx = np.nonzero(keep & (area > 1e-6))[0]
    if len(idx) == 0:
        raise BindingError("no surface in scope")
    stride = max(1, len(idx) // 600)
    sample = idx[::stride]
    lo, hi = np.asarray(P_).min(axis=0), np.asarray(P_).max(axis=0)
    tmax = float(np.linalg.norm(hi - lo)) + 1.0
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    it = IntCurvesFace_ShapeIntersector()
    it.Load(env.build.shape, 1e-6)
    best, where = math.inf, None
    for i in sample:
        o = cen[i]
        th = _ray_thickness(it, tuple(float(x) for x in o), tuple(float(-x) for x in nv[i]), tmax)
        if th is not None and th < best:
            best, where = th, int(face[i])
    if not math.isfinite(best):
        raise BindingError("no wall found by the rays")
    dim = env.tol("dimension_tolerance")
    thin = env.fdm()["thin_wall_delta"] if env.fdm() else None
    lo_t = dim.lo + (thin["lo"] if thin else 0.0)
    q = Quantity(best, best + lo_t, best + max(0.0, dim.hi), "mm", dim.source, "pack default",
                 "thinnest wall (as printed: bias − band + thin-wall delta)", dim.placeholder)
    t = term("thinnest wall", f"Walls are at least {_rng(lim)} mm thick as printed", "mm", ">=",
             lambda v, lim: v, lambda v, lim: lim, {"v": q, "lim": lim}, formula="min ray thickness ≥ min wall")
    return _result(env, spec, FORMS["min_wall"], t.plain, [t], faces=[where] if where is not None else [],
                   features=feats, method_assumptions=[
                       f"Thickness = distance along the inward normal from {len(sample)} sampled facet centres to the "
                       f"next surface (sampled; sharp tips read thin; walls under {RAY_TMIN:g} mm are not resolved)",
                       "As printed: XY bias − band (packs dimension_tolerance) and the thin-wall delta"])


@form("overhang", "pack rule", "rule", 1,
      "The steepest unsupported overhang in the print orientation (inferred or accepted) is within the pack limit.",
      [P("limit", "number", False, None, "degrees (default: fdm_printing 45°)")],
      {}, "Prints without supports (overhang within {limit} limit, degrees from vertical)")
def _overhang(env, spec, bd, comps):
    r = Overhang().evaluate(env, spec)
    if not r.ran:
        raise BindingError(r.reason)
    if bd.get("limit"):
        lim = number(bd["limit"], env.params, "limit")
        worst = r.terms[0].nominal
        t = term("steepest unsupported overhang", f"No overhang steeper than {lim:g}° from vertical", "deg", "<=",
                 lambda a: a, lambda a: lim, {"a": Quantity.exact(worst, "deg", "tessellation")},
                 formula=f"max overhang angle ≤ {lim:g}°")
        r = _result(env, spec, FORMS["overhang"], r.plain, [t], faces=r.faces, assumptions=r.assumptions,
                    method_assumptions=r.method_assumptions)
    r.kind, r.rung = spec.get("kind") or "rule", 1
    return r


@form("hole_edge_distance", "pack rule", "rule", 1,
      "Every hole centre is at least factor × Ø from its face's outer edge and from the other holes in that face.",
      [P("holes", "ref", doc="hole feature"), P("factor", "range", False, "2", "× hole Ø (arch §8.2: 2)")],
      {"holes": "A.P.holes", "factor": "2"}, "Every hole of {holes} is at least {factor} × Ø from an edge")
def _hole_edge(env, spec, bd, comps):
    tg = resolve(env, bd["holes"])
    if not tg.diameters:
        raise BindingError(f"'{tg.text}' is not a hole feature")
    face = _face_of_hole(env, tg)
    fac = range_q(bd.get("factor", "2"), env.params, "factor", unit="")
    terms = []
    others = []
    for r in env.build.records:
        det = r.detail or {}
        if det.get("centres") and det.get("on") == tg.face_ref:
            for k, c in enumerate(det["centres"]):
                others.append((r.id, k, c, float(det.get("diameter") or 0.0)))
    for k, p in enumerate(tg.points):
        dia = tg.diameters[k]
        inside, d = _inside_and_edge_distance(face, p)
        dd = d if inside else -d
        for fid, kk, c, dia2 in others:
            if fid == tg.hole_feature and kk == k:
                continue
            dd = min(dd, (p - c).length() - dia2 / 2)
        terms.append(term(f"hole {k} edge distance", f"Hole {k} is at least {_rng(fac)}×Ø from an edge", "mm", ">=",
                          lambda d, f: d, lambda d, f: f * dia, {"d": _pos_q(env, dd, "centre to nearest edge"), "f": fac},
                          formula=f"distance(centre, edge or other hole) ≥ factor × Ø{dia:g}"))
    return _result(env, spec, FORMS["hole_edge_distance"], terms[0].plain if terms else "", terms,
                   features=tg.features, faces=_face_ids(env, [face] + tg.shapes),
                   method_assumptions=["Edge = the drilled face's outer boundary or the wall of another hole in it",
                                       "Worst case adds the process's positional tolerance (provisional)"])


@form("bridging", "pack rule", "rule", 1,
      "Horizontal round holes (axis ⊥ build direction) are small enough to print without support.",
      [P("holes", "text", False, "all", "all, or a comma-separated list of hole features"),
       P("max", "number", False, None, "Ø mm (default: fdm_printing horizontal_hole_max_d)")],
      {"holes": "all"}, "Horizontal holes ({holes}) print without support (Ø within {max} limit, mm)")
def _bridging(env, spec, bd, comps):
    p = env.fdm()
    if p is None or env.orientation is None:
        raise BindingError("no print orientation for this process")
    up = env.orientation["up"]
    lim = (Quantity(number(bd["max"], env.params, "max"), number(bd["max"], env.params, "max"),
                    number(bd["max"], env.params, "max"), "mm", "binding", "model", "max")
           if bd.get("max") else Quantity.from_pack(p["horizontal_hole_max_d"], "fdm_printing.horizontal_hole_max_d",
                                                    "largest unsupported horizontal hole"))
    which = str(bd.get("holes") or "all")
    names = None if which == "all" else {s.strip() for s in which.split(",")}
    biggest, feats = 0.0, []
    for r in env.build.records:
        det = r.detail or {}
        if not det.get("centres") or (names is not None and r.id not in names):
            continue
        n = det.get("normal")
        if n is None:
            continue
        nn = (n.x, n.y, n.z) if hasattr(n, "x") else tuple(n)
        if abs(sum(a * b for a, b in zip(nn, up))) > 0.1:
            continue
        d = max(float(det.get("diameter") or 0.0), float(det.get("head") or 0.0))
        feats.append(r.id)
        biggest = max(biggest, d)
    t = term("largest horizontal hole Ø", "Horizontal holes print without support", "mm", "<=", lambda d, lim: d,
             lambda d, lim: lim, {"d": _q_exact(biggest, "mm", "largest horizontal hole (incl. countersink head)"),
                                  "lim": lim}, formula="max horizontal Ø ≤ limit")
    return _result(env, spec, FORMS["bridging"], t.plain, [t], features=feats,
                   faces=sorted({i for f in feats for i in env.feature_faces(f)}),
                   method_assumptions=["Holes whose axis is within ≈6° of perpendicular to the build direction",
                                       "Countersink heads count at their head Ø"])


# ---------------------------------------------------------------- fit against component envelopes

class Projection:
    """The part projected along an axis: triangles in 2D (u lateral, v up) with face ids."""

    def __init__(self, env: Env, axis, up=(0.0, 0.0, 1.0)):
        import numpy as np
        a = np.asarray(axis, dtype=float)
        a /= np.linalg.norm(a)
        upv = np.asarray(up, dtype=float)
        v = upv - upv.dot(a) * a
        if np.linalg.norm(v) < 1e-9:
            raise BindingError("the cylinder axis must not be vertical")
        v /= np.linalg.norm(v)
        u = np.cross(v, a)
        self.a, self.u, self.v = a, u, v
        t = env.tessellation()
        Pp, I = t["P"], t["I"]
        Q = np.stack([Pp @ u, Pp @ v], axis=1)
        T = Q[I]                                             # (m, 3, 2)
        ar = 0.5 * np.abs((T[:, 1, 0] - T[:, 0, 0]) * (T[:, 2, 1] - T[:, 0, 1])
                          - (T[:, 2, 0] - T[:, 0, 0]) * (T[:, 1, 1] - T[:, 0, 1]))
        keep = ar > 1e-10
        self.T_all, self.face_all = T, t["face"]
        self.T = T[keep]
        self.face = t["face"][keep]
        self.lo = self.T.min(axis=1)
        self.hi = self.T.max(axis=1)
        self.vmin, self.vmax = float(self.lo[:, 1].min()), float(self.hi[:, 1].max())
        self.umin, self.umax = float(self.lo[:, 0].min()), float(self.hi[:, 0].max())
        self.along = Pp @ a

    def to2d(self, p) -> tuple:
        import numpy as np
        q = np.asarray([p.x, p.y, p.z], dtype=float)
        return float(q @ self.u), float(q @ self.v)

    def to3d(self, uu: float, vv: float, aa: float):
        from . import kernel as K
        q = self.u * uu + self.v * vv + self.a * aa
        return K.Vec3(*[float(x) for x in q])

    def _near(self, c, r):
        m = ((self.lo[:, 0] <= c[0] + r) & (self.hi[:, 0] >= c[0] - r) & (self.lo[:, 1] <= c[1] + r)
             & (self.hi[:, 1] >= c[1] - r))
        return m

    def dist(self, c, r_hint: float = 50.0, mask=None):
        """Distance from point c to the union of triangles (0 inside), considering triangles
        within r_hint (inf when none); with `mask` only those triangles."""
        import numpy as np
        m = self._near(c, r_hint)
        if mask is not None:
            m &= mask
        if not m.any():
            return math.inf
        T = self.T[m]
        p = np.asarray(c, dtype=float)
        a, b, cc = T[:, 0], T[:, 1], T[:, 2]

        def cross(o, x, y):
            return (x[:, 0] - o[:, 0]) * (y[1] - o[:, 1]) - (x[:, 1] - o[:, 1]) * (y[0] - o[:, 0])
        d1, d2, d3 = cross(a, b, p), cross(b, cc, p), cross(cc, a, p)
        inside = ((d1 >= 0) & (d2 >= 0) & (d3 >= 0)) | ((d1 <= 0) & (d2 <= 0) & (d3 <= 0))
        if inside.any():
            return 0.0

        def seg(s, e):
            se = e - s
            L2 = (se * se).sum(axis=1)
            L2[L2 == 0] = 1e-30
            tt = np.clip(((p - s) * se).sum(axis=1) / L2, 0, 1)
            q = s + se * tt[:, None]
            return np.sqrt(((q - p) ** 2).sum(axis=1))
        return float(min(seg(a, b).min(), seg(b, cc).min(), seg(cc, a).min()))

    def seg_dist(self, c, faces: set) -> float:
        """Distance from c to the projected edges of the triangles of `faces` (faces parallel to
        the axis project to segments, so this is the distance to their projected outline)."""
        import numpy as np
        m = np.array([f in faces for f in self.face_all])
        if not m.any():
            return math.inf
        T = self.T_all[m]
        p = np.asarray(c, dtype=float)
        best = math.inf
        for i in range(3):
            s0, e0 = T[:, i], T[:, (i + 1) % 3]
            se = e0 - s0
            L2 = (se * se).sum(axis=1)
            L2[L2 == 0] = 1e-30
            tt = np.clip(((p - s0) * se).sum(axis=1) / L2, 0, 1)
            q = s0 + se * tt[:, None]
            best = min(best, float(np.sqrt(((q - p) ** 2).sum(axis=1)).min()))
        return best

    def clear(self, c, r) -> bool:
        return self.dist(c, r + 1e-6) >= r - 1e-6

    def strip_hits(self, u0: float, vc: float, r: float, side: int) -> bool:
        """Does any triangle meet the half-infinite strip {u ≥ u0 (side +1) or u ≤ u0, |v − vc| < r}?"""
        import numpy as np
        h = r - 1e-4
        if side > 0:
            m = self.hi[:, 0] > u0 + 1e-9
            bu0, bu1 = u0, max(self.umax, u0) + 1.0
        else:
            m = self.lo[:, 0] < u0 - 1e-9
            bu0, bu1 = min(self.umin, u0) - 1.0, u0
        m &= (self.lo[:, 1] < vc + h) & (self.hi[:, 1] > vc - h)
        if not m.any():
            return False
        T = self.T[m]
        box = np.array([[bu0, vc - h], [bu1, vc - h], [bu1, vc + h], [bu0, vc + h]])
        # SAT on the triangle edge normals (the box axes were tested by the bbox filter)
        for i in range(3):
            e = T[:, (i + 1) % 3] - T[:, i]
            nrm = np.stack([-e[:, 1], e[:, 0]], axis=1)
            tp = np.einsum("mk,mjk->mj", nrm, T)
            bp = nrm @ box.T
            sep = (bp.max(axis=1) < tp.min(axis=1) - 1e-12) | (bp.min(axis=1) > tp.max(axis=1) + 1e-12)
            T, nrm = T[~sep], None
            if len(T) == 0:
                return False
        return True


def _drop(pr: Projection, u0: float, r: float):
    """Lower a disk of radius r at lateral u0 from above the part; let it settle sideways.
    Returns (u, v) of the rest centre, or None if it falls past the part."""
    v_top = pr.vmax + r + 1.0
    floor = pr.vmin - r - 1.0
    step = max(0.05, min(0.5, r / 4))

    def lower(u, v):
        while True:
            nv = v - step
            if nv < floor:
                return None
            if pr.clear((u, nv), r):
                v = nv
                continue
            a, b = v, nv
            for _ in range(30):
                mid = 0.5 * (a + b)
                if pr.clear((u, mid), r):
                    a = mid
                else:
                    b = mid
            return a

    v = lower(u0, v_top)
    if v is None:
        return None
    u = u0
    for _ in range(400):            # settle: slide sideways and down while that lowers the centre
        best = None
        s = max(0.05, r / 2)
        while s >= 0.02:
            for d in (-1.0, 1.0):
                uu = u + d * s
                if not pr.clear((uu, v + 0.01), r):
                    continue
                vv = lower(uu, v + 0.01)
                if vv is None:
                    return None
                if vv < v - 1e-4 and (best is None or vv < best[1]):
                    best = (uu, vv)
            if best is not None:
                break
            s /= 2
        if best is None:
            break
        u, v = best
    return u, v


def _escape_lift(pr: Projection, c, r: float, side: int, hmax: float) -> float:
    """Least lift before the disk at rest centre c can slide out toward `side` (+1/−1);
    `hmax` if something above blocks a straight lift."""
    step = 0.25
    h = 0.0
    prev = None
    while h <= hmax:
        if h > 0 and not pr.clear((c[0], c[1] + h), r):
            return hmax                       # a hood above: no lift-then-slide escape
        if not pr.strip_hits(c[0], c[1] + h, r, side):
            if prev is None:
                return 0.0
            a, b = prev, h
            for _ in range(20):
                mid = 0.5 * (a + b)
                if pr.strip_hits(c[0], c[1] + mid, r, side):
                    a = mid
                else:
                    b = mid
            return b
        prev = h
        h += step
    return hmax


def _cyl_params(env, bd, comps):
    from . import kernel as K
    cid = bd.get("component")
    comp: Component | None = comps.get(cid)
    if comp is None:
        raise BindingError(f"no component '{cid}' (components: {', '.join(sorted(comps)) or 'none'})")
    if comp.shape != "cylinder":
        raise BindingError(f"component '{cid}' is a {comp.shape}, not a cylinder")
    axis = vector(bd.get("axis", "X"), "axis")
    up = vector(bd.get("up", "Z"), "up")
    seat = resolve(env, bd["seat"])
    key = (round(axis[0], 9), round(axis[1], 9), round(axis[2], 9), round(up[0], 9), round(up[1], 9), round(up[2], 9))
    pr = env.cache.get(("proj", key))
    if pr is None:
        pr = env.cache[("proj", key)] = Projection(env, axis, up)
    sp = _mean(seat.points)
    u0, _v0 = pr.to2d(sp)
    a0 = float(K.Vec3(*axis).dot(sp))
    seat_faces = set(_face_ids(env, seat.shapes))
    return comp, pr, seat, u0, a0, seat_faces


def rest(env, bd, comps, D: float):
    """(u, v) rest centre of a Ø`D` rod in the cradle, cached per build."""
    comp, pr, seat, u0, a0, _sf = _cyl_params(env, bd, comps)
    k = ("rest", bd.get("component"), bd.get("seat"), bd.get("axis", "X"), bd.get("up", "Z"), round(D, 6))
    if k not in env.cache:
        env.cache[k] = _drop(pr, u0, D / 2)
    return env.cache[k]


def _rod_ghost(comp, pr, rc, a0, D, made_by, reviewed, note=""):
    if rc is None:
        return None
    c = pr.to3d(rc[0], rc[1], a0)
    span = float(pr.along.max() - pr.along.min())
    return {"component": comp.id, "shape": "cylinder", "center": [c.x, c.y, c.z],
            "axis": [float(x) for x in pr.a], "diameter": D, "length": min(comp.dims["length"].nominal, 3 * span + 60),
            "shortened": comp.dims["length"].nominal > 3 * span + 60, "made_by": made_by, "reviewed": reviewed,
            "note": note}


@form("holds_cylinder", "fit", "relation", 1,
      "A cylinder component (e.g. a rod Ø6–14) lowered onto the seat comes to rest in the cradle, for both ends "
      "of its diameter range: it is captured on both sides (escape lift > 0) and rests on the seat faces.",
      [P("component", "component", doc="a cylinder component id"),
       P("seat", "ref", doc="the face(s) it should rest on (export or reference)"),
       P("axis", "vector", False, "X", "cylinder axis direction"), P("up", "vector", False, "Z", "installed up")],
      {"component": "rod", "seat": "cradle_seat", "axis": "X"}, "Holds {component} on {seat} (axis {axis})")
def _holds(env, spec, bd, comps):
    comp, pr, seat, u0, a0, seat_faces = _cyl_params(env, bd, comps)
    dq = comp.dims["diameter"]
    terms, ghosts = [], []
    hmax = pr.vmax - pr.vmin + dq.hi + 2
    for D in sorted({dq.lo, dq.hi}):
        rc = rest(env, bd, comps, D)
        if rc is None:
            lift = -D
            gap = math.inf
        else:
            lift = min(_escape_lift(pr, rc, D / 2, -1, hmax), _escape_lift(pr, rc, D / 2, 1, hmax))
            gap = pr.seg_dist(rc, seat_faces) - D / 2
        t = env.tol("position_tolerance", D)
        terms.append(term(f"Ø{D:g} captured", f"A Ø{D:g} mm {comp.id} comes to rest inside the cradle", "mm", ">=",
                          lambda v: v, lambda v: 0.0,
                          {"v": Quantity(lift, lift + t.lo, lift + t.hi, "mm", t.source, "pack default",
                                         f"escape lift of Ø{D:g} (−Ø: falls past the part)", t.placeholder)},
                          thin_abs=1.0, formula="min(escape lift left, right) > 0"))
        if seat_faces:
            g = gap if math.isfinite(gap) else 1e3
            terms.append(term(f"Ø{D:g} on the seat", f"A Ø{D:g} mm {comp.id} rests on the seat faces", "mm", "<=",
                              lambda v: v, lambda v: CONTACT_TOL, {"v": _q_exact(round(g, 4), "mm", "gap to the seat")},
                              formula=f"gap(rest, seat) ≤ {CONTACT_TOL:g} mm (contact)"))
        gh = _rod_ghost(comp, pr, rc, a0, D, comp.made_by, comp.reviewed, f"Ø{D:g} at rest")
        if gh:
            ghosts.append(gh)
    rcn = rest(env, bd, comps, dq.nominal)
    gh = _rod_ghost(comp, pr, rcn, a0, dq.nominal, comp.made_by, comp.reviewed, "nominal")
    return _result(env, spec, FORMS["holds_cylinder"], f"Holds a Ø{_rng(dq)} mm {comp.id}", terms,
                   features=seat.features, faces=_face_ids(env, seat.shapes),
                   method_assumptions=[
                       "The part is projected along the cylinder axis (a long rod spans the whole part)",
                       "The rod is lowered from above the seat and settles sideways under gravity; no friction",
                       "Escape lift: least rise before it can slide out sideways (lift-then-slide)",
                       f"Contact within {CONTACT_TOL:g} mm on the display tessellation; rigid part, no snap fit"],
                   ghosts=[gh] if gh else [])


@form("retention", "fit", "relation", 1,
      "A rod resting in the cradle cannot leave it sideways without lifting at least `min_lift` (both diameter "
      "ends, both sides).",
      [P("component", "component"), P("seat", "ref"), P("min_lift", "range", doc="mm"),
       P("axis", "vector", False, "X"), P("up", "vector", False, "Z")],
      {"component": "rod", "seat": "cradle_seat", "min_lift": "5"},
      "{component} cannot leave the cradle without lifting at least {min_lift} mm")
def _retention(env, spec, bd, comps):
    comp, pr, seat, u0, a0, _sf = _cyl_params(env, bd, comps)
    lim = range_q(bd["min_lift"], env.params, "minimum lift")
    dq = comp.dims["diameter"]
    hmax = pr.vmax - pr.vmin + dq.hi + 2
    terms = []
    for D in sorted({dq.lo, dq.hi}):
        rc = rest(env, bd, comps, D)
        lifts = ([-D, -D] if rc is None else
                 [_escape_lift(pr, rc, D / 2, s, hmax) for s in (-1, 1)])
        for side, lift in zip(("toward −u", "toward +u"), lifts):
            t = env.tol("position_tolerance", D)
            terms.append(term(f"Ø{D:g} lift {side}", f"A Ø{D:g} mm {comp.id} must lift ≥ {_rng(lim)} mm to escape",
                              "mm", ">=", lambda v, lim: v, lambda v, lim: lim,
                              {"v": Quantity(lift, lift + t.lo, lift + t.hi, "mm", t.source, "pack default",
                                             "escape lift", t.placeholder), "lim": lim},
                              formula="escape lift ≥ min_lift"))
    return _result(env, spec, FORMS["retention"], f"{comp.id} cannot leave without lifting {_rng(lim)} mm", terms,
                   features=seat.features, faces=_face_ids(env, seat.shapes),
                   method_assumptions=["Lift-then-slide escape in the projection along the axis (minimax height for a "
                                       "cradle with a lip); sliding out along the axis is not considered",
                                       "Rigid part and rod; no friction"])


def _box_clearance(shape, center, frame, half, wall=None) -> float:
    """Signed clearance of a box (centre, frame (a, u, v), half sizes) to the part and to the
    half-space behind `wall` (point, room-facing normal): negative = penetration depth."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    a, u, v = frame

    def box(inset):
        hx, hy, hz = (max(1e-3, h - inset) for h in half)
        o = center - a * hx - u * hy - v * hz
        return BRepPrimAPI_MakeBox(gp_Ax2(gp_Pnt(o.x, o.y, o.z), gp_Dir(v.x, v.y, v.z), gp_Dir(a.x, a.y, a.z)),
                                   2 * hx, 2 * hy, 2 * hz).Shape()

    def dist(inset):
        d = BRepExtrema_DistShapeShape(box(inset), shape)
        d.Perform()
        return d.Value() if d.IsDone() else 0.0

    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    clr = dist(0.0)
    cl = BRepClass3d_SolidClassifier(shape, gp_Pnt(center.x, center.y, center.z), 1e-7)
    if clr <= 1e-7 or cl.State() == TopAbs_IN:
        lo, hi = 0.0, min(half)
        if dist(hi - 1e-3) <= 1e-7:
            clr = -hi
        else:
            for _ in range(25):
                mid = 0.5 * (lo + hi)
                if dist(mid) > 1e-7:
                    hi = mid
                else:
                    lo = mid
            clr = -hi
    if wall is not None:
        wp, wn = wall
        corners = [center + a * (sa * half[0]) + u * (su * half[1]) + v * (sv * half[2])
                   for sa in (-1, 1) for su in (-1, 1) for sv in (-1, 1)]
        clr = min(clr, min((c - wp).dot(wn) for c in corners))
    return float(clr)


def _wall(env, bd):
    from . import kernel as K
    w = bd.get("wall") or ("export:wall_face" if "wall_face" in env.design.exports else None)
    if not w:
        return None, None
    tg = resolve(env, w)
    if len(tg.shapes) != 1:
        raise BindingError(f"wall '{w}' must be one planar face")
    n = K.face_normal(tg.shapes[0])        # outward from the part: into the wall
    return (K.centroid(tg.shapes[0]), -n), tg


@form("clears_box", "fit", "relation", 1,
      "A box component (e.g. a reel) hanging from a held cylinder component, offset along its axis, clears the part "
      "and the wall, for every corner of the size and offset ranges.",
      [P("component", "component", doc="a box component id"),
       P("hangs_from", "component", doc="the cylinder component it hangs from (e.g. rod)"),
       P("seat", "ref", doc="the seat the cylinder rests on (as in holds_cylinder)"),
       P("along", "range", False, "0", "offset along the axis from the seat, mm"),
       P("axis", "vector", False, "X"), P("up", "vector", False, "Z"),
       P("wall", "ref", False, None, "planar face against the wall (default: export wall_face)")],
      {"component": "reel", "hangs_from": "rod", "seat": "cradle_seat", "along": "60..200"},
      "{component} hanging from {hangs_from} ({along} mm along it) clears the part and the wall")
def _clears_box(env, spec, bd, comps):
    from . import kernel as K
    box = comps.get(bd.get("component"))
    if box is None or box.shape != "box":
        raise BindingError(f"'{bd.get('component')}' is not a box component")
    cbd = {**bd, "component": bd["hangs_from"]}
    rod, pr, seat, u0, a0, _sf = _cyl_params(env, cbd, comps)
    along = range_q(bd.get("along", "0"), env.params, "along")
    wall, wtg = _wall(env, bd)
    a, u, v = (K.Vec3(*[float(x) for x in pr.a]), K.Vec3(*[float(x) for x in pr.u]), K.Vec3(*[float(x) for x in pr.v]))
    dq = rod.dims["diameter"]
    al, ac, dn = (box.dims[k] for k in ("along", "across", "down"))
    worst, worst_at, nominal, ghost = math.inf, None, None, None
    for D in sorted({dq.nominal, dq.lo, dq.hi}):
        rc = rest(env, cbd, comps, D)
        if rc is None:
            raise BindingError(f"the Ø{D:g} {rod.id} does not come to rest on the seat (see holds_cylinder)")
        for off in sorted({along.nominal, along.lo, along.hi}):
            for big in (False, True):
                L, W, H = ((al.hi, ac.hi, dn.hi if dn.nominal >= 0 else dn.lo) if big else
                           (al.nominal, ac.nominal, dn.nominal))
                axis_pt = pr.to3d(rc[0], rc[1], a0 + off)
                centre = axis_pt - v * (H / 2) if H >= 0 else axis_pt + v * (abs(H) / 2)
                half = (L / 2, W / 2, abs(H) / 2)
                c = _box_clearance(env.build.shape, centre, (a, u, v), half, wall)
                if not big and D == dq.nominal and off == along.nominal:
                    nominal = c
                    ghost = {"component": box.id, "shape": "box", "center": [centre.x, centre.y, centre.z],
                             "axes": [[a.x, a.y, a.z], [u.x, u.y, u.z], [v.x, v.y, v.z]], "size": [L, W, abs(H)],
                             "made_by": box.made_by, "reviewed": box.reviewed, "note": f"{off:g} mm along"}
                if c < worst:
                    worst, worst_at = c, {"diameter": D, "along": off, "size": [L, W, H]}
    q = Quantity(nominal, min(worst, nominal), max(worst, nominal), "mm", "component ranges", "model",
                 f"clearance of {box.id} (worst at Ø{worst_at['diameter']:g}, {worst_at['along']:g} mm along)")
    t = term(f"{box.id} clearance", f"The {box.id} clears the part and the wall", "mm", ">=", lambda c: c,
             lambda c: 0.0, {"c": q}, thin_abs=3.0, formula="min distance(box, part ∪ wall) ≥ 0")
    t.worst_inputs = worst_at
    gh_rod = _rod_ghost(rod, pr, rest(env, cbd, comps, dq.nominal), a0, dq.nominal, rod.made_by, rod.reviewed)
    return _result(env, spec, FORMS["clears_box"], f"The {box.id} clears the part and the wall", [t],
                   features=seat.features, faces=_face_ids(env, seat.shapes + (wtg.shapes if wtg else [])),
                   method_assumptions=[
                       f"The {box.id} box hangs from the {rod.id} axis ({'below' if dn.nominal >= 0 else 'above'} it), "
                       "centred across, at the stated offset along",
                       "Worst case over the rod Ø ends, the offset ends and the largest box (monotone assumption)",
                       "The wall is the plane of the part's wall face" if wall else "No wall plane given"],
                   ghosts=[g for g in (ghost, gh_rod) if g])


# ---------------------------------------------------------------- hand calculations

def _load_q(env, bd, comps) -> Quantity:
    t = str(bd.get("load", ""))
    if t.startswith("component:"):
        c = comps.get(t[len("component:"):])
        if c is None or c.mass is None:
            raise BindingError(f"'{t}': no component with a mass")
        return c.mass
    return range_q(t, env.params, "load", unit="kg", source="binding")


def _load_point(env, bd, comps):
    t = str(bd.get("at", ""))
    if t.startswith("component:"):
        cid = t[len("component:"):]
        seat = bd.get("seat")
        if not seat:
            raise BindingError("a load at a component needs its 'seat'")
        cbd = {"component": cid, "seat": seat, "axis": bd.get("axis", "X"), "up": bd.get("up", "Z")}
        comp, pr, sg, u0, a0, _sf = _cyl_params(env, cbd, comps)
        rc = rest(env, cbd, comps, comp.dims["diameter"].nominal)
        if rc is None:
            raise BindingError(f"the {cid} does not come to rest on the seat")
        return pr.to3d(rc[0], rc[1], a0), sg.features
    tg = resolve(env, t)
    return _mean(tg.points), tg.features


def _wall_geometry(env, bd, comps):
    """(heights of the anchors above the pivot, lever L, anchor feature, faces, features)."""
    from . import kernel as K
    wall, wtg = _wall(env, bd)
    if wall is None:
        raise BindingError("no wall face: give 'wall' or export wall_face")
    up = K.Vec3(*vector(bd.get("up", "Z"), "up"))
    wf = wtg.shapes[0]
    lo_pt = min((K.Vec3(q.X(), q.Y(), q.Z()) for q in _vertices(wf)), key=lambda p: p.dot(up))
    p, feats = _load_point(env, bd, comps)
    L = (p - wall[0]).dot(wall[1])
    if L <= 0:
        raise BindingError("the load point is not in front of the wall")
    heights, anc = [], None
    if bd.get("anchors"):
        anc = resolve(env, bd["anchors"])
        if not anc.diameters:
            raise BindingError(f"'{anc.text}' is not a hole feature")
        heights = [(c - lo_pt).dot(up) for c in anc.points]
    return heights, L, anc, wtg, feats


def _vertices(face):
    from OCP.BRep import BRep_Tool
    from OCP.TopoDS import TopoDS

    from . import kernel as K
    return [BRep_Tool.Pnt_s(TopoDS.Vertex(v)) for v in K.subshapes(face, K.KINDS["vertex"])]


_LOAD_PARAMS = [P("load", "range", doc="kg, a range (0.2..1) or component:<id> (its mass)"),
                P("at", "ref", doc="where the load acts: a reference, or component:<id> (its rest centre)"),
                P("seat", "ref", False, None, "the seat, when the load is a component resting on it"),
                P("wall", "ref", False, None, "planar face against the wall (default: export wall_face)"),
                P("up", "vector", False, "Z"), P("axis", "vector", False, "X", "rod axis, for component loads"),
                P("duration", "enum", False, "sustained", "sustained (SF 4 on printed strength) | short (SF 2)",
                  ("sustained", "short")),
                P("safety_factor", "number", False, None, "a floor; the packs' factors apply when higher")]
_SECTION = [P("section_width", "number", True, None, "mm (expression of parameters allowed)"),
            P("section_depth", "number", True, None, "mm, in the bending plane"),
            P("section_at", "number", True, None, "distance of the checked section from the wall, mm"),
            P("stress_axis", "vector", False, "Y", "direction of the bending stress (along the arm)")]


def _floor(env, bd):
    return number(bd["safety_factor"], env.params, "safety_factor") if bd.get("safety_factor") else 0.0


def _anchor_terms(env, bd, comps):
    heights, L, anc, wtg, feats = _wall_geometry(env, bd, comps)
    if anc is None:
        raise BindingError("anchor pull-out needs 'anchors' (the wall-screw hole feature)")
    W = _load_q(env, bd, comps)
    a, sfa, _ = anchor_sf(env, _floor(env, bd))
    return anchor_term(env, heights, L, W, sfa, a), a, sfa, anc, wtg, feats, L


def _bend_terms(env, bd, comps):
    _h, L, _anc, wtg, feats = _wall_geometry(env, {**bd, "anchors": None}, comps)
    W = _load_q(env, bd, comps)
    sfm, sfm_name = material_sf(bd.get("duration", "sustained"), _floor(env, bd))
    b = number(bd["section_width"], env.params, "section_width")
    h = number(bd["section_depth"], env.params, "section_depth")
    ys = number(bd["section_at"], env.params, "section_at")
    t, across = bending_term(env, W, L, b, h, ys, vector(bd.get("stress_axis", "Y")), sfm, what="The section")
    return t, across, sfm, sfm_name, feats


def _load_assumptions(env, bd, extra):
    a = packs.anchor(env.context.get("install"))
    out = [f"Static {bd.get('duration', 'sustained')} load {bd.get('load')} kg at {bd.get('at')}",
           "Rigid pivot about the lowest point of the wall face; screws share the moment by height (T = M·z_max/Σz²)",
           f"Anchor: {a['label']}, mean ultimate from packs.ANCHORS ({a['tension_n']['status']})"]
    return out + extra


@form("anchor_pullout", "hand calculation", "analysis", 2,
      "Wall screws in their anchors carry the moment of a load (rigid pivot model); SF from the anchor pack "
      "(4 drywall, ≈5 wood) on mean ultimate.",
      [P("anchors", "ref", doc="the wall-screw hole feature")] + _LOAD_PARAMS,
      {"anchors": "A.P.holes", "load": "component:rod", "at": "component:rod", "seat": "cradle_seat"},
      "The wall screws ({anchors}) hold {load} kg at {at}, safety factor from the anchor pack")
def _anchor_pullout(env, spec, bd, comps):
    t, a, sfa, anc, wtg, feats, L = _anchor_terms(env, bd, comps)
    return _result(env, spec, FORMS["anchor_pullout"], t.plain, [t], features=anc.features + feats,
                   faces=_face_ids(env, anc.shapes + wtg.shapes),
                   method_assumptions=_load_assumptions(env, bd, [f"SF {sfa:g} ({a['safety']}) on mean ultimate; "
                                                                  "shear and head pull-through not checked"]))


@form("bending", "hand calculation", "analysis", 2,
      "A rectangular section at a distance from the wall bends under the load: σ = 6M/(bh²) × SF ≤ short-term "
      "tensile strength (× across-layer ratio when the stress runs along the build direction).",
      _LOAD_PARAMS + _SECTION,
      {"load": "component:rod", "at": "component:rod", "seat": "cradle_seat", "section_width": "20",
       "section_depth": "6", "section_at": "10"},
      "The {section_width} × {section_depth} section, {section_at} from the wall, carries {load} kg at {at} (mm)")
def _bending(env, spec, bd, comps):
    t, across, sfm, sfm_name, feats = _bend_terms(env, bd, comps)
    return _result(env, spec, FORMS["bending"], t.plain, [t], features=feats,
                   method_assumptions=[f"Rectangular section {bd['section_width']} × {bd['section_depth']} mm at "
                                       f"{bd['section_at']} mm from the wall (the binding states it)",
                                       f"SF {sfm:g} ({sfm_name}) on short-term in-layer strength; creep covered",
                                       "Stress across layers (ratio 0.3–0.8)" if across else "Stress within layers"])


@form("load", "hand calculation", "analysis", 2,
      "Anchor pull-out and (when a section is given) bending together, as R.c1 generalized.",
      [P("anchors", "ref", doc="the wall-screw hole feature")] + _LOAD_PARAMS
      + [P(p.name, p.type, False, p.default, p.doc, p.choices) for p in _SECTION],
      {"anchors": "A.P.holes", "load": "0.2..1", "at": "component:rod", "seat": "cradle_seat"},
      "Holds {load} kg at {at} (wall screws {anchors}; bending when a section is given)")
def _load(env, spec, bd, comps):
    ta, a, sfa, anc, wtg, feats, L = _anchor_terms(env, bd, comps)
    terms, extra = [ta], [f"SF {sfa:g} ({a['safety']}) on mean ultimate"]
    if bd.get("section_width") and bd.get("section_depth") and bd.get("section_at"):
        tb, across, sfm, sfm_name, _f = _bend_terms(env, bd, comps)
        terms.append(tb)
        extra.append(f"SF {sfm:g} ({sfm_name}) on printed strength; stress {'across' if across else 'within'} layers")
    else:
        extra.append("No section given: bending is not checked")
    return _result(env, spec, FORMS["load"], f"Holds {_rng(_load_q(env, bd, comps))} kg", terms,
                   features=anc.features + feats, faces=_face_ids(env, anc.shapes + wtg.shapes),
                   method_assumptions=_load_assumptions(env, bd, extra))


# ---------------------------------------------------------------- tool access

@form("tool_access", "tool access", "rule", 1,
      "A straight screwdriver (cylinder Ø × length) coaxial with each screw of a hole feature clears the part.",
      [P("holes", "ref", doc="hole feature"), P("diameter", "number", False, "30", "mm"),
       P("length", "number", False, "150", "mm")],
      {"holes": "A.P.holes", "diameter": "30", "length": "150"},
      "A Ø{diameter} mm screwdriver, {length} mm long, reaches every screw of {holes}")
def _tool_access(env, spec, bd, comps):
    tg = resolve(env, bd["holes"])
    if not tg.hole_feature:
        raise BindingError(f"'{tg.text}' is not a hole feature")
    r = ToolAccess(tg.hole_feature, number(bd.get("diameter", 30), env.params, "diameter"),
                   number(bd.get("length", 150), env.params, "length")).evaluate(env, spec)
    if not r.ran:
        raise BindingError(r.reason)
    return r


# ---------------------------------------------------------------- evaluation entry point

def evaluate(env: Env, spec: dict, binding: dict, comps: dict) -> CheckResult:
    """Evaluate one intent-file binding.  Unresolvable bindings come back *not run* with the
    reason; nothing here raises."""
    from .checks import _rung
    made_by = str(binding.get("made_by") or "model")
    reviewed = binding.get("status") == "accepted"
    f = binding.get("form")
    base = dict(id=spec["id"], node=spec.get("node", ""), statement=spec.get("statement", ""),
                plain=spec.get("statement", "") or spec["id"], kind=spec.get("kind") or "?",
                rung=_rung(spec.get("kind")), priority=spec.get("priority", ""), source=spec.get("source", ""))
    if f == "descriptive":
        r = CheckResult(state="not run", reason=f"descriptive, not run: {binding.get('reason', '')}", **base)
    else:
        errs = validate_binding(binding, comps)
        fm = FORMS.get(f)
        if errs or fm is None:
            r = CheckResult(state="not run", reason="binding is invalid: " + "; ".join(errs), **base)
        else:
            try:
                r = fm.fn(env, spec, binding, comps)
                r.kind = spec.get("kind") or fm.kind
            except BindingError as e:
                r = CheckResult(state="not run", reason=f"{f}: {e}", **base)
            except Exception as e:   # noqa: BLE001 - a broken binding is reported, not raised
                r = CheckResult(state="not run", reason=f"{f} raised {type(e).__name__}: {e}", **base)
    r.binding = dict(binding)
    r.binding_text = describe(binding, comps)
    r.spec_made_by = made_by
    r.binding_reviewed = reviewed
    return r
