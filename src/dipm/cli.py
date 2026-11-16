"""Tiny CLI.

  python -m dipm build FILE [--param name=value ...] [--out out/] [--step] [--faces]
                            [--prefs P] [--lock L] [--reinterpret]
  python -m dipm stability FILE
  python -m dipm interpret FILE [--prefs P] [--lock L] [--no-write]
  python -m dipm answer FILE ASSUMPTION_ID READING --prefs P [--scope node|design|house] [--note TEXT]

The design file must define a module-level `design` (a `dipm.Design`) or a `make_design()`.
Interpretations (architecture §10 item 2): `build` reads `<FILE stem>.interpretations.json`
(the lock) unless the design attached its own; a missing or stale lock is re-resolved in
memory.  `interpret` re-resolves and writes the lock; `answer` remembers a choice in a
preferences file, then re-resolves.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import warnings

from .errors import DipmError
from .program import Design
from .report import build_report


def load_design(path: str) -> Design:
    spec = importlib.util.spec_from_file_location("_dipm_design_" + os.path.basename(path).replace(".", "_"), path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "design"):
        return mod.design
    if hasattr(mod, "make_design"):
        return mod.make_design()
    raise SystemExit(f"{path} defines neither `design` nor `make_design()`")


def _params(items) -> dict:
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"--param expects name=value, got {it!r}")
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _attach_lock(design: Design, path: str, lock: str | None, prefs: str | None) -> None:
    """Use the design's own lock spec if it set one, overridden by --lock / --prefs."""
    cur = design.lock
    design.use_lock(path, lock or (cur.lock if cur else None), prefs or (cur.prefs if cur else None))


def _interpret_and_write(design: Design, path: str, write: bool) -> int:
    from .interpret import format_interpretation, write_lock
    interp = design.ensure_interpretations(force=True)
    print("\n".join(format_interpretation(interp, source="re-resolved")))
    print(f"  ({interp.stats.get('builds', 0)} builds over {len(interp.sample_points)} sample points)")
    if interp.questions:
        print(f"\n{len(interp.questions)} question(s) need an answer: the readings above pass every check "
              f"but give different geometry.  Answer with:")
        for q in interp.questions:
            print(f"  python -m dipm answer {path} {q.id} <{'|'.join(o['reading'] for o in q.options)}> --prefs <file>")
    if write:
        write_lock(interp, design.lock.lock)
        print(f"\nwrote {os.path.relpath(design.lock.lock)}")
    return 1 if any(n.kind == "no_survivor" for n in interp.notices) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dipm", description="design-intent parametric model: v0 DSL core")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build a design and print a report")
    b.add_argument("file")
    b.add_argument("--param", "-p", action="append", help="name=value (repeatable)")
    b.add_argument("--out", help="directory to write <name>.brep (and .step with --step)")
    b.add_argument("--step", action="store_true", help="also write STEP (interchange only)")
    b.add_argument("--faces", action="store_true", help="print 'why is this here?' for every face")
    b.add_argument("--prefs", help="preferences JSON (remembered answers)")
    b.add_argument("--lock", help="interpretations lock file (default <file stem>.interpretations.json)")
    b.add_argument("--reinterpret", action="store_true", help="re-resolve interpretations in memory, ignoring the lock")
    s = sub.add_parser("stability", help="run the stability harness over declared parameter ranges")
    s.add_argument("file")
    i = sub.add_parser("interpret", help="resolve ambiguous intent-word slots and write the lock file")
    i.add_argument("file")
    i.add_argument("--prefs", help="preferences JSON (remembered answers)")
    i.add_argument("--lock", help="lock file to write (default <file stem>.interpretations.json)")
    i.add_argument("--no-write", action="store_true", help="print only; do not write the lock")
    an = sub.add_parser("answer", help="remember the answer to an interpretation question")
    an.add_argument("file")
    an.add_argument("assumption_id", help="e.g. A.3.cable/centered_on.point")
    an.add_argument("reading")
    an.add_argument("--prefs", required=True, help="preferences JSON to write (created if missing)")
    an.add_argument("--scope", choices=("node", "design", "house"), default="node",
                    help="node: this design's intent node (default); design: every node of this design; "
                         "house: every design")
    an.add_argument("--note", default="", help="why (kept in the preferences file)")
    an.add_argument("--lock", help="lock file to update")
    an.add_argument("--no-resolve", action="store_true", help="only record the preference")
    a = ap.parse_args(argv)

    design = load_design(a.file)
    if a.cmd == "build":
        _attach_lock(design, a.file, a.lock, a.prefs)
        try:
            params = design.resolve_params(_params(a.param))
        except DipmError as e:
            print(e, file=sys.stderr)
            return 2
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            design.ensure_interpretations(force=a.reinterpret)
        for w in caught:
            print(f"warning: {w.message}", file=sys.stderr)
        bld = design.build(params, on_fail="record")
        print(build_report(bld, show_faces=a.faces))
        if a.out and bld.shape is not None:
            os.makedirs(a.out, exist_ok=True)
            suffix = "".join(f"_{k}-{v}" for k, v in sorted(_params(a.param).items()))
            stem = os.path.join(a.out, design.name + suffix.replace("#", ""))
            for p in bld.write(stem, brep=True, step=a.step):
                print(f"wrote {p}")
        return 0 if bld.ok else 1
    if a.cmd == "stability":
        from .stability import run
        _attach_lock(design, a.file, None, None)
        rep = run(design)
        print(rep)
        return 0 if rep.ok else 1
    if a.cmd == "interpret":
        _attach_lock(design, a.file, a.lock, a.prefs)
        return _interpret_and_write(design, a.file, not a.no_write)
    if a.cmd == "answer":
        from .interpret import Preferences
        _attach_lock(design, a.file, a.lock, a.prefs)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            interp = design.ensure_interpretations()
        try:
            asm = interp.assumption(a.assumption_id)
        except KeyError as e:
            print(e.args[0], file=sys.stderr)
            return 2
        if a.reading not in asm.readings:
            print(f"{a.reading!r} is not a reading of {asm.id}; offered: {asm.readings}", file=sys.stderr)
            return 2
        prefs = Preferences.load(a.prefs)
        ctx = {"node": f"{design.name}:{asm.node}", "design": f"{design.name}:*", "house": "*"}[a.scope]
        key = prefs.record(asm.word, asm.slot, ctx, a.reading, a.note)
        prefs.save()
        print(f"recorded {key} = {a.reading} in {a.prefs}")
        if any(e["reading"] == a.reading for e in asm.eliminated):
            print(f"warning: {a.reading!r} is currently eliminated by a check; it will be overridden", file=sys.stderr)
        if a.no_resolve:
            return 0
        return _interpret_and_write(design, a.file, True)
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
