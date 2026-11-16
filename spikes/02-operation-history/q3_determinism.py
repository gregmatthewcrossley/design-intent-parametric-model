"""Q3 -- determinism: rebuild every default model (ops.DEFAULTS) repeatedly in-process and in separate
processes (distinct PYTHONHASHSEED / ASLR; parallel BOP off and on), and compare:
  * BRep text bytes (canonical serialization, spike 01),
  * (V,E,F,R,S,H) and both adjacency hashes,
  * a ROLE fingerprint: for every role, the positions of its sub-shapes in the result's TopExp map.
    Identical BRep + identical role fingerprint means history maps roles to the same sub-shapes every time;
  * an order-free ROLE-GEOMETRY fingerprint (per role: rounded centroid + area), which stays meaningful
    when the BRep bytes / sub-shape order are not reproducible (found: BRepOffset join mode).

Worker mode:  python q3_determinism.py --worker --parallel 0|1 --repeat N
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict

import ops
from common import HERE, ShapeMap, topo
from OCP.BOPAlgo import BOPAlgo_Options
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp


def role_fingerprint(run) -> str:
    m = ShapeMap()
    for k in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
        TopExp.MapShapes_s(run.shape, k, m)
    parts = []
    for r, shapes in sorted(run.roles.items()):
        parts.append(r + ":" + ",".join(str(i) for i in sorted(m.FindIndex(s) for s in shapes)))
    if run.ledger is not None:
        for e in run.ledger.items:
            parts.append(f"L:{e.tag}:{m.FindIndex(e.shape)}:{e.genealogy}")
    return hashlib.sha256("|".join(sorted(parts)).encode()).hexdigest()[:16]


def role_geom_fingerprint(run) -> str:
    """Order-free: per role, the sorted (centroid, area) of its faces rounded to 1e-6 (edges: centroid+length)."""
    parts = []
    for r, shapes in sorted(run.roles.items()):
        g = sorted(tuple(round(c, 6) for c in topo.centroid(x)) + (round(topo.area(x), 6),) for x in shapes
                   if x.ShapeType() == TopAbs_FACE)
        parts.append(f"{r}:{g}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def fingerprint(run) -> dict:
    sig = topo.signature(run.shape)
    return {"VEFRSH": list(sig["VEFRSH"]), "adj": sig["adj"][:16], "adj_topo": sig["adj_topo"][:16],
            "brep": topo.sha(topo.brep_bytes(run.shape))[:16], "roles": role_fingerprint(run),
            "roles_geom": role_geom_fingerprint(run)}


KEYS = ["VEFRSH", "adj", "adj_topo", "brep", "roles", "roles_geom"]


def run_worker(parallel: bool, repeat: int, tag: str):
    BOPAlgo_Options.SetParallelMode_s(parallel)
    out = []
    for name, fn in ops.DEFAULTS.items():
        for k in range(repeat):
            t0 = time.perf_counter()
            run = fn()
            dt = time.perf_counter() - t0
            fp = fingerprint(run)
            fp.update({"model": name, "parallel": parallel, "rep": k, "proc": tag, "build_ms": round(1000 * dt, 2)})
            out.append(fp)
    return out


def summarise(records):
    groups = defaultdict(lambda: defaultdict(set))
    procs, n, times = defaultdict(set), defaultdict(int), defaultdict(list)
    for r in records:
        for k in KEYS:
            groups[r["model"]][k].add(json.dumps(r[k]))
        procs[r["model"]].add(r["proc"])
        n[r["model"]] += 1
        times[r["model"]].append(r["build_ms"])
    return [{"model": m, "n": n[m], "processes": len(procs[m]),
             **{f"distinct_{k}": len(d[k]) for k, _ in zip(KEYS, KEYS)},
             "median_build_ms": sorted(times[m])[len(times[m]) // 2]} for m, d in groups.items()]


def main(n_inproc=10, n_procs=4, repeat=2):
    recs = []
    for par in (False, True):
        recs += run_worker(par, n_inproc // 2, "main")
    for i in range(n_procs):
        env = dict(os.environ, PYTHONHASHSEED=str(2000 + i))
        cp = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", "--parallel", str(i % 2),
                             "--repeat", str(repeat), "--tag", f"p{i}"], cwd=HERE, env=env,
                            capture_output=True, text=True, check=True)
        recs += [json.loads(l) for l in cp.stdout.splitlines() if l.startswith("{")]
    rows = summarise(recs)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "q3.json"), "w") as fh:
        json.dump({"summary": rows, "n_inproc": n_inproc, "n_procs": n_procs, "repeat": repeat}, fh, indent=1)
    print(f"\n## Q3 determinism: {n_inproc} in-process builds (parallel BOP off/on) + {n_procs} processes x {repeat}"
          " (distinct PYTHONHASHSEED, parallel alternating); number of DISTINCT values per model")
    print("| model | builds | processes | " + " | ".join(KEYS) + " | median ms |")
    print("|---" * (len(KEYS) + 4) + "|")
    for r in rows:
        print(f"| {r['model']} | {r['n']} | {r['processes']} | "
              + " | ".join(str(r[f'distinct_{k}']) for k in KEYS) + f" | {r['median_build_ms']} |")
    bad = [r["model"] for r in rows if any(r[f"distinct_{k}"] != 1 for k in KEYS)]
    print(f"\nmodels with any variation: {bad or 'none'}")
    bad_geom = [r["model"] for r in rows if any(r[f"distinct_{k}"] != 1 for k in ("VEFRSH", "adj", "adj_topo", "roles_geom"))]
    print(f"models whose topology / geometry / role-geometry varied: {bad_geom or 'none'}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--parallel", type=int, default=0)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--tag", default="w")
    a = ap.parse_args()
    if a.worker:
        for r in run_worker(bool(a.parallel), a.repeat, a.tag):
            print(json.dumps(r))
    else:
        main()
