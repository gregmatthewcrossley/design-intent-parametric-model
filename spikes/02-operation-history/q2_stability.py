"""Q2 -- edit stability: sweep each operation's driving parameters.

At every parameter point the harness rebuilds the model and records:
  * build ok / kernel failure;
  * Euler ok, BRepCheck validity, dH and dS vs declared;
  * every role's cardinality vs declared, its descriptor set, and the base references' genealogy;
  * the topology-only adjacency hash (spike 01) -> 'topology class'.
A point is AS DECLARED when all of the above match.  Deviations are listed with their parameters, so
RESULTS.md can separate legitimate topology changes (pattern instance falls off the part, chamfer
consumes a face) from history defects.
"""
from __future__ import annotations

import itertools
import json
import os

import ops
from common import HERE, checks, describe, topo
from OCP.TopAbs import TopAbs_FACE
from q1_roles import card_ok


def grid(**axes):
    keys = list(axes)
    return [dict(zip(keys, vals)) for vals in itertools.product(*axes.values())]


SWEEPS = {
    "revolve": (ops.revolve, grid(angle=[15, 90, 180, 270, 345, 359.9, 360], r_in=[0.0, 5.0])
                + grid(angle=[90, 360], top_slant=[2.0], r_in=[5.0])),
    "chamfer.two_edges": (ops.chamfer, grid(d=[0.5, 1, 3, 5, 9.9, 10, 15, 19.9, 20, 25])),
    "chamfer.ridge": (lambda d: ops.chamfer(d, "ridge"), grid(d=[2, 5, 10, 14, 14.9, 14.99, 15, 16])),
    "chamfer.all12": (lambda d: ops.chamfer(d, "all12"), grid(d=[0.5, 2, 5, 9.9, 10, 12])),
    "shell.open_top": (ops.shell, grid(t=[-0.5, -2, -5, -9.9, -10, -14.9, -15, 2])),
    "shell.two_openings": (lambda t: ops.shell(t, ("cap(END)", "side(a-b)")), grid(t=[-1, -2, -5, -9.9, 2])),
    "shell.closed_void": (ops.shell_void, grid(t=[0.5, 2, 5, 9.9, 10, 12])),
    "loft.2sec": (ops.loft, grid(s1=[4, 10, 16, 20, 30], twist=[0, 15, 45])),
    "loft.3sec": (lambda ruled, z1: ops.loft(ruled=ruled, z1=z1, third="square"),
                  grid(ruled=[False, True], z1=[5, 15, 30])),
    "loft.square_to_circle": (lambda s1, ruled: ops.loft(s1=s1, ruled=ruled, third="circle"),
                              grid(s1=[8, 16, 24], ruled=[False, True])),
    "sweep.open": (lambda bend_r, pw, builder: ops.sweep("open", bend_r=bend_r, pw=pw, builder=builder),
                   grid(bend_r=[5, 10, 20, 40], pw=[2, 6, 12], builder=["pipe", "pipeshell"])),
    "sweep.closed": (lambda pw, profile: ops.sweep("closed", pw=pw, profile=profile),
                     grid(pw=[2, 6, 20], profile=["rect", "circle"])),
    "draft": (ops.draft, grid(angle=[0.5, 1, 5, 10, 20, 30, 35, 36.8, 37, 40, -5, -20])),
    "pattern.linear_holes": (lambda n, pitch, combine: ops.pattern_holes("linear", n=n, pitch=pitch, combine=combine),
                             grid(n=[1, 2, 3, 4], pitch=[12, 7, 5], combine=["tool_list", "sequential", "compound"])),
    "pattern.circular_holes": (lambda n, combine: ops.pattern_holes("circular", n=n, combine=combine),
                               grid(n=[1, 3, 4, 6, 8, 10, 11, 12], combine=["tool_list", "compound"])),
    "pattern.linear_bosses": (ops.pattern_bosses, grid(n=[1, 2, 3], pitch=[12, 5], combine=["tool_list", "compound"])),
    "mirror": (lambda gap, clean: ops.mirror(gap, clean=clean), grid(gap=[-5, -1, 0, 1, 5], clean=[False, True])),
}


def point(fn, params) -> dict:
    try:
        run = fn(**params)
    except Exception as ex:   # noqa: BLE001
        return {"params": params, "built": False, "error": str(ex)[:120]}
    if run.shape is None or run.shape.IsNull() or not topo.subshapes(run.shape, TopAbs_FACE):
        return {"params": params, "built": False, "error": "kernel returned an empty/null shape without raising"}
    after = checks(run.shape)
    if run.before is not None:
        b = checks(run.before)
        dH, dS = after["VEFRSH"][5] - b["VEFRSH"][5], after["VEFRSH"][4] - b["VEFRSH"][4]
    else:
        dH, dS = after["VEFRSH"][5], after["VEFRSH"][4]
    role_dev = {r: (len(s), run.expected_card.get(r)) for r, s in run.roles.items()
                if not card_ok(len(s), run.expected_card.get(r))}
    base_dev, genealogy = {}, {}
    if run.ledger is not None:
        for k, exp in run.base_expected.items():
            n = run.ledger.count(*k)
            if n != exp:
                base_dev[".".join(map(str, k))] = (n, exp)
            genealogy[".".join(map(str, k))] = sorted({tuple(ev[1] for ev in g) for g in run.ledger.genealogy(*k)})
    desc = {r: sorted({describe(x, run.shape) for x in s}) for r, s in run.roles.items()}
    rec = {"params": params, "built": True, "variant": run.variant, "VEFRSH": after["VEFRSH"],
           "euler_ok": after["euler_ok"], "valid": after["valid"], "solids": after["solids"],
           "dH": dH, "exp_dH": run.expected_dH, "dS": dS, "exp_dS": run.expected_dS,
           "role_dev": role_dev, "base_dev": base_dev, "genealogy": genealogy, "desc": desc,
           "adj_topo": topo.adjacency_hash(run.shape, geometric=False)[:12],
           "notes": [n for n in run.notes if isinstance(n, str)]}
    rec["as_declared"] = (after["euler_ok"] and after["valid"] and dH == run.expected_dH and dS == run.expected_dS
                          and not role_dev and not base_dev)
    return rec


def run_sweep(name):
    fn, pts = SWEEPS[name]
    return [point(fn, p) for p in pts]


def summarise(name, recs) -> dict:
    built = [r for r in recs if r["built"]]
    classes = {}
    for r in built:
        classes.setdefault(r["adj_topo"], []).append(r["params"])
    return {"sweep": name, "points": len(recs), "built": len(built),
            "as_declared": sum(r["as_declared"] for r in built),
            "invalid": sum(not r["valid"] for r in built), "euler_fail": sum(not r["euler_ok"] for r in built),
            "topology_classes": len(classes)}


def main():
    out = {}
    print("\n## Q2 stability sweeps")
    print("| sweep | points | built | as declared | invalid | Euler fail | topology classes |")
    print("|---|---|---|---|---|---|---|")
    for name in SWEEPS:
        recs = run_sweep(name)
        s = summarise(name, recs)
        out[name] = {"summary": s, "points": recs}
        print(f"| {name} | {s['points']} | {s['built']} | {s['as_declared']} | {s['invalid']} | {s['euler_fail']} | "
              f"{s['topology_classes']} |")
    print("\n## Q2 deviations (points not as declared, and kernel failures)")
    for name, d in out.items():
        for r in d["points"]:
            if not r["built"]:
                print(f"- {name} {r['params']}: KERNEL FAILURE: {r['error']}")
            elif not r["as_declared"]:
                bits = []
                if not r["valid"]:
                    bits.append("INVALID")
                if not r["euler_ok"]:
                    bits.append("EULER FAIL")
                if r["dH"] != r["exp_dH"]:
                    bits.append(f"dH={r['dH']} (exp {r['exp_dH']})")
                if r["dS"] != r["exp_dS"]:
                    bits.append(f"dS={r['dS']} (exp {r['exp_dS']})")
                if r["role_dev"]:
                    bits.append(f"roles {r['role_dev']}")
                if r["base_dev"]:
                    bits.append(f"base {r['base_dev']}")
                print(f"- {name} {r['params']}: VEFRSH={r['VEFRSH']} " + "; ".join(bits))
    # genealogy stability: within each sweep, among as-declared points of one topology class, genealogy constant?
    print("\n## Q2 genealogy / descriptor stability within a topology class")
    for name, d in out.items():
        by_cls = {}
        for r in d["points"]:
            if r["built"] and r["as_declared"]:
                by_cls.setdefault(r["adj_topo"], []).append(r)
        for cls, rs in by_cls.items():
            g = {json.dumps(r["genealogy"], sort_keys=True) for r in rs}
            ds = {json.dumps(r["desc"], sort_keys=True) for r in rs}
            print(f"- {name} class {cls}: {len(rs)} pts, distinct genealogies={len(g)}, distinct role descriptors={len(ds)}")
        d["genealogy_stability"] = {cls: {"n": len(rs),
                                          "genealogies": len({json.dumps(r['genealogy'], sort_keys=True) for r in rs}),
                                          "descriptors": len({json.dumps(r['desc'], sort_keys=True) for r in rs})}
                                    for cls, rs in by_cls.items()}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "q2.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    return out


if __name__ == "__main__":
    main()
