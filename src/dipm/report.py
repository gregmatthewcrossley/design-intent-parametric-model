"""Human-readable build report (used by the CLI).  Plain text, no colour."""
from __future__ import annotations

from .program import Build, Resolution
from .refs import fmt_genealogy


def build_report(b: Build, show_refs: bool = True, show_faces: bool = False, assessment=None) -> str:
    """The report.  `assessment` (assess.Assessment) adds context, print orientation and the
    intent checks with margins; without one it is computed from the files next to the design
    (never written).  The result line is tiered: there is no bare PASS (B1)."""
    d = b.design
    if assessment is None:
        assessment = _assess(b)
    L = [f"Design: {d.name}" + (f" - {d.doc}" if d.doc else "")]
    L.append("Parameters:")
    for n, p in d.params.items():
        v = b.params[n]
        rng = f" range {p.range}" if p.range else (f" choices {p.choices}" if p.choices else "")
        mark = "" if v == p.default else f"   (default {p.default})"
        L.append(f"  {n} = {v}{(' ' + p.unit) if p.unit and p.choices is None else ''}{rng}{mark}")
    L.append("")
    L.append("Features (invariants after each: validity, Euler, ΔH, ΔS, volume sign):")
    for r in b.records:
        tags = ", ".join(str(d.display_tag(t)) for t in r.tags) or "-"
        low = f" <- {r.lowered_from}" if r.lowered_from else ""
        status = "OK  " if r.ok else "FAIL"
        L.append(f"  [{status}] {r.id:<6} {r.op}{low}   intent: {tags}   ({r.ms:.1f} ms)")
        if r.instance_tags:
            L.append("         instances: " + ", ".join(f"k={k}: {', '.join(str(d.display_tag(t)) for t in v)}"
                                                      for k, v in sorted(r.instance_tags.items())))
        if r.checks is not None:
            c = r.checks
            parts = []
            for ck in c.checks:
                if ck.name in ("delta_H", "delta_S"):
                    parts.append(f"{ck.name}={ck.got}{'' if ck.ok else f' (expected {ck.expected})'}")
                else:
                    parts.append(f"{ck.name}:{'ok' if ck.ok else 'FAIL'}")
            L.append(f"         {c.counts}  vol={c.volume:.6g}  " + "  ".join(parts))
        if r.inputs and show_refs:
            for res in r.inputs:
                L.append(f"         uses {res.ref} -> {res.count}" +
                         (f"  [{'; '.join(res.genealogies)}]" if res.genealogies else ""))
        if r.error is not None:
            L += ["         " + line for line in str(r.error).splitlines()]
    L.append("")
    from .interpret import format_interpretation      # architecture §10.2 / §4.8
    il = format_interpretation(b.interpretation, b.slots, b.interpretation_source)
    if il:
        L += il + [""]
    if assessment is not None:
        from .checks import format_checks
        ctx = ", ".join(f"{k}={v['value']}" + ("" if v["reviewed"] else " (assumed, unreviewed)")
                        for k, v in assessment.context.items())
        L.append(f"Context: {ctx}")
        o = assessment.orientation
        if o is not None:
            L.append(f"Print orientation: {o.get('label')}  [made_by: {o.get('made_by')}; "
                     f"{'accepted' if o.get('reviewed') else 'unreviewed'}; {o.get('source', '')}]")
            if o.get("rationale"):
                L.append(f"  why: {o['rationale']}")
        st = assessment.status["intent"]
        L.append(f"Intent checks ({st['run']} of {st['total']} run; worst case over the input ranges):")
        L += format_checks(assessment.checks)
        L.append("")
    if b.signature:
        s = b.signature
        L.append("Signature:")
        L.append(f"  (V,E,F,R,S,H) = {s.VEFRSH}   volume = {s.volume:.6g} mm^3")
        L.append(f"  adjacency hash (geometry) = {s.adj_geom[:16]}")
        L.append(f"  adjacency hash (topology) = {s.adj_topo[:16]}")
        L.append(f"  role-geometry fingerprint = {s.roles_geom[:16]}")
        mode, data = b.canonical()
        import hashlib
        L.append(f"  canonical ({mode}) sha256 = {hashlib.sha256(data).hexdigest()[:16]}")
    if d.exports and show_refs:
        L.append("")
        L.append("Named exports (resolved on the final solid):")
        for name, res in b.exports.items():
            if isinstance(res, Resolution):
                L.append(f"  {name:<14} = {res.ref} -> {res.count}  [{'; '.join(res.genealogies)}]")
            else:
                L.append(f"  {name:<14} ERROR {getattr(res, 'message', res)}")
    if show_faces and b.shape is not None:
        L.append("")
        L.append("Why is each face here?")
        for f in b.faces():
            w = b.why(f)
            L += ["  " + line for line in str(w).splitlines()]
    unt = b.untracked_faces() if b.shape is not None else []
    L.append("")
    L.append(f"Coverage: {len(b.faces()) - len(unt) if b.shape is not None else 0}/"
             f"{len(b.faces()) if b.shape is not None else 0} faces have a genealogy")
    if assessment is not None:
        L.append(f"Result: {assessment.status['text']}  ({b.ms:.0f} ms)")
    else:
        L.append(f"Result: kernel invariants {'pass' if b.ok else 'FAIL'} ({len(b.errors)} error(s)) · intent checks: "
                 f"not assessed  ({b.ms:.0f} ms)")
    return "\n".join(L)


def _assess(b: Build):
    d = b.design
    path = d.lock.design_file if d.lock is not None else None
    if path is None:
        from .assess import assess
        try:
            return assess(d, b, None, None)
        except Exception:   # noqa: BLE001
            return None
    from .assess import assess_file
    try:
        return assess_file(d, b, path)[0]
    except Exception:   # noqa: BLE001 - the report still shows the kernel tier
        return None
