"""Stability harness (dsl.md §5.7; architecture §6 'edit stability', §8.6 edit tests).

Perturb each design parameter across its declared range, rebuild, and assert that
  * the build succeeds and every invariant passes after every feature;
  * every reference (named exports, every feature's input references, and every
    creator tag in the ledger) keeps its **cardinality** and **genealogy**;
  * the **topology-only** adjacency hash is unchanged, unless the caller declares that
    this parameter point may legitimately change topology.
Ported from spike 01 §2.3 (20/20 points stable on the bracket).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .errors import DipmError
from .program import Build, Design, Resolution


@dataclass
class Snapshot:
    params: dict
    ok: bool
    errors: list
    VEFRSH: tuple | None
    adj_topo: str | None
    refs: dict = field(default_factory=dict)   # key -> (count, genealogies)


def snapshot(build: Build) -> Snapshot:
    refs: dict = {}
    for name, res in build.exports.items():
        if isinstance(res, Resolution):
            refs[f"export:{name}={res.ref}"] = (res.count, res.genealogies)
        else:
            refs[f"export:{name}"] = ("ERROR", str(getattr(res, "message", res)))
    for r in build.records:
        for i, res in enumerate(r.inputs):
            refs[f"input:{r.id}#{i}:{res.ref}"] = (res.count, res.genealogies)
    by_tag: dict = {}
    for e in build.ledger.items:
        by_tag.setdefault(str(e.tag), []).append(e)
    for t in build.ledger.tags():
        es = by_tag.get(str(t), [])
        gens = tuple(sorted({" -> ".join(f"{f}:{ev}" for f, ev in e.genealogy) for e in es}))
        uniq = len(build.ledger.unique(es))
        refs[f"tag:{t}"] = (uniq, gens)
    sig = build.signature
    return Snapshot(dict(build.params), build.ok, [str(e) for e in build.errors],
                    sig.VEFRSH if sig else None, sig.adj_topo if sig else None, refs)


def compare(base: Snapshot, other: Snapshot, topology_may_change: bool = False) -> list[str]:
    """Human-readable list of differences that violate stability (empty = stable)."""
    problems = []
    if not other.ok:
        problems += [f"build failed: {e.splitlines()[0]} | {' '.join(e.split())[:300]}" for e in other.errors] \
            or ["build reported failures"]
        return problems
    if not topology_may_change:
        if other.adj_topo != base.adj_topo:
            problems.append(f"topology-only hash changed ({base.adj_topo[:12]} -> {other.adj_topo[:12]})")
        if other.VEFRSH != base.VEFRSH:
            problems.append(f"(V,E,F,R,S,H) changed {base.VEFRSH} -> {other.VEFRSH}")
        for k in sorted(set(base.refs) | set(other.refs)):
            a, b = base.refs.get(k), other.refs.get(k)
            if a is None or b is None:
                problems.append(f"{k}: present only in {'baseline' if b is None else 'variant'}")
            elif a[0] != b[0]:
                problems.append(f"{k}: cardinality {a[0]} -> {b[0]}")
            elif a[1] != b[1]:
                problems.append(f"{k}: genealogy {list(a[1])} -> {list(b[1])}")
    return problems


@dataclass
class PointResult:
    params: dict
    changed: dict
    problems: list
    topology_may_change: bool = False

    @property
    def ok(self) -> bool:
        return not self.problems

    def __str__(self):
        ch = ", ".join(f"{k}={v}" for k, v in self.changed.items()) or "(defaults)"
        if self.ok:
            return f"  STABLE  {ch}"
        return f"  UNSTABLE {ch}\n" + "\n".join(f"      - {p}" for p in self.problems)


@dataclass
class StabilityReport:
    design: str
    baseline: Snapshot
    points: list

    @property
    def ok(self) -> bool:
        return self.baseline.ok and all(p.ok for p in self.points)

    def __str__(self):
        n_ok = sum(p.ok for p in self.points)
        head = (f"Stability harness: {self.design}: {n_ok}/{len(self.points)} points stable "
                f"(baseline VEFRSH={self.baseline.VEFRSH}, adj_topo={(self.baseline.adj_topo or '')[:12]})")
        return "\n".join([head] + [str(p) for p in self.points])


def default_points(design: Design) -> list[dict]:
    """One-at-a-time sweep over each parameter's sweep values, plus the all-low and all-high
    corners of the numeric ranges.  De-duplicated, deterministic order."""
    base = design.defaults()
    pts = []
    for name, p in design.params.items():
        for v in p.sweep_values():
            pts.append({**base, name: v})
    ranged = {n: p for n, p in design.params.items() if p.range is not None and p.samples is None}
    if len(ranged) > 1:
        pts.append({**base, **{n: p.range[0] for n, p in ranged.items()}})
        pts.append({**base, **{n: p.range[1] for n, p in ranged.items()}})
    out, seen = [], set()
    for d in pts:
        key = tuple(sorted(d.items()))
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def grid_points(design: Design, values: dict) -> list[dict]:
    """Full factorial over `values` ({param: [v, ...]}), other params at defaults."""
    base = design.defaults()
    names = list(values)
    return [{**base, **dict(zip(names, combo))} for combo in itertools.product(*(values[n] for n in names))]


def run(design: Design, points: list[dict] | None = None, allow_topology_change=None) -> StabilityReport:
    """Build the baseline (defaults) and every point; compare each to the baseline.

    allow_topology_change: optional predicate params -> bool for points where the author
    *declares* a legitimate structural change (then only build success/invariants are checked).
    """
    base_params = design.defaults()
    base = snapshot(design.build(on_fail="record"))
    results = []
    for params in (points if points is not None else default_points(design)):
        changed = {k: v for k, v in params.items() if base_params.get(k) != v}
        may = bool(allow_topology_change and allow_topology_change(params))
        try:
            snap = snapshot(design.build(params, on_fail="record"))
            problems = compare(base, snap, may)
        except DipmError as e:   # parameter errors etc.
            problems = [f"build raised: {e.message}"]
        results.append(PointResult(params, changed, problems, may))
    return StabilityReport(design.name, base, results)


def edit_test(design: Design, before: dict, after: dict, topology_may_change: bool = False):
    """One §8.6-style edit: build `before` and `after`, return (build_before, build_after, problems)."""
    b0 = design.build(before, on_fail="record")
    b1 = design.build(after, on_fail="record")
    return b0, b1, compare(snapshot(b0), snapshot(b1), topology_may_change)
