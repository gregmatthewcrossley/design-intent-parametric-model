"""Rung-1 invariants run after every feature, regardless of intent (dsl.md §5).

1. Kernel validity: BRepCheck_Analyzer (geometric checks on), non-null, positive volume.
2. Euler-Poincaré  V - E + F - R = 2(S - H)  with the counting rule validated in
   spike 01 (14 solids) and spike 02 (29 models):
     * de-duplicate sub-shapes by TShape + Location, ignoring orientation (seams count once);
     * exclude degenerated edges (sphere/cone poles AND fillet corners);
     * never de-duplicate by TShape alone (an extrude's END cap shares START's TShape).
3. Per-feature expected ΔH **and** ΔS, declared by each op and computed from its
   interaction with existing geometry (`ops.Expect`).
4. Volume sign: cuts remove material, adds add it, rigid motions keep it.
5. Topological signature: (V,E,F,R,S,H) + two Weisfeiler-Lehman face-adjacency hashes
   (geometry-inclusive; topology-only **without surface or curve type**), plus an
   order-free role-geometry fingerprint.
6. Canonical serialization: BRep text, except after BRepOffset join-mode ops (not
   byte-deterministic, spike 02 §3), where the fingerprint is the canonical form.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopExp import TopExp

from . import kernel as K


# ---------------------------------------------------------------- Euler-Poincaré

@dataclass(frozen=True)
class EulerCounts:
    V: int
    E: int
    F: int
    R: int
    S: int
    H: float          # solved genus; integral and >= 0 iff the check passes
    solids: int
    E_degenerated: int

    @property
    def ok(self) -> bool:
        return float(self.H).is_integer() and self.H >= 0

    def tuple6(self) -> tuple:
        return (self.V, self.E, self.F, self.R, self.S, int(self.H) if self.ok else self.H)

    def __str__(self):
        v, e, f, r, s, h = self.tuple6()
        return f"V={v} E={e} F={f} R={r} S={s} H={h}"


def euler_counts(shape) -> EulerCounts:
    """Counts under the validated rule (module docstring, dsl.md §5.2)."""
    V = len(K.subshapes(shape, TopAbs_VERTEX))
    edges = K.subshapes(shape, TopAbs_EDGE)
    degen = sum(1 for e in edges if K.is_degenerated(e))
    E = len(edges) - degen
    faces = K.subshapes(shape, TopAbs_FACE)
    F = len(faces)
    R = sum(len(K.subshapes(f, TopAbs_WIRE)) - 1 for f in faces)
    S = len(K.subshapes(shape, TopAbs_SHELL))
    H = S - (V - E + F - R) / 2
    return EulerCounts(V, E, F, R, S, H, len(K.subshapes(shape, TopAbs_SOLID)), degen)


def is_valid(shape) -> bool:
    return (not shape.IsNull()) and BRepCheck_Analyzer(shape, True).IsValid()


# ---------------------------------------------------------------- signature

def _q(x: float, sig: int = 6) -> str:
    s = f"{x:.{sig}g}"
    return "0" if s in ("-0", "0") else s


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def adjacency_hash(shape, geometric: bool = True, rounds: int = 4) -> str:
    """Order-independent Weisfeiler-Lehman hash of the face-adjacency graph.

    geometric=True  node = surface type | rounded area | wire count; edge = curve type.
                    Changes with any geometry change ("same program -> same geometry").
    geometric=False node = wire count | edge-use count; edge = 'seam' or 'e'.
                    **No surface or curve type**: equal loft sections flip a plane/B-spline
                    label with no topology change (spike 02 §1.4), so a topology hash must
                    not see it.  Constant across legitimate parameter edits.
    Degenerated edges are skipped; seam edges become labelled self-loops; sha256, sorted
    multisets (no language `hash()`, no map order).
    """
    faces = K.subshapes(shape, TopAbs_FACE)
    fm = K.ShapeMap()
    for f in faces:
        fm.Add(f)
    labels = []
    for f in faces:
        nw = len(K.subshapes(f, TopAbs_WIRE))
        if geometric:
            labels.append(f"{K.surface_type(f)}|{_q(K.area(f))}|w{nw}")
        else:
            ne = sum(1 for e in K.subshapes(f, TopAbs_EDGE) if not K.is_degenerated(e))
            labels.append(f"w{nw}|e{ne}")
    amap = K.ShapeAncestorMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, amap)
    nbrs: list[list] = [[] for _ in faces]
    for i in range(1, amap.Extent() + 1):
        e = amap.FindKey(i)
        if K.is_degenerated(e):
            continue
        anc = sorted({fm.FindIndex(f) - 1 for f in K.occ_list(amap.FindFromIndex(i))})
        ct = K.curve_type(e) if geometric else "e"
        if len(anc) == 1:
            nbrs[anc[0]].append(("seam:" + ct, anc[0]))
        else:
            for a in anc:
                for b in anc:
                    if a != b:
                        nbrs[a].append((ct, b))
    cur = [_sha(lbl)[:16] for lbl in labels]
    for _ in range(rounds):
        cur = [_sha(cur[i] + "|" + ",".join(sorted(f"{el}>{cur[j]}" for el, j in nbrs[i])))[:16]
               for i in range(len(faces))]
    return _sha(",".join(sorted(cur)))


def role_geometry_fingerprint(ledger, nd: int = 6) -> str:
    """Order-free fingerprint: for each tag, the sorted (rounded centroid, area|length) of the
    sub-shapes it resolves to.  Stays meaningful when BRep bytes/sub-shape order are not
    reproducible (BRepOffset join mode, spike 02 §3)."""
    by_tag: dict = {}
    for e in ledger.items:
        by_tag.setdefault(str(e.tag), []).append(
            K.centroid(e.shape).rounded(nd) + (K._r(K.measure(e.shape), nd),))
    parts = [f"{t}:{sorted(set(v))}" for t, v in sorted(by_tag.items())]
    return _sha("|".join(parts))


@dataclass(frozen=True)
class Signature:
    """Topological signature stored with each solution (dsl.md §5.4)."""
    VEFRSH: tuple
    adj_geom: str
    adj_topo: str
    roles_geom: str
    volume: float

    def as_dict(self) -> dict:
        return {"VEFRSH": list(self.VEFRSH), "adj_geom": self.adj_geom, "adj_topo": self.adj_topo,
                "roles_geom": self.roles_geom, "volume": round(self.volume, 6)}

    def short(self) -> str:
        return (f"VEFRSH={self.VEFRSH} adj_geom={self.adj_geom[:12]} adj_topo={self.adj_topo[:12]} "
                f"roles_geom={self.roles_geom[:12]} volume={self.volume:.6g}")


def signature(shape, ledger) -> Signature:
    return Signature(euler_counts(shape).tuple6(), adjacency_hash(shape, True), adjacency_hash(shape, False),
                     role_geometry_fingerprint(ledger), K.volume(shape))


def canonical_bytes(shape, ledger, byte_deterministic: bool) -> tuple[str, bytes]:
    """(mode, bytes).  mode 'brep' = OCCT BRep text; mode 'fingerprint' = JSON of the signature,
    used when any feature in the program is a BRepOffset join-mode op (dsl.md §5.4 exception)."""
    if byte_deterministic:
        return "brep", K.brep_bytes(shape)
    return "fingerprint", json.dumps(signature(shape, ledger).as_dict(), sort_keys=True).encode()


# ---------------------------------------------------------------- per-feature check record

@dataclass
class Check:
    """One invariant evaluation after one feature."""
    name: str
    ok: bool
    expected: object = None
    got: object = None
    note: str = ""

    def __str__(self):
        s = f"{'PASS' if self.ok else 'FAIL'} {self.name}"
        if self.expected is not None or self.got is not None:
            s += f" (expected {self.expected}, got {self.got})"
        if self.note:
            s += f" - {self.note}"
        return s


@dataclass
class FeatureChecks:
    feature: str
    checks: list = field(default_factory=list)
    counts: EulerCounts | None = None
    volume: float = 0.0

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def failures(self) -> list:
        return [c for c in self.checks if not c.ok]


VOLUME_TOL_REL = 1e-9   # relative to the larger volume
VOLUME_TOL_ABS = 1e-6   # mm^3


def run_feature_invariants(feature_id: str, before, after, expect, prev: FeatureChecks | None = None) -> FeatureChecks:
    """Run invariants 1-4 for one feature.  `expect` is an `ops.Expect`.

    `before` is None for the first (creator) feature: counts start from the empty set
    (H=0, S=0, volume 0).  `prev` (the previous feature's checks on `before`) avoids
    recomputing its counts and volume.
    """
    fc = FeatureChecks(feature_id)
    if after is None or after.IsNull():
        fc.checks.append(Check("validity", False, "non-null solid", "null shape",
                               "kernel returned a null shape without raising (silently invalid)"))
        return fc
    valid = BRepCheck_Analyzer(after, True).IsValid()
    fc.checks.append(Check("validity", valid, note="" if valid else "BRepCheck_Analyzer reports an invalid shape"))
    c1 = euler_counts(after)
    fc.counts = c1
    fc.checks.append(Check("euler", c1.ok, "integral H >= 0", f"{c1}"))
    v1 = K.volume(after)
    fc.volume = v1
    fc.checks.append(Check("positive_volume", v1 > VOLUME_TOL_ABS, "> 0", f"{v1:.6g}"))
    if prev is not None and prev.counts is not None and before is not None:
        c0, v0 = prev.counts, prev.volume
    elif before is not None:
        c0, v0 = euler_counts(before), K.volume(before)
    else:
        c0, v0 = None, 0.0
    h0 = int(c0.H) if (c0 is not None and c0.ok) else 0
    s0 = c0.S if c0 is not None else 0
    if c1.ok and (c0 is None or c0.ok):
        dh = int(c1.H) - h0
        fc.checks.append(Check("delta_H", dh == expect.dH, expect.dH, dh, expect.why_dH))
    ds = c1.S - s0
    fc.checks.append(Check("delta_S", ds == expect.dS, expect.dS, ds, expect.why_dS))
    dv = v1 - v0
    tol = max(VOLUME_TOL_ABS, VOLUME_TOL_REL * max(abs(v0), abs(v1)))
    sign = expect.volume_sign
    if sign == "+":
        ok, want = dv > tol, "ΔV > 0 (adds material)"
    elif sign == "-":
        ok, want = dv < -tol, "ΔV < 0 (removes material)"
    elif sign == "0":
        ok, want = abs(dv) <= max(tol, 1e-7 * max(abs(v0), 1.0)), "ΔV = 0 (rigid / no material change)"
    else:
        ok, want = abs(dv) > tol, "ΔV != 0"
    fc.checks.append(Check("volume_sign", ok, want, f"ΔV={dv:.6g}"))
    return fc
