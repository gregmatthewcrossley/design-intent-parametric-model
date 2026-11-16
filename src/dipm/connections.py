"""Intent <-> feature <-> parameter connections (docs/gui.md §2 items 4 and 9).

Derived, read-only views of a design and one of its builds:

* `param_dependencies(feature)`: the declared parameters a feature's lazy arguments read,
  found by walking its expression trees (ParamRef, BinOp, Func, placements, profiles,
  segments built from closures ...).  Static: no build needed.
* `intent_tree(design, build)`: the intent tree derived from intent tags.  Node ids are
  dotted (`A.P.1` -> parent `A.P` -> `A`); the conventional root `R` (architecture §8)
  parents every other top-level id.  Missing intermediate nodes are created.  Labels come
  from `Design.label_intent` if given, else from tag notes, else from the intent words.
  Status = the worst status of the features beneath (failed > warn > ok; not built).
* `diagnostics(...)`: features with no intent, intents with no feature, features serving
  several unrelated intents (coupling), and dependencies between features of unrelated
  intents (possible false coupling, architecture §5.1).

Uses (feature -> feature) come from `Build.uses` (resolved references plus geometry read
without a reference, NOTES DECISIONS #33).
"""
from __future__ import annotations

import dataclasses
import types
from dataclasses import dataclass, field

from .expr import ParamRef

ROOT = "R"
STATUS_RANK = {"ok": 0, "not_built": 1, "warn": 2, "fail": 3}


# ---------------------------------------------------------------- parameter dependencies

def param_dependencies(obj) -> list:
    """Sorted names of the parameters an object's lazy expressions read (deep walk)."""
    found: set = set()
    _walk(obj, found, set())
    return sorted(found)


def _walk(x, found: set, seen: set) -> None:
    if x is None or isinstance(x, (str, bytes, int, float, bool, complex)):
        return
    if id(x) in seen:
        return
    seen.add(id(x))
    if isinstance(x, ParamRef):
        found.add(x.name)
        return
    if isinstance(x, dict):
        for v in x.values():
            _walk(v, found, seen)
        return
    if isinstance(x, (list, tuple, set, frozenset)):
        for v in x:
            _walk(v, found, seen)
        return
    if isinstance(x, (types.FunctionType, types.MethodType)):
        fn = x.__func__ if isinstance(x, types.MethodType) else x
        if isinstance(x, types.MethodType):
            _walk(x.__self__, found, seen)
        for cell in fn.__closure__ or ():
            try:
                _walk(cell.cell_contents, found, seen)
            except ValueError:      # empty cell
                pass
        for d in fn.__defaults__ or ():
            _walk(d, found, seen)
        return
    if isinstance(x, (types.BuiltinFunctionType, type, types.ModuleType)):
        return
    if dataclasses.is_dataclass(x):
        for f in dataclasses.fields(x):
            if f.name in ("id", "tags"):
                continue
            _walk(getattr(x, f.name, None), found, seen)
        return
    mod = type(x).__module__ or ""
    if mod.startswith("dipm") and hasattr(x, "__dict__"):
        for v in vars(x).values():
            _walk(v, found, seen)


def feature_params(design) -> dict:
    """feature id -> sorted parameter names its own arguments read (direct dependencies)."""
    return {f.id: param_dependencies(f) for f in design.features}


def params_through_uses(direct: dict, uses: dict) -> dict:
    """feature id -> parameters it depends on directly or through the features it uses."""
    def go(fid):
        out, seen, stack = set(), set(), [fid]
        while stack:
            f = stack.pop()
            if f in seen:
                continue
            seen.add(f)
            out |= set(direct.get(f, ()))
            stack.extend(uses.get(f, ()))
        return out

    return {fid: sorted(go(fid)) for fid in direct}


# ---------------------------------------------------------------- intent tree

def parent_of(node: str) -> str | None:
    if "." in node:
        return node.rsplit(".", 1)[0]
    return None if node == ROOT else ROOT


def ancestors(node: str) -> list:
    out, p = [], parent_of(node)
    while p is not None:
        out.append(p)
        p = parent_of(p)
    return out


def related(a: str, b: str) -> bool:
    """True if one node is the other or an ancestor of it."""
    return a == b or a in ancestors(b) or b in ancestors(a)


def _sort_key(node: str) -> tuple:
    """Siblings: named sub-intents before numbered ones (A.P before A.3), then by name/number."""
    return tuple((1, int(p), "") if p.isdigit() else (0, 0, p) for p in node.split("."))


@dataclass
class IntentNode:
    id: str
    label: str
    parent: str | None
    children: list = field(default_factory=list)
    words: list = field(default_factory=list)        # intent words tagged at this node
    notes: list = field(default_factory=list)        # tag notes at this node
    features: list = field(default_factory=list)     # features tagged *at* this node (feature level)
    instances: list = field(default_factory=list)    # (feature, k) instance tags at this node
    realized_by: list = field(default_factory=list)  # features shown as callouts (most specific node)
    status: str = "ok"
    implicit: bool = False                            # created only as an ancestor of a tagged node

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def feature_nodes(feature) -> list:
    """Intent nodes a feature's feature-level tags name (declaration order, deduped)."""
    return list(dict.fromkeys(t.node for t in feature.tags))


def minimal_nodes(nodes) -> list:
    """Drop nodes that are ancestors of another node in the list (A.P.holes: [A.P, A] -> [A.P])."""
    return [n for n in nodes if not any(m != n and n in ancestors(m) for m in nodes)]


def feature_status(rec, slot_ids_with_attention: set) -> str:
    if rec is None:
        return "not_built"
    if not rec.ok:
        return "fail"
    return "warn" if rec.id in slot_ids_with_attention else "ok"


def intent_tree(design, build=None, attention: set | None = None) -> dict:
    """{root, nodes: {id: IntentNode}} derived from the design's intent tags (and a build's
    instance tags and statuses).  `attention`: feature ids with a pending question/notice."""
    attention = attention or set()
    recs = {r.id: r for r in build.records} if build is not None else {}
    nodes: dict = {}

    def get(nid: str, implicit: bool) -> IntentNode:
        if nid not in nodes:
            nodes[nid] = IntentNode(nid, "", parent_of(nid), implicit=implicit)
            p = parent_of(nid)
            if p is not None:
                get(p, True)
        elif not implicit:
            nodes[nid].implicit = False
        return nodes[nid]

    for f in design.features:
        for t in f.tags:
            n = get(t.node, False)
            if t.word not in n.words:
                n.words.append(t.word)
            if t.note and t.note not in n.notes:
                n.notes.append(t.note)
            if f.id not in n.features:
                n.features.append(f.id)
        for n_id in minimal_nodes(feature_nodes(f)):
            nodes[n_id].realized_by.append(f.id)
        inst = None
        if build is not None and f.id in recs:
            inst = recs[f.id].instance_tags
        elif getattr(f, "instance_tags", None):
            inst = {str(k): ts for k, ts in enumerate(f.instance_tags)}
        for k, ts in sorted((inst or {}).items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else kv[0]):
            for t in ts:
                n = get(t.node, False)
                if t.word not in n.words:
                    n.words.append(t.word)
                if t.note and t.note not in n.notes:
                    n.notes.append(t.note)
                n.instances.append([f.id, k])
    for nid, label in getattr(design, "intent_labels", {}).items():
        get(nid, False)
    if nodes and ROOT not in nodes:
        get(ROOT, True)
    labels = getattr(design, "intent_labels", {})
    for n in nodes.values():
        n.label = labels.get(n.id) or (n.notes[0] if n.notes else
                                       (", ".join(w.replace("_", " ") for w in n.words) if n.words else ""))
    for n in nodes.values():
        if n.parent is not None and n.parent in nodes:
            nodes[n.parent].children.append(n.id)
    for n in nodes.values():
        n.children.sort(key=_sort_key)
    # status: worst of the features at or beneath each node
    fstat = {f.id: feature_status(recs.get(f.id) if build is not None else None, attention)
             if build is not None else "not_built" for f in design.features}

    def beneath(nid: str) -> set:
        out = set(nodes[nid].features) | {fid for fid, _ in nodes[nid].instances}
        for c in nodes[nid].children:
            out |= beneath(c)
        return out

    for n in nodes.values():
        fs = beneath(n.id)
        n.status = max((fstat[f] for f in fs), key=STATUS_RANK.get, default="ok") if fs else "ok"
    order = []

    def walk(nid):
        order.append(nid)
        for c in nodes[nid].children:
            walk(c)

    roots = sorted((n.id for n in nodes.values() if n.parent is None or n.parent not in nodes), key=_sort_key)
    for r in roots:
        walk(r)
    return {"roots": roots, "order": order, "nodes": {nid: nodes[nid] for nid in order}}


# ---------------------------------------------------------------- diagnostics

def diagnostics(design, tree: dict, uses: dict) -> dict:
    """Connection diagnostics (docs/gui.md §2 item 9)."""
    nodes = tree["nodes"]
    no_intent = [f.id for f in design.features if not f.tags]
    no_feature = []
    for nid, n in nodes.items():
        sub = [nid] + [m for m in nodes if nid in ancestors(m)]
        if not any(nodes[m].features or nodes[m].instances for m in sub):
            no_feature.append(nid)
    multi = []
    for f in design.features:
        mins = minimal_nodes(feature_nodes(f))
        if len(mins) > 1:
            multi.append({"feature": f.id, "nodes": mins})
    fnodes = {f.id: minimal_nodes(feature_nodes(f)) for f in design.features}
    cross = []
    for fid, gs in uses.items():
        for g in gs:
            a, b = fnodes.get(fid, []), fnodes.get(g, [])
            if a and b and not any(related(x, y) for x in a for y in b):
                cross.append({"from": fid, "to": g, "from_nodes": a, "to_nodes": b})
    return {"no_intent": no_intent, "no_feature": no_feature, "multi_intent": multi, "cross_intent": cross}
