"""Q1 -- roles available per operation, history correctness, invariants (Euler, validity, dH, dS).

For every default model in ops.DEFAULTS:
  * role table: each role's cardinality vs the declared one, and its geometric descriptors;
  * base references (pre-existing body, spike-01 ledger) carried through the op vs declared;
  * coverage: result faces not reachable from any role or base reference ("unnamed");
  * history audit: Generated/Modified/IsDeleted checked against the result shape (common.audit_history);
  * invariants: Euler-Poincare with the spike-01 counting rule, BRepCheck validity, dH and dS.
"""
from __future__ import annotations

import json
import os

import ops
from common import HERE, audit_history, checks, coverage, describe, topo


def card_ok(n, expected):
    return n >= 1 if expected is None else n == expected


def analyse(name, run) -> dict:
    after = checks(run.shape)
    if run.before is not None:
        b = checks(run.before)
        dH, dS = after["VEFRSH"][5] - b["VEFRSH"][5], after["VEFRSH"][4] - b["VEFRSH"][4]
    else:
        b, dH, dS = None, after["VEFRSH"][5], after["VEFRSH"][4]
    roles = {}
    for r, shapes in run.roles.items():
        roles[r] = {"n": len(shapes), "expected": run.expected_card.get(r),
                    "ok": card_ok(len(shapes), run.expected_card.get(r)),
                    "desc": sorted({describe(s, run.shape) for s in shapes})}
    base = {}
    if run.ledger is not None:
        for k, exp in run.base_expected.items():
            n = run.ledger.count(*k)
            gen = sorted({tuple(ev[1] for ev in g) for g in run.ledger.genealogy(*k)})
            base[f"{k[0]}.{k[1]}({k[2]})"] = {"n": n, "expected": exp, "ok": n == exp, "events": gen}
    audit = audit_history(run.algo, run.audit_inputs, run.shape) if run.audit_inputs and run.algo is not None else None
    cov = coverage(run.shape, run.roles, run.ledger)
    return {
        "model": name, "op": run.op, "variant": run.variant, "params": run.params,
        "before": b, "after": after, "dH": dH, "dS": dS,
        "expected_dH": run.expected_dH, "expected_dS": run.expected_dS,
        "dH_ok": dH == run.expected_dH, "dS_ok": dS == run.expected_dS,
        "roles": roles, "roles_ok": all(r["ok"] for r in roles.values()),
        "base_refs": base, "base_ok": all(v["ok"] for v in base.values()),
        "coverage": cov, "audit": audit, "notes": run.notes,
        "ledger_isdeleted_disagreements": len(run.ledger.isdeleted_disagreements) if run.ledger else None,
    }


def main():
    rows = []
    for name, fn in ops.DEFAULTS.items():
        try:
            rows.append(analyse(name, fn()))
        except Exception as ex:   # noqa: BLE001 -- record, don't abort the run
            rows.append({"model": name, "error": repr(ex)})
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "q1.json"), "w") as fh:
        json.dump(rows, fh, indent=1, default=str)

    print("\n## Q1 summary: invariants and history per model")
    print("| model | V,E,F,R,S,H | Euler | valid | dH (exp) | dS (exp) | roles ok | base refs ok | unnamed faces | "
          "IsDeleted false+ | consumed | missed |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if "error" in r:
            print(f"| {r['model']} | ERROR {r['error']} |")
            continue
        a = r["audit"] or {}
        print(f"| {r['model']} | {r['after']['VEFRSH']} | {r['after']['euler_ok']} | {r['after']['valid']} | "
              f"{r['dH']} ({r['expected_dH']}) | {r['dS']} ({r['expected_dS']}) | {r['roles_ok']} | {r['base_ok']} | "
              f"{len(r['coverage']['unnamed'])}/{r['coverage']['faces']} | {a.get('false_deleted', '-')} | "
              f"{a.get('consumed', '-')} | {a.get('missed_delete', '-')} |")
    print("\n## Q1 role tables")
    for r in rows:
        if "error" in r:
            continue
        print(f"\n### {r['model']}  ({r['params']})")
        for k, v in r["roles"].items():
            flag = "" if v["ok"] else "   <-- MISMATCH"
            print(f"  {k:48s} n={v['n']} (exp {v['expected']})  {v['desc']}{flag}")
        for k, v in r["base_refs"].items():
            if not v["ok"] or v["events"] not in ([()], []):
                print(f"  [base] {k:41s} n={v['n']} (exp {v['expected']})  events={v['events']}"
                      + ("" if v["ok"] else "   <-- MISMATCH"))
        if r["coverage"]["unnamed"]:
            print(f"  unnamed faces: {r['coverage']['unnamed']}")
        if r["notes"]:
            print(f"  notes: {r['notes']}")
        if r["audit"] and r["audit"]["isdeleted_disagree"]:
            print(f"  audit: {({k: r['audit'][k] for k in ('false_deleted', 'consumed', 'missed_delete')})}")
    return rows


if __name__ == "__main__":
    main()
