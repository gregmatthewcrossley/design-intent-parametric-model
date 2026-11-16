"""Executable intent checks with margins, and the tiered build status (docs/gui.md §8.2
3E.1–3E.3; tolerance-uncertainty.md §2; review-response B1, B2).

**No bare PASS.**  A build's status is reported in tiers (`tiered_status`): the kernel
invariants (validity, Euler, ΔH, ΔS, volume sign, references), then the intent checks of the
intent file, each **run** (with a state: ample, thin or failing) or **not run** (no computable
form yet).  Nothing is green unless it ran and passed.

**Margins.**  Every check that runs reports a nominal value, a worst-case value, the limit
(nominal and worst case) and the margin, from quantities with ranges (`quantity.Quantity`:
rule packs, component data, assumptions) propagated worst case over every corner of the
input box.  State: *failing* if the worst-case margin is negative, *thin* if it is below
`packs.THIN_FRACTION` of the limit (or the check's own absolute band), else *ample*.

Checks are bound to intent-file check ids by the design (`Design.check("R.c1", ...)`): the
statement lives in the intent file, the grounding (which features, which load) in the DSL,
next to the geometry it reads.  v0 implementations:

* `cantilever_load` (R.c1, rung 2 analysis): simplified rigid pivot about the bottom of the
  leg, static point load at the arm tip (R.a1); anchor pull-out T = M·z_max/Σz²; bending of
  the arm plate beyond the gusset; PLA/PETG allowable from pack data (across layers when the
  stress runs along the build direction, R.a2); safety factor from the check statement.
* `tool_access` (R.c4, rung 1 rule): a straight access cylinder (Ø30 mm, ≥ 150 mm) coaxial with
  each screw, swept out from the face; clearance to the part material in front of the face.
* `overhang` (R.c2, rung 1 rule): steepest unsupported overhang in the current print
  orientation (3E.10) against the pack limit (45°); horizontal holes that bridge are excluded.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from . import packs
from .quantity import Quantity, worst_margin

STATES = ("ample", "thin", "failing", "not run")


@dataclass
class CheckTerm:
    """One compared quantity of a check (a check may have several; the governing one decides)."""
    name: str                 # "upper anchor pull-out × SF"
    plain: str
    unit: str
    sense: str                # "<=" (value must stay at or below the limit) or ">="
    nominal: float
    worst: float
    limit: float
    limit_worst: float
    margin: float
    margin_worst: float
    margin_rel: float | None  # margin_worst / |limit_worst| (None when the limit is 0)
    state: str
    inputs: list = field(default_factory=list)       # Quantity dicts
    worst_inputs: dict = field(default_factory=dict)
    method: str = ""
    formula: str = ""


@dataclass
class CheckResult:
    id: str
    node: str
    statement: str            # from the intent file
    plain: str                # plain language ("Holds 20 kg at the arm tip with a safety factor of 2")
    kind: str                 # architecture §4.1 kind
    rung: int
    state: str                # ample | thin | failing | not run
    reason: str = ""          # why not run / what governs
    governing: str = ""
    terms: list = field(default_factory=list)        # CheckTerm
    assumptions: list = field(default_factory=list)  # [{id, statement, made_by, reviewed}]
    method_assumptions: list = field(default_factory=list)   # what the hand-calc model takes for granted
    features: list = field(default_factory=list)
    faces: list = field(default_factory=list)
    made_by: str = "engine"
    priority: str = ""
    source: str = ""
    spec_made_by: str = "author"
    reviewed: bool = False    # the check's statement (its node) is reviewed
    confirms: list = field(default_factory=list)     # interpretation slots this check can confirm (B3)

    @property
    def ran(self) -> bool:
        return self.state != "not run"

    def headline(self) -> CheckTerm | None:
        for t in self.terms:
            if t.name == self.governing:
                return t
        return self.terms[0] if self.terms else None

    def as_dict(self) -> dict:
        d = asdict(self)
        h = self.headline()
        d["headline"] = asdict(h) if h else None
        return d


def classify(margin_worst: float, limit_worst: float, thin_abs: float = 0.0) -> tuple[str, float | None]:
    rel = margin_worst / abs(limit_worst) if abs(limit_worst) > 1e-12 else None
    if margin_worst < 0:
        return "failing", rel
    band = max(thin_abs, packs.THIN_FRACTION * abs(limit_worst))
    return ("thin" if margin_worst < band else "ample"), rel


def term(name: str, plain: str, unit: str, sense: str, value_fn, limit_fn, inputs: dict, thin_abs: float = 0.0,
         formula: str = "") -> CheckTerm:
    r = worst_margin(value_fn, limit_fn, sense, inputs)
    state, rel = classify(r["margin_worst"], r["limit_worst"], thin_abs)
    return CheckTerm(name, plain, unit, sense, r["nominal"], r["worst"], r["limit"], r["limit_worst"], r["margin"],
                     r["margin_worst"], rel, state, [q.as_dict() | {"name": k} for k, q in inputs.items()],
                     r["worst_inputs"], r["method"], formula)


def _rank(t: CheckTerm) -> tuple:
    order = {"failing": 0, "thin": 1, "ample": 2}
    return (order[t.state], t.margin_rel if t.margin_rel is not None else t.margin_worst)


# ---------------------------------------------------------------- what a check sees

@dataclass
class Env:
    build: object
    design: object
    context: dict             # effective context values (key -> text)
    orientation: dict | None  # {"up": [x, y, z], ...} or None
    assumptions: dict         # intent-file assumption id -> plain dict
    params: dict

    def __post_init__(self):
        self._faces = None

    # parameter expressions are evaluated like feature arguments
    def ev(self, x):
        from .expr import ev
        return ev(x, self)

    @property
    def faces(self) -> list:
        if self._faces is None:
            self._faces = self.build.faces()
        return self._faces

    def face_ids(self, refs) -> list:
        from . import kernel as K
        smap = K.ShapeMap()
        for f in self.faces:
            smap.Add(f)
        out = []
        for r in refs:
            try:
                shapes = self.build.resolve(r)
            except Exception:   # noqa: BLE001 - a missing role simply involves no face
                continue
            for s in shapes:
                i = smap.FindIndex(s) - 1
                if i >= 0 and i not in out:
                    out.append(i)
        return sorted(out)

    def feature_faces(self, fid: str) -> list:
        return [i for i, f in enumerate(self.faces) if any(e.tag.feature == fid for e in self.build.ledger.who(f))]

    def fdm(self) -> dict | None:
        return packs.process(self.context.get("process"))

    def tol(self, which: str) -> Quantity:
        p = self.fdm()
        if p is None:
            return Quantity.exact(0.0, "mm", "no process tolerance")
        e = p[which]
        return Quantity(0.0, -e["value"], e["value"], "mm", f"{p['pack']}.{which}", "pack default", which,
                        bool(e.get("placeholder")))

    def assumption(self, aid: str) -> dict:
        a = self.assumptions.get(aid) or {}
        return {"id": aid, "statement": a.get("statement", ""), "made_by": a.get("made_by", "model"),
                "status": a.get("status", "proposed"), "reviewed": a.get("status") == "accepted",
                "in_file": bool(a)}


class IntentCheck:
    """Base: `evaluate(env) -> CheckResult` (state, terms, faces).  `rung`/`kind` follow
    architecture §4.1."""
    kind = "rule"
    rung = 1
    plain = ""

    def evaluate(self, env: Env, spec: dict) -> CheckResult:   # pragma: no cover - abstract
        raise NotImplementedError

    def _result(self, spec: dict, env: Env, plain: str, terms: list, **kw) -> CheckResult:
        terms = sorted(terms, key=_rank)
        gov = terms[0] if terms else None
        return CheckResult(spec["id"], spec.get("node", ""), spec.get("statement", ""), plain,
                           spec.get("kind") or self.kind, self.rung, gov.state if gov else "not run",
                           governing=gov.name if gov else "", terms=terms, priority=spec.get("priority", ""),
                           source=spec.get("source", ""), **kw)


# ---------------------------------------------------------------- R.c1: load (rung 2)

@dataclass
class CantileverLoad(IntentCheck):
    """A bracket carrying a point load at its arm tip, held to a wall by screws in anchors.

    Model (stated in every result, `method_assumptions`): the bracket pivots rigidly about the
    bottom of its leg; the moment M = W·L is carried by the screws in proportion to their
    height above the pivot, so the top screw pulls out with T = M·z_max / Σz²; the arm plate
    beyond the gusset carries M_s = W·(L − y_s) in bending (σ = 6·M_s / (b·h²)).  Shear, the
    leg's bearing on the wall, the gusset and the leg sections, anchor stiffness and creep are
    not modelled."""
    load_kg: Quantity
    safety_factor: float
    anchors: str                      # hole feature whose centres are the wall screws
    section_width: object             # arm plate width b (expression)
    section_depth: object             # arm plate thickness h (expression)
    section_at: object                # distance of the checked section from the wall (expression)
    stress_axis: tuple = (0.0, 1.0, 0.0)   # direction of the bending stress (along the arm)
    involves: tuple = ()
    load_assumption: str = "R.a1"
    layer_assumption: str = "R.a2"
    kind = "analysis"
    rung = 2

    def evaluate(self, env: Env, spec: dict) -> CheckResult:
        from . import kernel as K
        b = env.build
        rec = b.record(self.anchors)
        centres = list((rec.detail or {}).get("centres") or [])
        if not centres:
            return CheckResult(spec["id"], spec.get("node", ""), spec.get("statement", ""), "", self.kind, self.rung,
                               "not run", reason=f"{self.anchors} has no hole centres in this build")
        lo, hi = K.bbox(b.shape)
        pos = env.tol("position_tolerance")
        dim = env.tol("dimension_tolerance")
        g = packs.G_STANDARD
        sf = self.safety_factor
        W = self.load_kg
        inputs = {"m": W}
        zs = []
        for k, c in enumerate(centres):
            z = c.z - lo.z
            q = Quantity(z, z + pos.lo, z + pos.hi, "mm", pos.source, "pack default", f"height of screw {k} above the pivot",
                         pos.placeholder)
            inputs[f"z{k}"] = q
            zs.append(f"z{k}")
        L = hi.y - lo.y
        inputs["L"] = Quantity(L, L + pos.lo, L + pos.hi, "mm", pos.source, "pack default", "lever arm: wall to arm tip",
                               pos.placeholder)
        anchor = packs.ANCHORS.get(env.context.get("install", packs.DEFAULT_INSTALL)) or packs.ANCHORS[packs.DEFAULT_INSTALL]
        cap = Quantity.from_pack(anchor["pullout_n"], "anchors.pullout_n", f"{anchor['label']} pull-out capacity")

        def tension(m, L, **z):
            zz = [z[k] for k in zs]
            return m * g * L * max(zz) / sum(v * v for v in zz)

        anc_inputs = {**inputs, "cap": cap}
        t_anchor = term("upper anchor pull-out × SF", f"Top wall screw pulls out of its anchor (×{sf:g} safety)", "N",
                        "<=", lambda cap, **x: sf * tension(**x), lambda cap, **x: cap, anc_inputs,
                        formula=f"{sf:g} · m·g·L·z_max / Σz² ≤ anchor pull-out")
        # arm bending beyond the gusset
        bw, bh, ys = float(env.ev(self.section_width)), float(env.ev(self.section_depth)), float(env.ev(self.section_at))
        mat = packs.material(env.context.get("material")) or packs.MATERIALS["PLA"]
        fdm = env.fdm()
        across = False
        if env.orientation is not None:
            up = env.orientation["up"]
            across = abs(sum(a * u for a, u in zip(self.stress_axis, up))) > 0.7
        sec = {"m": W, "L": inputs["L"],
               "b": Quantity(bw, bw + dim.lo, bw + dim.hi, "mm", dim.source, "pack default", "arm plate width",
                             dim.placeholder),
               "h": Quantity(bh, bh + dim.lo, bh + dim.hi, "mm", dim.source, "pack default", "arm plate thickness",
                             dim.placeholder),
               "ys": Quantity(ys, ys + pos.lo, ys + pos.hi, "mm", pos.source, "pack default",
                              "checked section: end of the gusset", pos.placeholder),
               "s": Quantity.from_pack(mat["tensile_mpa"], f"materials.{mat['label']}.tensile_mpa",
                                       f"{mat['label']} tensile strength")}
        if across and fdm is not None:
            sec["r"] = Quantity.from_pack(fdm["across_layer_strength_ratio"], f"{fdm['pack']}.across_layer_strength_ratio",
                                          "strength across layers / in-layer")

        def sigma(m, L, b, h, ys, **_):
            return 6.0 * m * g * max(L - ys, 0.0) / (b * h * h)

        t_bend = term("arm bending stress × SF",
                      f"Arm plate beyond the gusset bends (×{sf:g} safety{', stress across layers' if across else ''})",
                      "MPa", "<=", lambda **x: sf * sigma(**x),
                      lambda s, r=1.0, **_: s * r, sec,
                      formula=f"{sf:g} · 6·m·g·(L − y_s) / (b·h²) ≤ tensile strength"
                              + (" × across-layer ratio" if across else ""))
        asm = [env.assumption(self.load_assumption)]
        if across:
            asm.append(env.assumption(self.layer_assumption))
        if env.orientation is not None:
            asm.append({"id": "print_orientation", "statement": env.orientation.get("label", ""),
                        "made_by": env.orientation.get("made_by", "model"),
                        "reviewed": bool(env.orientation.get("reviewed")), "in_file": False})
        faces = env.face_ids(self.involves) if self.involves else []
        faces = sorted(set(faces) | set(env.feature_faces(self.anchors)))
        kg = W.nominal
        return self._result(spec, env, f"Holds {kg:g} kg at the arm tip with a safety factor of {sf:g}",
                            [t_anchor, t_bend], assumptions=asm, faces=faces,
                            features=[self.anchors] + sorted({e.tag.feature for i in faces
                                                              for e in b.ledger.who(env.faces[i])} - {self.anchors}),
                            method_assumptions=[
                                f"Static point load of {kg:g} kg (range {W.lo:g}–{W.hi:g} kg) at the arm tip "
                                f"({self.load_assumption})",
                                "The bracket pivots rigidly about the bottom of its leg; the screws carry the "
                                "moment in proportion to their height (T = M·z_max/Σz²)",
                                "The arm plate beyond the gusset is the critical section; gusset, leg, shear and "
                                "the leg bearing on the wall are not checked",
                                "Anchor capacity and material strength are placeholder pack data (packs.py)",
                                ("Bending stress runs along the build direction, so the across-layer strength "
                                 f"applies ({self.layer_assumption})") if across else
                                "Bending stress runs within the layers (in-layer strength)"])


def cantilever_load(load_kg: float, load_range: tuple, safety_factor: float, anchors, section_width, section_depth,
                    section_at, involves=(), stress_axis=(0.0, 1.0, 0.0), load_assumption: str = "R.a1") -> CantileverLoad:
    fid = anchors if isinstance(anchors, str) else anchors.id
    q = Quantity(float(load_kg), float(load_range[0]), float(load_range[1]), "kg", load_assumption, "model",
                 "shelf load")
    return CantileverLoad(q, float(safety_factor), fid, section_width, section_depth, section_at,
                          tuple(stress_axis), tuple(involves), load_assumption)


# ---------------------------------------------------------------- R.c4: tool access (rung 1)

@dataclass
class ToolAccess(IntentCheck):
    """A straight Ø`diameter` cylinder, `length` long, coaxial with each screw of `holes`,
    swept out from the face the hole is drilled in, must clear the part.  Clearance is the
    distance from the cylinder to the part's material in front of that face (positive: clear,
    0: touching); a negative clearance is the depth by which the cylinder must shrink to fit
    (found by bisection on the radius)."""
    holes: str
    diameter: float = 30.0
    length: float = 150.0
    involves: tuple = ()
    assumption: str = "R.a3"
    thin_abs: float = 2.0        # mm: a hand on a driver needs a little slack (placeholder)
    kind = "rule"
    rung = 1

    def evaluate(self, env: Env, spec: dict) -> CheckResult:
        b = env.build
        rec = b.record(self.holes)
        det = rec.detail or {}
        centres, normal = list(det.get("centres") or []), det.get("normal")
        if not centres or normal is None:
            return CheckResult(spec["id"], spec.get("node", ""), spec.get("statement", ""), "", self.kind, self.rung,
                               "not run", reason=f"{self.holes} has no hole axes in this build")
        pos = env.tol("position_tolerance")
        terms, faces = [], set(env.feature_faces(self.holes))
        for k, c in enumerate(centres):
            clr, near = access_clearance(b.shape, c, normal, self.diameter / 2, self.length, env.faces)
            faces |= set(near)
            inputs = {"c": Quantity(clr, clr + pos.lo, clr + pos.hi, "mm", pos.source, "pack default",
                                    f"clearance of screw {k}'s access cylinder", pos.placeholder)}
            terms.append(term(f"screw {k} driver clearance", f"A Ø{self.diameter:g} mm driver reaches screw {k}",
                              "mm", ">=", lambda c: c, lambda c: 0.0, inputs, self.thin_abs,
                              formula=f"distance(Ø{self.diameter:g}×{self.length:g} mm cylinder, part) ≥ 0"))
        return self._result(spec, env, f"A Ø{self.diameter:g} mm screwdriver, {self.length:g} mm long, reaches every wall "
                                       "screw", terms, assumptions=[env.assumption(self.assumption)], faces=sorted(faces),
                            features=[self.holes], method_assumptions=[
                                f"Straight access: a Ø{self.diameter:g} mm cylinder, {self.length:g} mm long, coaxial "
                                "with each screw, starting at the face (architecture §8.1 R.c4)",
                                "Only material in front of the face counts; worst case adds the process's positional "
                                "tolerance (placeholder)"])


def access_clearance(shape, centre, normal, radius: float, length: float, faces: list) -> tuple[float, list]:
    """(signed clearance in mm, ids of the faces nearest the cylinder)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from . import kernel as K
    n = K.Vec3(*normal) if not isinstance(normal, K.Vec3) else normal
    n = n.unit()
    c = centre if isinstance(centre, K.Vec3) else K.Vec3(*centre)
    lo, hi = K.bbox(shape)
    S = (hi - lo).length() + length + 10.0
    eps = 1e-3
    # material in front of the face plane: the part ∩ a big box on the +n side
    ref = K.Vec3(1, 0, 0) if abs(n.x) < 0.9 else K.Vec3(0, 1, 0)
    u = (ref - n * ref.dot(n)).unit()
    v = n.cross(u).unit()
    o = c + n * eps - u * S - v * S
    box = BRepPrimAPI_MakeBox(gp_Ax2(gp_Pnt(o.x, o.y, o.z), gp_Dir(n.x, n.y, n.z), gp_Dir(u.x, u.y, u.z)),
                              2 * S, 2 * S, S).Shape()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    # a copy: a boolean may touch its arguments' tolerances, and the build's solid must stay
    # byte-identical (its BRep text is the canonical form, dsl.md §5.4)
    front = BRepAlgoAPI_Common(BRepBuilderAPI_Copy(shape, True, False).Shape(), box).Shape()
    if K.volume(front) <= 1e-9:
        return 1e3, []

    def cyl(r):
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(c.x, c.y, c.z), gp_Dir(n.x, n.y, n.z)), r, length).Shape()

    def dist(r):
        d = BRepExtrema_DistShapeShape(cyl(r), front)
        d.Perform()
        return d

    d = dist(radius)
    clr = d.Value()
    if clr <= 1e-7:
        a, bnd = 1e-3, radius
        if dist(a).Value() <= 1e-7:
            clr = -radius
        else:
            for _ in range(30):
                mid = 0.5 * (a + bnd)
                if dist(mid).Value() > 1e-7:
                    a = mid
                else:
                    bnd = mid
            clr = a - radius
    # nearest faces: the original faces within a hair of the closest point(s)
    near = []
    if d.NbSolution():
        p = d.PointOnShape2(1)
        vx = BRepBuilderAPI_MakeVertex(p).Vertex()
        for i, f in enumerate(faces):
            dd = BRepExtrema_DistShapeShape(vx, f)
            dd.Perform()
            if dd.Value() < 1e-4:
                near.append(i)
    return float(clr), near


# ---------------------------------------------------------------- R.c2: overhang (rung 1)

@dataclass
class Overhang(IntentCheck):
    """The steepest unsupported overhang, in degrees from vertical, in the print orientation in
    use (the inferred or accepted one, 3E.10), against the process limit.  Facets on the bed
    and horizontal holes that bridge are excluded (packs.FDM)."""
    kind = "rule"
    rung = 1

    def evaluate(self, env: Env, spec: dict) -> CheckResult:
        from .resolution import _bridgeable, facet_table
        p = env.fdm()
        if p is None or env.orientation is None:
            return CheckResult(spec["id"], spec.get("node", ""), spec.get("statement", ""), "", self.kind, self.rung,
                               "not run", reason="no print orientation for this process")
        import numpy as np
        up = np.asarray(env.orientation["up"], dtype=float)
        area, nv, cen, face, P = facet_table(env.build.shape)
        h = cen @ up - float((P @ up).min())
        d = -(nv @ up)
        bed = (d > 0.999) & (h < 1e-3)
        bridge = _bridgeable(env.build, list(up), p["bridge_max_mm"]["value"])
        keep = np.array([f not in bridge for f in face]) & ~bed & (d > 1e-6)
        ang = np.degrees(np.arcsin(np.clip(d, 0.0, 1.0)))
        worst = float(ang[keep].max()) if keep.any() else 0.0
        lim = p["overhang_max_deg"]["value"]
        down = sorted({int(f) for f in face[(d > 0.01) & ~bed]})
        t = term("steepest unsupported overhang", f"No overhang steeper than {lim:g}° from vertical", "deg", "<=",
                 lambda a: a, lambda a: lim, {"a": Quantity.exact(round(worst, 3), "deg", "tessellation")},
                 formula=f"max overhang angle from vertical ≤ {lim:g}°")
        o = env.orientation
        return self._result(spec, env, f"Prints without supports ({o.get('label', 'current orientation')})", [t],
                            assumptions=[{"id": "print_orientation", "statement": o.get("label", ""),
                                          "made_by": o.get("made_by", "model"), "reviewed": bool(o.get("reviewed")),
                                          "in_file": False}],
                            faces=down, features=[], method_assumptions=[
                                "Measured on the display tessellation (curved faces within its angular deflection)",
                                f"Horizontal holes up to Ø{p['bridge_max_mm']['value']:g} mm bridge (placeholder)"])


def overhang() -> Overhang:
    return Overhang()


# ---------------------------------------------------------------- evaluating every intent check

KERNEL_PLAIN = {
    "validity": "The geometry is a valid solid", "euler": "Its topology adds up (Euler–Poincaré parity)",
    "delta_H": "Each feature makes the expected number of holes", "delta_S": "No feature splits the part",
    "volume_sign": "Each feature adds or removes material as it should", "refs": "Every reference finds its target",
}


def intent_specs(design, intent_plain: dict | None) -> list:
    """Every intent check: from the intent file (with its node), plus bound checks the file lacks."""
    out, seen = [], set()

    def walk(lst):
        for n in lst or []:
            for c in n.get("checks") or []:
                out.append({**c, "node": n["id"]})
                seen.add(c["id"])
            walk(n.get("children"))

    walk((intent_plain or {}).get("intents"))
    for cid in design.checks if hasattr(design, "checks") else {}:
        if cid not in seen:
            out.append({"id": cid, "node": cid.rsplit(".c", 1)[0], "statement": "", "kind": design.checks[cid].kind})
    return out


def evaluate_checks(design, build, intent_plain: dict | None, context: dict, orientation: dict | None,
                    reviewed_nodes: set | None = None) -> list:
    """CheckResult per intent check (run or not run).  Never raises for one bad check: its
    error becomes a not-run reason."""
    asm = {}

    def walk(lst):
        for n in lst or []:
            for a in n.get("assumptions") or []:
                asm[a["id"]] = a
            walk(n.get("children"))

    walk((intent_plain or {}).get("intents"))
    env = Env(build, design, context, orientation, asm, build.params)
    bound = getattr(design, "checks", {}) or {}
    out = []
    for spec in intent_specs(design, intent_plain):
        impl = bound.get(spec["id"])
        reviewed = spec["node"] in (reviewed_nodes or set())
        if impl is None or build.shape is None or not build.ok:
            reason = ("the build failed: intent checks run only on a valid solid" if impl is not None
                      else _not_run_reason(spec))
            r = CheckResult(spec["id"], spec["node"], spec.get("statement", ""), _plain_fallback(spec),
                            spec.get("kind") or "?", _rung(spec.get("kind")), "not run", reason=reason,
                            priority=spec.get("priority", ""), source=spec.get("source", ""))
        else:
            try:
                r = impl.evaluate(env, spec)
            except Exception as e:   # noqa: BLE001 - a broken check is reported, not raised
                r = CheckResult(spec["id"], spec["node"], spec.get("statement", ""), _plain_fallback(spec),
                                spec.get("kind") or impl.kind, impl.rung, "not run",
                                reason=f"the check raised {type(e).__name__}: {e}")
        r.reviewed = reviewed
        out.append(r)
    return out


def _rung(kind) -> int:
    return {"relation": 1, "rule": 1, "analysis": 2, "learned score": 3, "live judgment": 4}.get(kind or "", 0)


def _plain_fallback(spec: dict) -> str:
    return spec.get("statement", "") or spec["id"]


def _not_run_reason(spec: dict) -> str:
    k = spec.get("kind")
    if k == "learned score":
        return "learned score (rung 3): no pinned scorer yet"
    if k == "live judgment":
        return "live judgment (rung 4): needs a person"
    return "descriptive: no computable form bound to this check yet (NOTES TODO 4)"


def tiered_status(build, results: list) -> dict:
    """The honest status (B1, gui.md §8.3 item 1): kernel tier, intent tier, margins.  There is
    no single PASS flag; `headline` is the header text."""
    kfail = len(build.errors) + sum(1 for r in build.records if not r.ok and r.error is None)
    kernel = {"state": "pass" if build.ok else "fail", "failures": len(build.errors),
              "features": len(build.records)}
    run = [r for r in results if r.ran]
    by = {s: [r.id for r in run if r.state == s] for s in ("failing", "thin", "ample")}
    intent = {"total": len(results), "run": len(run), "not_run": len(results) - len(run),
              "failing": len(by["failing"]), "thin": len(by["thin"]), "ample": len(by["ample"]),
              "failing_ids": by["failing"], "thin_ids": by["thin"], "ample_ids": by["ample"],
              "not_run_ids": [r.id for r in results if not r.ran]}
    parts = [f"Kernel {'✓' if build.ok else '✗ ' + str(kernel['failures'])}"]
    if results:
        parts.append(f"Intent checks {len(run)} of {len(results)} run")
    else:
        parts.append("Intent checks: none stated")
    if intent["failing"]:
        parts.append(f"{intent['failing']} failing")
    if intent["thin"]:
        parts.append(f"{intent['thin']} thin margin{'s' if intent['thin'] != 1 else ''}")
    _ = kfail
    return {"kernel": kernel, "intent": intent, "headline": " · ".join(parts),
            "text": (f"kernel invariants {'pass' if build.ok else 'FAIL'}"
                     + (f" ({kernel['failures']} error(s))" if not build.ok else "")
                     + f" · intent checks: {len(run)} of {len(results)} run, {intent['failing']} failing, "
                       f"{intent['thin']} thin, {intent['ample']} ample, {intent['not_run']} not run")}


def format_checks(results: list) -> list:
    """Report lines (CLI) for the intent checks."""
    L = []
    for r in results:
        if not r.ran:
            L.append(f"  [not run] {r.id:<7} {r.plain or r.statement}  ({r.reason})")
            continue
        L.append(f"  [{r.state.upper():<7}] {r.id:<7} {r.plain}")
        for t in r.terms:
            gov = " <- governs" if t.name == r.governing and len(r.terms) > 1 else ""
            L.append(f"      {t.name}: nominal {_n(t.nominal)} {t.unit}, worst case {_n(t.worst)} {t.unit}; limit "
                     f"{t.sense} {_n(t.limit)} (worst {_n(t.limit_worst)}) {t.unit}; margin {_n(t.margin)} nominal, "
                     f"{_n(t.margin_worst)} worst case [{t.state}]{gov}")
        for a in r.method_assumptions:
            L.append(f"      assumes: {a}")
    return L


def _n(x: float) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return str(x)
    a = abs(x)
    if a >= 100:
        return f"{x:,.0f}"
    if a >= 1:
        return f"{x:.2f}"
    return f"{x:.3g}"


def tool_access(holes, diameter: float = 30.0, length: float = 150.0, involves=(), assumption: str = "R.a3") -> ToolAccess:
    return ToolAccess(holes if isinstance(holes, str) else holes.id, float(diameter), float(length), tuple(involves),
                      assumption)
