"""Q4 -- build123d's clean() = ShapeUpgrade_UnifySameDomain(shape, UnifyEdges, UnifyFaces, ConcatBSplines)
with AllowInternalEdges(False) (build123d 0.13 runs this after every boolean by default).

Questions: does it provide history?  Is that history correct?  Can structural references survive merging?
Cases:
  noop        block (nothing to merge): are sub-shapes kept identical?
  bracket     spike-01 shelf bracket: do all 18 references still resolve with their declared cardinality?
  mirror      mirror-and-fuse: coplanar halves -> merge events
  revolve     two 180-degree revolves fused: half-cylinders across the seam -> one periodic face
  seq_pattern sequential overlapping holes: a seam-split wall (cardinality 2) is merged back to 1
  sweep       line+arc sweep: the planar side faces along the line and the arc are coplanar -> merged
"""
from __future__ import annotations

import json
import os

import ops      # noqa: I001  (importing common first puts spike 01 on sys.path)
import bracket  # spike 01
from common import HERE, HistoryAdapter, Ledger2, audit_history, checks, describe, topo
from refs import Tag, CardinalityError

from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX


def clean(shape):
    u = ShapeUpgrade_UnifySameDomain(shape, True, True, True)
    u.AllowInternalEdges(False)
    u.Build()
    return u.Shape(), u


def identity_kept(before, after) -> dict:
    """How many sub-shapes of `before` are still IsSame-present in `after` (per kind)."""
    from common import present_map
    P = present_map(after)
    return {k: f"{sum(P.Contains(s) for s in topo.subshapes(before, t))}/{len(topo.subshapes(before, t))}"
            for k, t in (("faces", TopAbs_FACE), ("edges", TopAbs_EDGE), ("vertices", TopAbs_VERTEX))}


def _key(f, role, src):
    return f"{f}.{role}({src})" if src else f"{f}.{role}"


def ledger_report(led: Ledger2, refs_spec) -> dict:
    out = {}
    for f, role, src, card in refs_spec:
        key = _key(f, role, src)
        try:
            led.resolve(f, role, src, card)
            ok = True
        except CardinalityError as ex:
            ok = str(ex)
        try:
            led.resolve(f, role, src, card, policy="error_on_merge")
            merge_ok = True
        except CardinalityError:
            merge_ok = False
        events = sorted({tuple(ev[1] for ev in g) for g in led.genealogy(f, role, src)})
        out[key] = {"n": led.count(f, role, src), "resolves": ok, "error_on_merge_ok": merge_ok,
                    "last_events": sorted({e[-1] if e else "-" for e in events})}
    return out


def case(name, shape, led, refs_spec, extra=None):
    cs, u = clean(shape)
    hist = HistoryAdapter(u.History())
    before_counts = {r: led.count(*r[:3]) for r in refs_spec}
    led.propagate("clean", hist, cs)
    rep = {"case": name, "before": checks(shape)["VEFRSH"], "after": checks(cs)["VEFRSH"],
           "valid_after": topo.is_valid(cs), "euler_after": topo.euler_counts(cs).ok,
           "identity_kept": identity_kept(shape, cs),
           "audit": {k: v for k, v in audit_history(hist, {"in": shape}, cs).items() if not k.endswith("examples")},
           "refs": ledger_report(led, refs_spec),
           "count_before_clean": {_key(*r[:3]): n for r, n in before_counts.items()}}
    if extra:
        rep.update(extra)
    return rep


def run_cases():
    out = []
    # --- noop
    s0, led = ops.block()
    spec = [(t.feature, t.role, t.source, ("exactly", 1)) for t in led.tags()]
    out.append(case("noop (plain block)", s0, led, spec))

    # --- bracket (spike 01), re-run its ledger through a Ledger2 so merges are visible
    b = bracket.build_bracket()
    led = Ledger2()
    led.items, led.deleted = list(b.ledger.items), list(b.ledger.deleted)
    spec = list(bracket.FINAL_REFERENCES)
    out.append(case("spike-01 bracket", b.shape, led, spec))

    # --- mirror and fuse (coplanar halves)
    r = ops.mirror(0.0)
    spec = [("E", "cap", "START", ("exactly", 1)), ("M", "cap", "START", ("exactly", 1)),
            ("E", "side", "o-p", ("exactly", 1)), ("M", "side", "o-p", ("exactly", 1)),
            ("E", "side", "r-s", ("exactly", 1)), ("M", "side", "r-s", ("exactly", 1))]
    rep = case("mirror + fuse", r.shape, r.ledger, spec)
    e_cap = r.ledger.resolve("E", "cap", "START")[0]
    m_cap = r.ledger.resolve("M", "cap", "START")[0]
    rep["E.cap(START) is M.cap(START) after clean"] = bool(e_cap.IsSame(m_cap))
    out.append(rep)

    # --- two half revolves fused: periodic faces merged across the seam
    r1, r2 = ops.revolve(180), ops.revolve(180)
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir
    import math
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.pi)
    tr = BRepBuilderAPI_Transform(r2.shape, t, True)
    led = Ledger2()
    for role in ("side(outer)", "side(inner)", "side(top)"):
        led.add(Tag("R1", role), r1.roles[role])
        led.add(Tag("R2", role), [tr.ModifiedShape(x) for x in r2.roles[role]])
    fu = BRepAlgoAPI_Fuse(r1.shape, tr.Shape())
    led.propagate("fuse", fu, fu.Shape())
    spec = [(f, role, None, ("exactly", 1)) for f in ("R1", "R2") for role in ("side(outer)", "side(inner)", "side(top)")]
    out.append(case("2 x revolve(180) fused (seam merge)", fu.Shape(), led, spec,
                    {"fused_valid": topo.is_valid(fu.Shape())}))

    # --- sequential overlapping holes: seam-split wall merged back
    r = ops.pattern_holes("linear", n=2, pitch=5, combine="sequential")
    spec = [("P", "wall", "instance0", ("exactly", 1)), ("P", "wall", "instance1", ("exactly", 1))]
    out.append(case("overlapping holes, sequential (wall split at seam)", r.shape, r.ledger, spec))

    # --- sweep line+arc: coplanar planar sides along line and arc
    r = ops.sweep()
    led = Ledger2()
    for role, shapes in r.roles.items():
        led.add(Tag("S", role), shapes)
    spec = [("S", role, None, ("exactly", 1)) for role in r.roles if "along" in role or "cap" in role]
    out.append(case("sweep line+arc", r.shape, led, spec))
    return out


def main():
    rows = run_cases()
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "q4.json"), "w") as fh:
        json.dump(rows, fh, indent=1, default=str)
    print("\n## Q4 clean() / UnifySameDomain")
    for r in rows:
        a = r["audit"]
        print(f"\n### {r['case']}: VEFRSH {r['before']} -> {r['after']}, valid={r['valid_after']}, "
              f"Euler={r['euler_after']}, identity kept {r['identity_kept']}")
        print(f"  history audit: false_deleted={a['false_deleted']} consumed={a['consumed']} "
              f"missed_delete={a['missed_delete']} modified_not_in_result={a['modified_not_in_result']}")
        for k, v in r["refs"].items():
            print(f"  {k:36s} n {r['count_before_clean'].get(k, '?')} -> {v['n']}  resolves={v['resolves']}  "
                  f"error_on_merge ok={v['error_on_merge_ok']}  last event={v['last_events']}")
        for k, v in r.items():
            if k.startswith(("E.cap", "fused")):
                print(f"  {k}: {v}")
    return rows


if __name__ == "__main__":
    main()
