"""Impact of a purpose change (docs/purpose-loop.md §3 step 1).

dipm diffs the purpose tree against the **review baseline** (`<design>.review.json`: what each
node said when its solution was last accepted) and classifies every node, check, assumption
and feature as

* **changed**: its own content differs from the baseline (or it is new);
* **invalidated**: it depends on what changed, through
  - *meaning*: its text uses a term the change removed (a word dropped from a changed
    statement, e.g. "shelf" when "Support a shelf on a wall" became "Support a fishing rod on
    a wall");
  - *supports*: an assumption that supports an invalidated check;
  - *source*: a check whose `source` names an invalidated check (A.P.c4 ← R.c4);
  - *nesting*: a node under an invalidated node (B.1 under B), and a node whose own check is
    invalidated;
  - *features*: a node whose features use a feature that serves an invalidated node;
* **survives**: everything else.

A changed node does **not** invalidate its children by nesting alone (A "Wall mounting"
survives the root's change): only the terms the change removed travel down the tree.  This is
a deterministic, lexical first cut (no synonyms: "books" does not mean "shelf"); every
classification lists its reasons, the model receives the report as structured data and can
argue with it in its purpose proposal.  Features that serve a changed or invalidated node are
invalidated (their realization needs a new look), but a feature invalidated only through a
*changed* node does not invalidate the features that use it, or every feature built on the
root's skeleton would be.
"""
from __future__ import annotations

import re

from .review import CONTENT_KEYS, node_content, plain_nodes

STOPWORDS = frozenset("""
a an the and or of on in at to for from by with without into onto over under up down out off is are be been
being it its this that these those as per via than then so such each every any all no not nor can could should
must may might will would shall do does did done has have had very more most less least only own same other
both either neither one two three first second ≥ ≤ mm kg deg n x y z""".split())
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]+")


def stem(w: str) -> str:
    w = w.lower().strip("-")
    for suf, rep in (("ies", "y"), ("ves", "f"), ("sses", "ss"), ("es", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and not w.endswith("ss"):
            return w[: -len(suf)] + rep
    return w


def terms(text: str) -> set:
    return {stem(m.group(0)) for m in _WORD.finditer(str(text or "")) if m.group(0).lower() not in STOPWORDS
            and len(m.group(0)) >= 3}


def _item_text(x: dict) -> str:
    return " ".join(str(x.get(k) or "") for k in ("statement", "grounded_as", "rationale"))


def _node_terms(content: dict) -> set:
    return terms(content.get("statement", ""))


def impact(intent_plain: dict, reviewed: dict, features: list | None = None) -> dict:
    """The stage-1 impact report.

    intent_plain: the current intent document (plain); reviewed: the review record's
    `reviewed` map {node id: {hash, content}}; features: [{id, serves: [node ids], uses:
    [feature ids]}] from a build (optional)."""
    nodes = plain_nodes(intent_plain)
    parents: dict = {}

    def walk(lst, parent):
        for n in lst or []:
            parents[n["id"]] = parent
            walk(n.get("children"), n["id"])
    walk((intent_plain or {}).get("intents"), None)

    removed_terms, added_terms = set(), set()
    node_cls, check_cls, asm_cls, feat_cls = {}, {}, {}, {}
    changes = []
    checks, asms = {}, {}
    for nid, n in nodes.items():
        cur = node_content(n)
        for c in cur["checks"]:
            checks[c["id"]] = {**c, "node": nid}
        for a in cur["assumptions"]:
            asms[a["id"]] = {**a, "node": nid}
        rec = (reviewed or {}).get(nid)
        if rec is None:
            node_cls[nid] = {"class": "changed", "reasons": ["new: not in the review baseline"], "new": True}
            changes.append({"id": nid, "new": True, "fields": list(CONTENT_KEYS), "before": None, "after": cur})
            continue
        before = rec.get("content") or {}
        fields = [k for k in CONTENT_KEYS if before.get(k, [] if k != "statement" else "") != cur.get(k)]
        if fields:
            node_cls[nid] = {"class": "changed", "reasons": [f"{', '.join(fields)} changed since reviewed"]}
            changes.append({"id": nid, "new": False, "fields": fields, "before": before, "after": cur})
            if "statement" in fields:
                removed_terms |= terms(before.get("statement", "")) - terms(cur["statement"])
                added_terms |= terms(cur["statement"]) - terms(before.get("statement", ""))
            for key in ("checks", "assumptions"):
                if key not in fields:
                    continue
                old = {x.get("id"): x for x in before.get(key) or []}
                for x in cur[key]:
                    o = old.get(x["id"])
                    if o != x:
                        (check_cls if key == "checks" else asm_cls)[x["id"]] = {
                            "class": "changed", "reasons": ["new since reviewed" if o is None else "edited since reviewed"]}
                        if o is not None:
                            removed_terms |= terms(_item_text(o)) - terms(_item_text(x))
    removed_nodes = sorted(set(reviewed or {}) - set(nodes))
    for nid in removed_nodes:
        removed_terms |= terms(((reviewed or {})[nid].get("content") or {}).get("statement", ""))
    removed_terms -= added_terms

    def mentions(text: str) -> list:
        return sorted(terms(text) & removed_terms)

    # 1. meaning: items whose text uses a removed term
    for nid, n in nodes.items():
        if nid in node_cls:
            continue
        hit = mentions(n.get("statement", ""))
        if hit:
            node_cls[nid] = {"class": "invalidated", "reasons": [f"its statement uses '{', '.join(hit)}', which the "
                                                                 "change removed"]}
    for cid, c in checks.items():
        if cid in check_cls:
            continue
        hit = mentions(_item_text(c))
        if hit:
            check_cls[cid] = {"class": "invalidated", "reasons": [f"uses '{', '.join(hit)}', which the change removed"]}
    for aid, a in asms.items():
        if aid in asm_cls:
            continue
        hit = mentions(_item_text(a))
        if hit:
            asm_cls[aid] = {"class": "invalidated", "reasons": [f"uses '{', '.join(hit)}', which the change removed"]}

    serves = {f["id"]: list(f.get("serves") or []) for f in features or []}
    uses = {f["id"]: list(f.get("uses") or []) for f in features or []}

    def bad(cls: dict, k) -> bool:
        return cls.get(k, {}).get("class") in ("changed", "invalidated")

    def invalid(cls: dict, k) -> bool:
        return cls.get(k, {}).get("class") == "invalidated"

    # 2. propagate to a fixpoint: source, supports, nesting, own checks, features
    for _ in range(64):
        moved = False

        def mark(cls, k, reason):
            nonlocal moved
            if k not in cls:
                cls[k] = {"class": "invalidated", "reasons": [reason]}
                moved = True
            elif cls[k]["class"] == "invalidated" and reason not in cls[k]["reasons"]:
                cls[k]["reasons"].append(reason)

        for cid, c in checks.items():
            src = str(c.get("source") or "")
            for other in re.findall(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", src):
                if other in checks and bad(check_cls, other):
                    mark(check_cls, cid, f"its source {other} is {check_cls[other]['class']}")
        for aid, a in asms.items():
            for s in a.get("supports") or []:
                if s in checks and bad(check_cls, s):
                    mark(asm_cls, aid, f"supports {s}, which is {check_cls[s]['class']}")
        for nid in nodes:
            p = parents.get(nid)
            if p is not None and invalid(node_cls, p):
                mark(node_cls, nid, f"nested under {p}, which is invalidated")
            if node_cls.get(nid, {}).get("class") != "changed":
                for c in node_content(nodes[nid])["checks"]:
                    if invalid(check_cls, c["id"]):
                        mark(node_cls, nid, f"its check {c['id']} is invalidated")
        # features that serve changed / invalidated nodes
        for fid, sv in serves.items():
            why = [n for n in sv if bad(node_cls, n)]
            if why and fid not in feat_cls:
                feat_cls[fid] = {"class": "invalidated",
                                 "reasons": [f"serves {', '.join(why)} ({', '.join(node_cls[n]['class'] for n in why)})"],
                                 "via_invalidated": any(invalid(node_cls, n) for n in why)}
                moved = True
            elif why and any(invalid(node_cls, n) for n in why) and not feat_cls[fid].get("via_invalidated"):
                feat_cls[fid]["via_invalidated"] = True
                moved = True
        for fid, sv in serves.items():
            for g in uses.get(fid, []):
                if feat_cls.get(g, {}).get("via_invalidated"):
                    for n in sv:
                        if node_cls.get(n, {}).get("class") != "changed":
                            mark(node_cls, n, f"its feature {fid} uses {g}, which serves an invalidated purpose")
        if not moved:
            break

    def fill(cls, ids):
        for k in ids:
            cls.setdefault(k, {"class": "survives", "reasons": []})

    fill(node_cls, nodes)
    fill(check_cls, checks)
    fill(asm_cls, asms)
    fill(feat_cls, serves)
    for k, v in check_cls.items():
        v["node"] = checks[k]["node"]
        v["statement"] = checks[k].get("statement", "")
    for k, v in asm_cls.items():
        v["node"] = asms[k]["node"]
        v["statement"] = asms[k].get("statement", "")
    for k, v in node_cls.items():
        v["statement"] = nodes[k].get("statement", "")
        v["parent"] = parents.get(k)
        v["features"] = [f for f, sv in serves.items() if k in sv]
    for v in feat_cls.values():
        v.pop("via_invalidated", None)

    def count(cls):
        out = {"changed": 0, "invalidated": 0, "survives": 0}
        for v in cls.values():
            out[v["class"]] += 1
        return out

    return {"terms": {"removed": sorted(removed_terms), "added": sorted(added_terms)},
            "changes": changes, "removed_nodes": removed_nodes,
            "nodes": node_cls, "checks": check_cls, "assumptions": asm_cls, "features": feat_cls,
            "summary": {"nodes": count(node_cls), "checks": count(check_cls), "assumptions": count(asm_cls),
                        "features": count(feat_cls)},
            "any_change": bool(changes or removed_nodes),
            "method": "lexical: removed terms travel through text, supports, source, nesting and features; "
                      "no synonyms (docs/purpose-loop.md §3 step 1; NOTES DECISIONS #73)"}


def impact_for(design_path: str, intent_plain: dict | None = None, summary: dict | None = None) -> dict:
    """Impact for a design on disk: its intent file against its review record."""
    from . import intent_store
    from .review import ReviewRecord, path_for
    if intent_plain is None:
        intent_plain = intent_store.load(intent_store.path_for(design_path)).to_plain()
    rec = ReviewRecord.load(path_for(design_path))
    feats = None
    if summary is not None:
        feats = [{"id": f["id"], "serves": f.get("serves", []), "uses": f.get("uses", [])}
                 for f in summary.get("features", [])]
    out = impact(intent_plain, rec.reviewed, feats)
    out["baseline"] = {"file": rec.path, "exists": rec.exists, "reviewed_nodes": sorted(rec.reviewed)}
    return out
