"""Design and Build -> JSON for the GUI (docs/gui.md §5).  Pure functions, no HTTP.

Face id i / edge id j are positions in `Build.faces()` / `Build.edges()`, the same order the
mesh uses (`mesh.py`), so the genealogy table and the mesh agree by construction.
"""
from __future__ import annotations

import math
from dataclasses import asdict

from .. import kernel as K
from ..connections import (diagnostics, feature_params, intent_tree, minimal_nodes, feature_nodes,
                           params_through_uses)
from ..errors import CardinalityError, DipmError, PolicyError, ReferenceError_
from ..interpret import MADE_BY_AUTHOR
from ..program import Build, Design, Resolution


def jsonable(x):
    """Best-effort conversion of engine values (Vec3, tuples, numbers) to JSON."""
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return x if math.isfinite(x) else str(x)
    if isinstance(x, K.Vec3):
        return [round(x.x, 6), round(x.y, 6), round(x.z, 6)]
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in x]
    return str(x)


def tag_dict(t, design=None) -> dict:
    """An intent tag for display: with an intent file its note is the node's statement (#45)."""
    if design is not None:
        t = design.display_tag(t)
    return {"node": t.node, "word": t.word, "note": t.note, "text": str(t)}


def design_info(design: Design, path: str | None = None) -> dict:
    params = []
    for n, p in design.params.items():
        params.append({"name": n, "default": jsonable(p.default), "range": jsonable(p.range),
                       "choices": jsonable(p.choices), "unit": p.unit, "doc": p.doc,
                       "kind": "choice" if p.choices is not None else ("range" if p.range is not None else "fixed")})
    lock = design.lock
    return {"name": design.name, "doc": design.doc, "file": path, "params": params,
            "features": [{"id": f.id, "op": f.op_name, "tags": [tag_dict(t, design) for t in f.tags]}
                         for f in design.features],
            "lock": lock.lock if lock else None, "prefs": lock.prefs if lock else None}


def _error(e) -> dict:
    if isinstance(e, DipmError):
        return e.as_dict()
    return {"kind": type(e).__name__, "message": str(e), "feature": None, "intent": [], "invariant": None,
            "expected": None, "got": None, "details": {}}


def _why_entries(w) -> list:
    return [{"tag": str(e.tag), "feature": e.feature, "role": e.tag.role, "source": e.tag.source, "op": e.op,
             "lowered_from": e.lowered_from, "intent": [tag_dict(t) for t in e.intent],
             "instance_intent": [tag_dict(t) for t in e.instance_intent],
             "events": [list(ev) for ev in e.events]} for e in w.entries]


def genealogy_tables(b: Build, failing: set) -> tuple[list, list]:
    """(faces, edges): per-id "why is this here?" rows, keyed like the mesh."""
    if b.shape is None:
        return [], []
    faces, edges = b.faces(), b.edges()
    fmap = K.ShapeMap()
    for f in faces:
        fmap.Add(f)
    frows = []
    for i, f in enumerate(faces):
        w = b.why(f)
        touched_by = []
        for e in w.entries:
            for fid in [e.feature] + [ev[0] for ev in e.events]:
                if fid not in touched_by:
                    touched_by.append(fid)
        frows.append({"id": i, "kind": "face", "surface": K.surface_type(f), "descriptor": w.descriptor,
                      "entries": _why_entries(w), "nodes": w.intent_nodes(),
                      "features": [e.feature for e in w.entries], "touched_by": touched_by,
                      "failing": bool(failing & {e.feature for e in w.entries}),
                      "failing_touched": bool(failing & set(touched_by)), "text": str(w)})
    erows = []
    for j, e in enumerate(edges):
        if K.is_degenerated(e):
            erows.append({"id": j, "kind": "edge", "degenerated": True, "descriptor": "degenerated", "entries": [],
                          "derived_from": [], "nodes": [], "features": [], "text": ""})
            continue
        w = b.why(e)
        adj = [fmap.FindIndex(g) - 1 for g in K.faces_of_edge(b.shape, e)]
        feats = [x.feature for x in w.entries] or sorted({x["features"][0] for i in adj
                                                          for x in [frows[i]] if x["features"]})
        erows.append({"id": j, "kind": "edge", "degenerated": False, "descriptor": w.descriptor,
                      "entries": _why_entries(w), "derived_from": adj if not w.entries else [],
                      "adjacent_faces": adj, "nodes": w.intent_nodes(), "features": feats, "text": str(w)})
    return frows, erows


def _checks(rec) -> dict:
    out = {"checks": [], "counts": None, "volume": None, "refs": [], "refs_ok": True}
    if rec.checks is not None:
        c = rec.checks
        out["checks"] = [{"name": ck.name, "ok": ck.ok, "expected": jsonable(ck.expected), "got": jsonable(ck.got),
                          "note": ck.note} for ck in c.checks]
        out["counts"] = str(c.counts) if c.counts else None
        out["vefrsh"] = list(c.counts.tuple6()) if c.counts else None
        out["volume"] = c.volume
    out["refs"] = [{"ref": r.ref, "count": r.count, "genealogies": list(r.genealogies)} for r in rec.inputs]
    if isinstance(rec.error, (CardinalityError, PolicyError, ReferenceError_)):
        out["refs_ok"] = False
    return out


def interpretations(b: Build) -> dict:
    interp = b.interpretation
    used = {u.id: {"reading": u.reading, "made_by": u.made_by, "source": u.source, "feature": u.feature,
                   "offered": list(u.offered)} for u in b.slots}
    if interp is None:
        slots = [{"id": u.id, "word": u.word, "slot": u.slot, "feature": u.feature, "node": u.node,
                  "chosen": u.reading, "made_by": u.made_by, "status": "unchecked", "sensitivity": "unknown",
                  "sensitivity_detail": "", "rationale": "unchecked ranked default (no lock / resolution)",
                  "readings": list(u.offered), "alternatives": [], "eliminated": [], "statement": ""}
                 for u in b.slots]
        return {"source": b.interpretation_source or "unchecked", "unchecked": bool(b.slots), "slots": slots,
                "questions": [], "notices": [], "used": used}
    slots = []
    for a in interp.assumptions:
        d = asdict(a)
        u = used.get(a.id)
        d["used"] = u["reading"] if u else None
        d["mismatch"] = bool(u and a.made_by != MADE_BY_AUTHOR and u["reading"] != a.chosen)
        slots.append(d)
    return {"source": b.interpretation_source, "unchecked": False, "slots": slots,
            "questions": [asdict(q) for q in interp.questions], "notices": [asdict(n) for n in interp.notices],
            "used": used}


def face_sizes(design: Design, b: Build) -> dict:
    """face id -> its main size in words, for size-on-hover callouts (gui.md §8.3 item 15):
    holes "Ø4.5 hole · 9 mm from edge", other cylinders "Ø…", planes "W × H mm"."""
    if b.shape is None:
        return {}
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopoDS import TopoDS
    out: dict = {}
    edge_d: dict = {}
    recs = {r.id: r for r in b.records}
    for i, f in enumerate(b.faces()):
        ents = b.ledger.who(f)
        e = ents[0] if ents else None
        r = recs.get(e.tag.feature) if e else None
        det = (r.detail or {}) if r else {}
        if e is not None and det.get("centres") is not None and e.tag.role in ("wall", "countersink", "floor"):
            k = int(e.tag.source or 0)
            key = (r.id, k)
            if key not in edge_d:
                edge_d[key] = None
                try:
                    host = b.resolve(design.feature(r.id).on)[0]
                    wire = BRepTools.OuterWire_s(TopoDS.Face(host))
                    c = det["centres"][k]
                    vx = BRepBuilderAPI_MakeVertex(c.pnt()).Vertex()
                    dd = BRepExtrema_DistShapeShape(vx, wire)
                    dd.Perform()
                    edge_d[key] = dd.Value()
                except Exception:   # noqa: BLE001 - the size alone is still useful
                    pass
            dia = det.get("diameter")
            word = {"countersink": "countersink", "floor": "hole floor"}.get(e.tag.role, "hole")
            txt = f"Ø{dia:g} {word}" if e.tag.role != "countersink" else f"Ø{det.get('head') or dia:g} countersink"
            if det.get("screw"):
                txt += f" ({det['screw']})"
            if edge_d[key] is not None:
                txt += f" · {edge_d[key]:.1f} mm from edge"
            out[i] = txt
            continue
        st = BRepAdaptor_Surface(TopoDS.Face(f))
        if st.GetType() == GeomAbs_Cylinder:
            out[i] = f"Ø{2 * st.Cylinder().Radius():.3g}"
            continue
        lo, hi = K.bbox(f)
        ext = sorted([hi.x - lo.x, hi.y - lo.y, hi.z - lo.z], reverse=True)
        out[i] = f"{ext[0]:.1f} × {ext[1]:.1f} mm" if ext[1] > 1e-6 else f"{ext[0]:.1f} mm"
    return out


def reference_objects() -> dict:
    """Sizes of the GUI's ghosted reference objects (gui.md §8.3 item 14), from packs.py: screws
    from the hole's spec (major Ø, head Ø), an ID-1 card, a fingertip and a hand."""
    from .. import packs
    from ..intent_layer import SCREWS
    screws = {k: {"major": packs.SCREW_MAJOR_MM[k], "head": SCREWS[k]["head"], "clearance": SCREWS[k]["clearance"],
                  "length": packs.SCREW_REFERENCE_LENGTH_MM["value"]} for k in SCREWS if k in packs.SCREW_MAJOR_MM}
    return {"screws": screws, "card": packs.ID1_CARD_MM, "fingertip": packs.FINGERTIP_MM, "hand": packs.HAND_MM}


def _guess(made_by: str | None, reviewed: bool) -> bool:
    """A guess (hatched in the GUI, PAIN-12) = not reviewed, whoever made it."""
    return not reviewed


def provenance(b: Build, interp: dict, intent_plain: dict | None, review, assessment) -> dict:
    """key -> {made_by, reviewed, guess, label} for every item a person may need to confirm
    (review B5): readings, assumptions, context, the print orientation and checks."""
    out: dict = {}
    accepted = getattr(review, "accepted", {}) or {}
    for sl in interp["slots"]:
        rev = sl.get("made_by") in ("user preference", "author") or accepted.get(f"slot:{sl['id']}") == sl.get("chosen")
        out[f"slot:{sl['id']}"] = {"made_by": sl.get("made_by"), "reviewed": bool(rev), "label": sl["id"],
                                  "value": sl.get("chosen")}
    def walk(lst):
        for n in lst or []:
            for a in n.get("assumptions") or []:
                out[f"assumption:{a['id']}"] = {"made_by": a.get("made_by", "model"),
                                                "reviewed": a.get("status") == "accepted", "label": a["id"],
                                                "value": a.get("statement", ""), "node": n["id"]}
            walk(n.get("children"))
    walk((intent_plain or {}).get("intents"))
    if assessment is not None:
        for k, v in assessment.context.items():
            out[f"context:{k}"] = {"made_by": v["made_by"], "reviewed": v["reviewed"], "label": k, "value": v["value"]}
        o = assessment.orientation
        if o is not None and not o.get("assumption_id"):
            out["orientation"] = {"made_by": o.get("made_by", "model"), "reviewed": bool(o.get("reviewed")),
                                  "label": "print orientation", "value": o.get("label")}
        for c in assessment.checks:
            out[f"check:{c.id}"] = {"made_by": c.spec_made_by, "reviewed": c.reviewed, "label": c.id,
                                    "value": c.statement, "node": c.node}
    for v in out.values():
        v["guess"] = _guess(v.get("made_by"), v["reviewed"])
    return out


def build_payload(design: Design, b: Build, mesh_id: str | None, warnings_: list = (),
                  intent: dict | None = None, assessment=None) -> dict:
    """`intent`: {"plain": the intent document as plain data, "stale": {node id: info},
    "review": ReviewRecord?} when the design has an intent file (docs/gui.md §7.2); the tree
    then comes from the file.  `assessment`: `assess.Assessment` (computed here, in memory,
    when not given: intent checks, context, orientation, tiered status; gui.md §8.2)."""
    from ..assess import assess
    plain_ = (intent or {}).get("plain")
    review = (intent or {}).get("review")
    if assessment is None:
        reviewed_nodes = (set(review.reviewed) - set((intent or {}).get("stale") or {})) if review is not None else set()
        assessment = assess(design, b, plain_, None, reviewed_nodes)
    interp = interpretations(b)
    # B3: a survivor counts as resolved (meant) only when an intent check at its node confirms it
    confirm = {}
    for c in assessment.checks:
        if c.ran and c.state != "failing":
            confirm.setdefault(c.node, []).append(c.id)
    for sl in interp["slots"]:
        sl["feasible"] = sl.get("feasible") or ([sl["chosen"]] + list(sl.get("alternatives") or []))
        if sl.get("made_by") == MADE_BY_AUTHOR:
            sl["resolution"] = "author"
        elif confirm.get(sl.get("node")):
            sl["resolution"], sl["confirmed_by"] = "confirmed", confirm[sl["node"]]
        else:
            sl["resolution"], sl["confirmed_by"] = "unconfirmed", []
    attention_slots = {q["id"] for q in interp["questions"]} | {n["id"] for n in interp["notices"]}
    attention = {s["feature"] for s in interp["slots"] if s["id"] in attention_slots}
    recs = {r.id: r for r in b.records}
    uses = {r.id: b.uses(r.id) for r in b.records}
    direct = feature_params(design)
    allp = params_through_uses(direct, uses)
    failing = {r.id for r in b.records if not r.ok}
    for e in b.errors:
        if getattr(e, "feature", None):
            failing.add(e.feature)
    plain = intent.get("plain") if intent else None
    stale = (intent or {}).get("stale") or {}
    tree = intent_tree(design, b, attention, intent=plain, stale=stale.keys())
    parents = tree["parents"] if plain is not None else None
    features = []
    for i, f in enumerate(design.features):
        r = recs.get(f.id)
        status = "not_built" if r is None else ("fail" if not r.ok else ("warn" if f.id in attention else "ok"))
        row = {"id": f.id, "index": i, "op": (r.op if r else f.op_name),
               "lowered_from": (r.lowered_from if r else getattr(f, "lowered_from", None)),
               "tags": [tag_dict(t, design) for t in f.tags], "nodes": feature_nodes(f),
               "serves": minimal_nodes([n for n in feature_nodes(f) if n in tree["nodes"]], parents),
               "instances": {k: [tag_dict(t, design) for t in v] for k, v in (r.instance_tags if r else {}).items()},
               "status": status, "ms": r.ms if r else None,
               "uses": uses.get(f.id, []), "references": b.references(f.id) if r else [],
               "reads": [{"what": d, "features": list(fs)} for d, fs in (r.reads if r else [])],
               "params": direct.get(f.id, []), "params_all": allp.get(f.id, direct.get(f.id, [])),
               "slots": [s["id"] for s in interp["slots"] if s["feature"] == f.id],
               "error": _error(r.error) if r and r.error else None, "detail": jsonable(r.detail) if r else {}}
        row.update(_checks(r) if r else {"checks": [], "counts": None, "volume": None, "refs": [], "refs_ok": True})
        inst_nodes = [t["node"] for ts in row["instances"].values() for t in ts]
        row["stale"] = [n for n in dict.fromkeys(row["nodes"] + inst_nodes) if n in stale]
        features.append(row)
    diag = diagnostics(design, tree, uses)
    frows, erows = genealogy_tables(b, failing)
    sizes = face_sizes(design, b)
    for fr in frows:
        fr["size"] = sizes.get(fr["id"], "")
    sig = b.signature.as_dict() if b.signature else None
    checks = [c.as_dict() for c in assessment.checks]
    # per node: worst state of the checks that ran there; how it was reviewed (#54 overrides)
    rank = {"failing": 0, "thin": 1, "ample": 2}
    overrides = getattr(review, "overrides", {}) or {}
    for nid, n in tree["nodes"].items():
        mine = [c for c in assessment.checks if c.node == nid]
        ran = [c.state for c in mine if c.ran]
        n.check_state = min(ran, key=lambda x: rank[x]) if ran else ""
        n.checks_not_run = sum(1 for c in mine if not c.ran)
        if n.in_file:
            failing_here = n.check_state == "failing" or n.status == "fail"
            if n.stale:
                n.review_state = "unreviewed" if (review is None or nid not in review.reviewed) else "stale"
            elif nid in overrides and failing_here:
                n.review_state = "reviewed_failing"
            else:
                n.review_state = "reviewed"
    prov = provenance(b, interp, plain_, review, assessment)
    guesses = sorted(k for k, v in prov.items() if v["guess"] and not k.startswith("check:"))
    status = dict(assessment.status)
    status["guesses"] = len(guesses)
    o = assessment.orientation
    return {
        "design": design.name, "params": jsonable(b.params), "ok": b.ok, "kernel_ok": b.ok, "status": status,
        "intent_checks": jsonable(checks),
        "context": {"items": assessment.context, "summary": assessment.context_summary,
                    "assumed": any(not v["reviewed"] for v in assessment.context.values())},
        "orientation": jsonable({k: v for k, v in o.items() if k not in ("inference",)}) if o else None,
        "appearance": jsonable(assessment.appearance), "provenance": prov, "guesses": guesses,
        "references": reference_objects(),
        "overrides": jsonable(overrides),
        "error_count": len(b.errors), "errors": [_error(e) for e in b.errors], "ms": b.ms,
        "features": features, "failing": sorted(failing),
        "tree": {"roots": tree["roots"], "order": tree["order"], "from_file": tree["from_file"],
                 "missing": tree["missing"],
                 "nodes": {k: v.as_dict() for k, v in tree["nodes"].items()}},
        "stale": {k: jsonable(v) for k, v in stale.items()},
        "diagnostics": diag, "interpretations": interp, "signature": sig,
        "faces": frows, "edges": erows, "mesh_id": mesh_id,
        "coverage": {"faces": len(frows), "with_genealogy": sum(1 for f in frows if f["entries"])},
        "warnings": list(warnings_),
    }
