"""Q3 -- determinism of rebuilds: in-process and across processes, parallel BOP off/on.

Worker mode:  python q3_determinism.py --worker --parallel 0|1 --repeat N
prints one JSON line per model per repeat.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict

from OCP.BOPAlgo import BOPAlgo_Options
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound

import bracket
import topo

HERE = os.path.dirname(os.path.abspath(__file__))


def hole_grid(parallel: bool):
    """Plate with a 10x10 grid of holes cut in ONE boolean (exercises the parallel BOP paths)."""
    from q1_euler import box, cyl_z
    c, bb = TopoDS_Compound(), BRep_Builder()
    bb.MakeCompound(c)
    for i in range(10):
        for j in range(10):
            bb.Add(c, cyl_z(5 + 10 * i, 5 + 10 * j, 3, -1, 7))
    op = BRepAlgoAPI_Cut(box(100, 100, 5), c)
    return op.Shape()


def models(parallel: bool):
    from q1_euler import fillet_all, box, cut, cyl_z
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    return {
        "bracket(200,5)": lambda: bracket.build_bracket(bracket.Params(parallel=parallel)).shape,
        "bracket(300,8)": lambda: bracket.build_bracket(bracket.Params(shelf_depth=300, t=8, parallel=parallel)).shape,
        "box+hole": lambda: cut(box(50, 30, 5), cyl_z(25, 15, 4, -1, 7)),
        "sphere+hole": lambda: cut(BRepPrimAPI_MakeSphere(10).Shape(), cyl_z(0, 0, 3, -20, 40)),
        "filleted box": lambda: fillet_all(box(), 2.0),
        "plate 10x10 holes": lambda: hole_grid(parallel),
    }


def fingerprint(shape) -> dict:
    sig = topo.signature(shape)
    return {"VEFRSH": list(sig["VEFRSH"]), "adj": sig["adj"][:16], "adj_topo": sig["adj_topo"][:16],
            "brep": topo.sha(topo.brep_bytes(shape))[:16],
            "step_stripped": topo.sha(topo.step_bytes(shape, True))[:16],
            "step_raw": topo.sha(topo.step_bytes(shape, False))[:16],
            "step_canonical": topo.sha(topo.canonical_step(topo.step_bytes(shape, False)))[:16],
            "step_b123d": topo.sha(topo.step_bytes_build123d(shape))[:16],
            "volume": round(topo.volume(shape), 6)}


def run_worker(parallel: bool, repeat: int, tag: str):
    BOPAlgo_Options.SetParallelMode_s(parallel)
    out = []
    for name, fn in models(parallel).items():
        for k in range(repeat):
            t0 = time.perf_counter()
            s = fn()
            dt = time.perf_counter() - t0
            fp = fingerprint(s)
            fp.update({"model": name, "parallel": parallel, "rep": k, "proc": tag, "build_s": round(dt, 4)})
            out.append(fp)
    return out


KEYS = ["VEFRSH", "adj", "adj_topo", "brep", "step_stripped", "step_canonical", "step_b123d", "step_raw", "volume"]


def summarise(records):
    """For each (model, parallel, key): number of distinct values."""
    groups = defaultdict(lambda: defaultdict(set))
    times = defaultdict(list)
    for r in records:
        g = (r["model"], r["parallel"])
        for k in KEYS:
            groups[g][k].add(json.dumps(r[k]))
        times[g].append(r["build_s"])
    rows = []
    for (m, p), d in sorted(groups.items()):
        rows.append({"model": m, "parallel": p, "n": len(times[(m, p)]),
                     **{f"distinct_{k}": len(d[k]) for k in KEYS},
                     "mean_build_ms": round(1000 * sum(times[(m, p)]) / len(times[(m, p)]), 1)})
    return rows


def main(n_inproc=20, n_procs=6):
    results = {}
    # (a) in-process, N repeats, parallel off and on
    inproc = []
    for par in (False, True):
        inproc += run_worker(par, n_inproc, "main")
    results["in_process"] = summarise(inproc)

    # (b) separate processes (different PYTHONHASHSEED and ASLR layout), 2 repeats each
    cross = []
    for par in (0, 1):
        for i in range(n_procs):
            env = dict(os.environ, PYTHONHASHSEED=str(1000 + i))
            cp = subprocess.run([sys.executable, __file__, "--worker", "--parallel", str(par), "--repeat", "2",
                                 "--tag", f"p{i}"], cwd=HERE, env=env, capture_output=True, text=True, check=True)
            cross += [json.loads(l) for l in cp.stdout.splitlines() if l.startswith("{")]
    results["cross_process"] = summarise(cross)

    # (c) everything pooled: in-process + cross-process, parallel off + on
    pooled = [dict(r, parallel="any") for r in inproc + cross]
    results["pooled_all"] = summarise(pooled)

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "q3.json"), "w") as fh:
        json.dump(results, fh, indent=1)
    for section in ("in_process", "cross_process", "pooled_all"):
        print(f"\n## Q3 {section}")
        print("| model | parallel | n | " + " | ".join(KEYS) + " | mean build ms |")
        print("|---" * (len(KEYS) + 4) + "|")
        for r in results[section]:
            print(f"| {r['model']} | {r['parallel']} | {r['n']} | "
                  + " | ".join(str(r[f'distinct_{k}']) for k in KEYS) + f" | {r['mean_build_ms']} |")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--parallel", type=int, default=0)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--tag", default="w")
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    if a.worker:
        for r in run_worker(bool(a.parallel), a.repeat, a.tag):
            print(json.dumps(r))
    else:
        main(n_inproc=a.n)
