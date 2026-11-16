"""The intent file `<design>.intent.yaml`: load, validate, edit, save (docs/gui.md §7.2).

This is the **only** module that knows the on-disk format (docs/user-experience.md §1.1:
schema-validated YAML, canonical form, comments preserved, one load/save module so a KDL swap
stays contained).  Everything else sees `IntentDoc` plus plain data (`to_plain()`), and
edits go through `apply_ops`.

Format (illustrative; the schema below is authoritative):

    design: shelf_bracket
    context: {process: fdm_printing, material: PETG}
    intents:
      - id: R
        statement: Support a shelf on a wall
        checks:
          - {id: R.c1, kind: analysis, source: world, statement: "..."}
        assumptions:
          - {id: R.a1, statement: "...", made_by: model, status: proposed}
        children:
          - id: A
            statement: Wall mounting

Hierarchy is stored by **nesting**, never derived from the dotted ids: ids are stable labels
and are not rewritten when a node moves (gui.md §7.4).

Canonical form: ruamel.yaml round-trip (comments, quote style and flow/block style of
existing nodes are kept), 2-space mappings, sequences indented 4 with the dash at 2, no line
wrapping, and a stable key order per object (`KEY_ORDER`).  Loading canonical text and saving
it again is byte-identical.

Concurrency: `save(..., base_hash=h)` refuses (`IntentConflict`) unless the file on disk still
has hash `h`; writes are atomic (`fileio.atomic_write`).
"""
from __future__ import annotations

import difflib
import io
import os
import re
import threading
from dataclasses import dataclass

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import MarkedYAMLError, YAMLError
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString

from .fileio import atomic_write, file_sha256, read_text, sha256_text

SUFFIX = ".intent.yaml"

# ---------------------------------------------------------------- schema

CHECK_KINDS = ("relation", "rule", "analysis", "learned score", "live judgment")   # architecture §4.1
PRIORITIES = ("must", "should", "nice to have")
MADE_BY = ("model", "user", "pack default", "author")                               # architecture §4.8
ASSUMPTION_STATUS = ("proposed", "accepted", "challenged", "replaced")
SENSITIVITY = ("high", "medium", "low", "insensitive", "forced", "none", "unknown")

ID_RE = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$")

# field -> (required, type, enum)   type: "str" | "list[str]" | "map" | "list[node]" ...
COMPONENT_SHAPES = ("cylinder", "box")

SCHEMA = {
    "top": {"design": (True, "str", None), "context": (False, "map[str]", None),
            # iteration 4: component envelopes the design must fit (components.py)
            "components": (False, "list[component]", None),
            "intents": (True, "list[node]", None)},
    "node": {"id": (True, "id", None), "statement": (True, "str", None), "receives": (False, "list[str]", None),
             "exports": (False, "list[str]", None), "checks": (False, "list[check]", None),
             "assumptions": (False, "list[assumption]", None), "children": (False, "list[node]", None)},
    "check": {"id": (True, "id", None), "kind": (False, "str", CHECK_KINDS), "source": (False, "str", None),
              "priority": (False, "str", PRIORITIES), "statement": (True, "str", None),
              "grounded_as": (False, "str", None), "origin": (False, "map[str]", None), "expr": (False, "str", None),
              # iteration 4: a computable form from the check vocabulary (vocabulary.py), or
              # {form: descriptive, reason: ...}; its values are text like everything else
              "binding": (False, "map[str]", None)},
    "assumption": {"id": (True, "id", None), "statement": (True, "str", None), "made_by": (False, "str", MADE_BY),
                   "rationale": (False, "str", None), "supports": (False, "list[str]", None),
                   "sensitivity": (False, "str", SENSITIVITY), "status": (False, "str", ASSUMPTION_STATUS),
                   # iteration 3: a machine-readable assumption (e.g. about: print_orientation, value: "0,0,-1")
                   "about": (False, "str", None), "value": (False, "str", None)},
    "component": {"id": (True, "id", None), "statement": (False, "str", None),
                  "shape": (False, "str", COMPONENT_SHAPES), "pack": (False, "str", None),
                  "diameter": (False, "str", None), "length": (False, "str", None), "size": (False, "str", None),
                  "mass": (False, "str", None), "source": (False, "str", None),
                  "made_by": (False, "str", MADE_BY), "status": (False, "str", ASSUMPTION_STATUS)},
}
KEY_ORDER = {k: list(v) for k, v in SCHEMA.items()}


class IntentSchemaError(ValueError):
    """The intent file is not valid YAML or does not match the schema.  `errors` holds one
    readable line per problem, each starting with where it is."""

    def __init__(self, errors: list, path: str | None = None):
        self.errors = list(errors)
        self.path = path
        where = f"{os.path.basename(path)}: " if path else ""
        super().__init__(where + ("; ".join(self.errors) if len(self.errors) <= 3 else
                                  "; ".join(self.errors[:3]) + f"; … ({len(self.errors)} problems)"))


class IntentConflict(RuntimeError):
    """A write was based on content that is no longer on disk (optimistic concurrency)."""

    def __init__(self, path: str, base_hash: str | None, current_hash: str | None):
        self.path, self.base_hash, self.current_hash = path, base_hash, current_hash
        super().__init__(f"{os.path.basename(path)} changed on disk (based on {str(base_hash)[:12]}, "
                         f"now {str(current_hash)[:12]})")


class IntentOpError(ValueError):
    """An edit operation cannot be applied (unknown id, moving a node into itself …)."""


def _type_name(x) -> str:
    if isinstance(x, bool):
        return "a boolean"
    if isinstance(x, (int, float)):
        return "a number"
    if x is None:
        return "empty (null)"
    if isinstance(x, dict):
        return "a mapping"
    if isinstance(x, list):
        return "a list"
    return type(x).__name__


def _suggest(word: str, options) -> str:
    m = difflib.get_close_matches(str(word), list(options), n=1, cutoff=0.6)
    return f" (did you mean '{m[0]}'?)" if m else ""


def validate(data) -> list:
    """Readable schema errors for loaded data (empty list = valid)."""
    errs: list = []
    if not isinstance(data, dict):
        return [f"the file must be a mapping with keys {', '.join(KEY_ORDER['top'])}; got {_type_name(data)}"]
    seen_ids: dict = {}

    def check_obj(obj, kind: str, where: str):
        if not isinstance(obj, dict):
            errs.append(f"{where}: must be a mapping; got {_type_name(obj)}")
            return
        spec = SCHEMA[kind]
        for k in obj:
            if k not in spec:
                errs.append(f"{where}: unknown key '{k}'{_suggest(k, spec)}; allowed: {', '.join(spec)}")
        for k, (req, typ, enum) in spec.items():
            if k not in obj:
                if req:
                    errs.append(f"{where}: missing required key '{k}'")
                continue
            v = obj[k]
            at = f"{where}.{k}"
            if typ in ("str", "id"):
                if not isinstance(v, str):
                    hint = " (quote it to keep it text)" if isinstance(v, (bool, int, float)) else ""
                    errs.append(f"{at}: must be text; got {_type_name(v)}{hint}")
                    continue
                if typ == "id":
                    if not ID_RE.match(v):
                        errs.append(f"{at}: '{v}' is not a valid id (letters, digits, _ separated by dots)")
                    elif v in seen_ids:
                        errs.append(f"{at}: id '{v}' is used twice (also at {seen_ids[v]})")
                    else:
                        seen_ids[v] = where
                if typ == "str" and not v.strip() and k == "statement":
                    errs.append(f"{at}: must not be empty")
                if enum and v not in enum:
                    errs.append(f"{at}: must be one of {', '.join(enum)}; got '{v}'{_suggest(v, enum)}")
            elif typ == "map[str]":
                if not isinstance(v, dict):
                    errs.append(f"{at}: must be a mapping; got {_type_name(v)}")
                    continue
                for kk, vv in v.items():
                    if not isinstance(vv, str):
                        errs.append(f"{at}.{kk}: must be text; got {_type_name(vv)} (quote it)")
            elif typ == "list[str]":
                if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                    errs.append(f"{at}: must be a list of text")
            elif typ.startswith("list["):
                sub = typ[5:-1]
                if not isinstance(v, list):
                    errs.append(f"{at}: must be a list; got {_type_name(v)}")
                    continue
                for i, item in enumerate(v):
                    label = f"{at}[{i}]"
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        label += f" ({item['id']})"
                    check_obj(item, sub, label)

    check_obj(data, "top", "file")
    if isinstance(data.get("intents"), list) and not data["intents"]:
        errs.append("file.intents: must hold at least one intent (the root)")
    return errs


# ---------------------------------------------------------------- YAML engine

def _yaml() -> YAML:
    y = YAML(typ="rt")
    y.indent(mapping=2, sequence=4, offset=2)
    y.width = 4096
    y.preserve_quotes = True
    y.allow_duplicate_keys = False
    return y


_YAML_LOCK = threading.Lock()     # a ruamel YAML instance is not thread-safe


def _canonicalize(data) -> None:
    """Stable key order (KEY_ORDER) for the top level, every node, check and assumption."""
    def order(m, kind):
        if not isinstance(m, CommentedMap):
            return
        for k in KEY_ORDER[kind]:
            if k in m:
                m.move_to_end(k)

    order(data, "top")
    for c in (data.get("components") or []) if isinstance(data, dict) else []:
        order(c, "component")
    for ref in iter_nodes_raw(data):
        n = ref[0]
        order(n, "node")
        for c in n.get("checks") or []:
            order(c, "check")
        for a in n.get("assumptions") or []:
            order(a, "assumption")


@dataclass
class IntentDoc:
    """A loaded intent file.  `data` is format-specific (ruamel round-trip objects); use
    `to_plain()`, `find()`, `nodes()` and `apply_ops()` instead of touching it directly."""
    data: CommentedMap
    path: str | None
    hash: str            # sha256 of the text it was loaded from / last saved as

    @property
    def design(self) -> str:
        return str(self.data.get("design", ""))

    def nodes(self) -> list:
        """[(id, parent id | None, depth)] in file (pre-)order."""
        return [(str(n["id"]), (str(p["id"]) if p is not None else None), depth)
                for n, p, _sib, _i, depth in iter_nodes_raw(self.data)]

    def ids(self) -> set:
        """Every id in the file: nodes, checks, assumptions and components."""
        out = {str(c.get("id")) for c in (self.data.get("components") or []) if isinstance(c, dict)}
        for n, *_ in iter_nodes_raw(self.data):
            out.add(str(n["id"]))
            for c in (n.get("checks") or []):
                out.add(str(c.get("id")))
            for a in (n.get("assumptions") or []):
                out.add(str(a.get("id")))
        return out

    def node_ids(self) -> list:
        return [i for i, _p, _d in self.nodes()]

    def find(self, node_id: str):
        for n, p, sib, i, depth in iter_nodes_raw(self.data):
            if str(n["id"]) == node_id:
                return n, p, sib, i
        raise IntentOpError(f"no intent node '{node_id}' in the intent file")

    def node_plain(self, node_id: str) -> dict:
        return to_plain(self.find(node_id)[0])

    def to_plain(self) -> dict:
        return to_plain(self.data)


def iter_nodes_raw(data):
    """Yield (node, parent node | None, sibling list, index, depth) in pre-order."""
    def walk(lst, parent, depth):
        if not isinstance(lst, list):
            return
        for i, n in enumerate(lst):
            if not isinstance(n, dict):
                continue
            yield n, parent, lst, i, depth
            yield from walk(n.get("children"), n, depth + 1)

    yield from walk(data.get("intents") if isinstance(data, dict) else None, None, 0)


def to_plain(x):
    """ruamel objects -> plain dict / list / str (JSON-ready)."""
    if isinstance(x, dict):
        return {str(k): to_plain(v) for k, v in x.items()}
    if isinstance(x, list):
        return [to_plain(v) for v in x]
    if isinstance(x, str):
        return str(x)
    return x


def loads(text: str, path: str | None = None) -> IntentDoc:
    """Parse and validate.  Raises IntentSchemaError with readable, located messages."""
    try:
        with _YAML_LOCK:
            data = _yaml().load(text)
    except MarkedYAMLError as e:
        mark = e.problem_mark
        loc = f"line {mark.line + 1}, column {mark.column + 1}: " if mark is not None else ""
        raise IntentSchemaError([f"{loc}{e.problem or e.context or 'invalid YAML'}"], path) from None
    except YAMLError as e:
        raise IntentSchemaError([f"invalid YAML: {e}"], path) from None
    errs = validate(data)
    if errs:
        raise IntentSchemaError(errs, path)
    return IntentDoc(data, path, sha256_text(text))


def load(path: str) -> IntentDoc:
    return loads(read_text(path), os.path.abspath(path))


def dumps(doc: IntentDoc) -> str:
    """Canonical text (key order, indentation); comments and scalar styles preserved."""
    _canonicalize(doc.data)
    buf = io.StringIO()
    with _YAML_LOCK:
        _yaml().dump(doc.data, buf)
    return buf.getvalue()


def canonical(text: str) -> str:
    return dumps(loads(text))


def save(doc: IntentDoc, path: str | None = None, base_hash: str | None = None) -> str:
    """Write canonically and atomically.  With `base_hash`, refuse (IntentConflict) unless the
    file on disk still has that hash (a missing file counts as hash None).  Returns the new hash."""
    path = os.path.abspath(path or doc.path or "")
    if not path:
        raise ValueError("no path to save the intent file to")
    errs = validate(doc.data)
    if errs:
        raise IntentSchemaError(errs, path)
    text = dumps(doc)
    with _SAVE_LOCK:
        if base_hash is not None:
            cur = file_sha256(path)
            if cur != base_hash:
                raise IntentConflict(path, base_hash, cur)
        atomic_write(path, text)
    doc.path, doc.hash = path, sha256_text(text)
    return doc.hash


_SAVE_LOCK = threading.Lock()


def path_for(design_file: str) -> str:
    """`examples/shelf_bracket.py` -> `examples/shelf_bracket.intent.yaml`."""
    return os.path.splitext(os.path.abspath(design_file))[0] + SUFFIX


# ---------------------------------------------------------------- edit operations

def _like(old, new: str):
    """Keep the quote style of the value being replaced (minimal diffs)."""
    if isinstance(old, DoubleQuotedScalarString):
        return DoubleQuotedScalarString(new)
    if isinstance(old, SingleQuotedScalarString):
        return SingleQuotedScalarString(new)
    return new


def _suffix_num(i: str, prefix: str) -> int | None:
    if not i.startswith(prefix):
        return None
    rest = i[len(prefix):]
    return int(rest) if rest.isdigit() else None


def next_child_id(doc: IntentDoc, parent_id: str, taken=()) -> str:
    """Next free dotted id under `parent_id`: `B` (with B.1) -> `B.2`.  Children of a root get
    the next unused capital letter (R -> D after A, B, C), following the bracket's convention.
    `taken` adds ids used elsewhere (e.g. in the DSL) so a new node never captures them."""
    used = doc.ids() | set(taken)
    _n, p, _s, _i = doc.find(parent_id)
    if p is None:
        for c in "ABCDEFGHIJKLMNOPQSTUVWXYZ":   # skip R, the conventional root
            if c not in used:
                return c
    nums = [x for x in (_suffix_num(i, parent_id + ".") for i in used) if x is not None]
    return f"{parent_id}.{max(nums, default=0) + 1}"


def _next_sub_id(doc: IntentDoc, node_id: str, letter: str, taken=()) -> str:
    used = doc.ids() | set(taken)
    nums = [x for x in (_suffix_num(i, f"{node_id}.{letter}") for i in used) if x is not None]
    return f"{node_id}.{letter}{max(nums, default=0) + 1}"


def _set_fields(m: CommentedMap, fields: dict, kind: str) -> None:
    spec = SCHEMA[kind]
    for k, v in fields.items():
        if k == "id":
            raise IntentOpError(f"cannot change a {kind}'s id here")
        if k not in spec:
            raise IntentOpError(f"unknown {kind} field '{k}'{_suggest(k, spec)}")
        if v is None or v == "" or v == []:
            if spec[k][0]:
                raise IntentOpError(f"{kind} field '{k}' is required")
            m.pop(k, None)
        else:
            m[k] = _like(m.get(k), v) if isinstance(v, str) else v


def _find_sub(node, key: str, sub_id: str, kind: str):
    lst = node.get(key) or []
    for i, x in enumerate(lst):
        if str(x.get("id")) == sub_id:
            return lst, i
    raise IntentOpError(f"no {kind} '{sub_id}' on intent '{node['id']}'")


def _append_like_siblings(lst, item: CommentedMap) -> None:
    """Append, matching the siblings' style: a list of one-line flow mappings stays one-line."""
    if len(lst) and isinstance(lst[0], CommentedMap) and lst[0].fa.flow_style():
        item.fa.set_flow_style()
    lst.append(item)


def _drop_if_empty(node, key: str) -> None:
    if key in node and not node[key]:
        del node[key]


def apply_op(doc: IntentDoc, op: dict, taken=()) -> dict:
    """Apply one edit to `doc` in memory.  Returns details (e.g. the id a new node got).

    ops: edit_statement {id, statement} · add_child {parent, statement?, id?} · delete {id} ·
    move {id, parent, index?} · add_check {id, check} · edit_check {id, check_id, fields} ·
    remove_check {id, check_id} · edit_assumption {id, assumption_id, fields} ·
    add_assumption {id, assumption} · set_context {fields} · set_binding {id, check_id, binding?, status?} ·
    add_component {component} · edit_component {component_id, fields} · remove_component {component_id}"""
    kind = op.get("op")
    if kind == "set_context":
        fields = {str(k): str(v) for k, v in (op.get("fields") or {}).items() if v not in (None, "")}
        if not fields:
            raise IntentOpError("set_context needs at least one field")
        ctx = doc.data.get("context")
        if ctx is None:
            ctx = CommentedMap()
            ctx.fa.set_flow_style()
            # context goes right after `design:` (KEY_ORDER top: design, context, intents)
            doc.data.insert(1 if "design" in doc.data else 0, "context", ctx)
        for k, v in fields.items():
            ctx[k] = _like(ctx.get(k), v)
        return {"context": dict(ctx)}
    if kind == "edit_statement":
        n, *_ = doc.find(op["id"])
        st = str(op.get("statement", "")).strip()
        if not st:
            raise IntentOpError("a statement must not be empty")
        n["statement"] = _like(n.get("statement"), st)
        return {"id": op["id"]}
    if kind == "add_child":
        parent, *_ = doc.find(op["parent"])
        nid = op.get("id") or next_child_id(doc, op["parent"], taken)
        if nid in doc.ids():
            raise IntentOpError(f"id '{nid}' is already used")
        node = CommentedMap()
        node["id"] = nid
        node["statement"] = str(op.get("statement") or "New intent").strip()
        if "children" not in parent or parent["children"] is None:
            parent["children"] = CommentedSeq()
        parent["children"].append(node)
        return {"id": nid}
    if kind == "delete":
        n, p, sib, i = doc.find(op["id"])
        if p is None and len(doc.data["intents"]) == 1:
            raise IntentOpError("cannot delete the root intent")
        removed = [str(x["id"]) for x, *_ in iter_nodes_raw({"intents": [n]})]
        sib.pop(i)
        if p is not None:
            _drop_if_empty(p, "children")
        return {"id": op["id"], "removed": removed}
    if kind == "move":
        n, p, sib, i = doc.find(op["id"])
        target, *_ = doc.find(op["parent"])
        inside = {str(x["id"]) for x, *_ in iter_nodes_raw({"intents": [n]})}
        if str(target["id"]) in inside:
            raise IntentOpError(f"cannot move '{op['id']}' into itself or its own subtree")
        if p is None:
            raise IntentOpError("cannot move a root intent")
        sib.pop(i)
        _drop_if_empty(p, "children")
        if "children" not in target or target["children"] is None:
            target["children"] = CommentedSeq()
        kids = target["children"]
        idx = op.get("index")
        idx = len(kids) if idx is None else max(0, min(int(idx), len(kids)))
        kids.insert(idx, n)
        return {"id": op["id"], "parent": op["parent"], "index": idx}
    if kind == "add_check":
        n, *_ = doc.find(op["id"])
        fields = dict(op.get("check") or {})
        cid = fields.pop("id", None) or _next_sub_id(doc, op["id"], "c", taken)
        if cid in doc.ids():
            raise IntentOpError(f"id '{cid}' is already used")
        c = CommentedMap()
        c["id"] = cid
        if not str(fields.get("statement", "")).strip():
            raise IntentOpError("a check needs a statement")
        _set_fields(c, fields, "check")
        if "checks" not in n or n["checks"] is None:
            n["checks"] = CommentedSeq()
        _append_like_siblings(n["checks"], c)
        return {"id": op["id"], "check_id": cid}
    if kind == "edit_check":
        n, *_ = doc.find(op["id"])
        lst, i = _find_sub(n, "checks", op["check_id"], "check")
        _set_fields(lst[i], dict(op.get("fields") or {}), "check")
        return {"id": op["id"], "check_id": op["check_id"]}
    if kind == "remove_check":
        n, *_ = doc.find(op["id"])
        lst, i = _find_sub(n, "checks", op["check_id"], "check")
        lst.pop(i)
        _drop_if_empty(n, "checks")
        return {"id": op["id"], "check_id": op["check_id"]}
    if kind == "edit_assumption":
        n, *_ = doc.find(op["id"])
        lst, i = _find_sub(n, "assumptions", op["assumption_id"], "assumption")
        _set_fields(lst[i], dict(op.get("fields") or {}), "assumption")
        return {"id": op["id"], "assumption_id": op["assumption_id"]}
    if kind == "add_assumption":
        n, *_ = doc.find(op["id"])
        fields = dict(op.get("assumption") or {})
        aid = fields.pop("id", None) or _next_sub_id(doc, op["id"], "a", taken)
        if aid in doc.ids():
            raise IntentOpError(f"id '{aid}' is already used")
        a = CommentedMap()
        a["id"] = aid
        _set_fields(a, fields, "assumption")
        if "assumptions" not in n or n["assumptions"] is None:
            n["assumptions"] = CommentedSeq()
        _append_like_siblings(n["assumptions"], a)
        return {"id": op["id"], "assumption_id": aid}
    if kind == "set_binding":
        # designer accepts / challenges / replaces a check's binding (iteration 4)
        n, *_ = doc.find(op["id"])
        lst, i = _find_sub(n, "checks", op["check_id"], "check")
        c = lst[i]
        if op.get("binding") is not None:
            b = op["binding"]
            if not isinstance(b, dict):
                raise IntentOpError("binding must be a mapping")
            m = CommentedMap()
            for k, v in b.items():
                m[str(k)] = str(v)
            m.fa.set_flow_style()
            c["binding"] = m
        if op.get("status"):
            if "binding" not in c:
                raise IntentOpError(f"check '{op['check_id']}' has no binding")
            c["binding"]["status"] = _like(c["binding"].get("status"), str(op["status"]))
        return {"id": op["id"], "check_id": op["check_id"]}
    if kind in ("add_component", "edit_component", "remove_component"):
        comps = doc.data.get("components")
        if kind == "add_component":
            fields = dict(op.get("component") or {})
            cid = str(fields.pop("id", "") or "")
            if not cid or cid in doc.ids() or any(str(x.get("id")) == cid for x in comps or []):
                raise IntentOpError(f"component id '{cid}' is missing or already used")
            if comps is None:
                comps = CommentedSeq()
                keys = list(doc.data.keys())
                doc.data.insert(keys.index("intents") if "intents" in keys else len(keys), "components", comps)
            c = CommentedMap()
            c["id"] = cid
            _set_fields(c, fields, "component")
            _append_like_siblings(comps, c)
            return {"component_id": cid}
        cid = str(op.get("component_id") or "")
        for i, x in enumerate(comps or []):
            if str(x.get("id")) == cid:
                if kind == "remove_component":
                    comps.pop(i)
                    if not comps:
                        del doc.data["components"]
                else:
                    _set_fields(x, dict(op.get("fields") or {}), "component")
                return {"component_id": cid}
        raise IntentOpError(f"no component '{cid}'")
    raise IntentOpError(f"unknown operation {kind!r}")


def apply_ops(doc: IntentDoc, ops: list, taken=()) -> list:
    """Apply several edits in order, then re-validate.  All or nothing: on error the caller
    discards `doc` (re-load from disk), so a half-applied list never reaches a file."""
    results = [apply_op(doc, op, taken) for op in ops]
    errs = validate(doc.data)
    if errs:
        raise IntentSchemaError(errs, doc.path)
    return results


def rename_id_in_doc(doc: IntentDoc, old: str, new: str) -> None:
    """Rename a node id (the explicit 'rename id' action, gui.md §7.4).  Check/assumption ids
    that start with `old.` are renamed with it; `supports` lists are updated."""
    if not ID_RE.match(new):
        raise IntentOpError(f"'{new}' is not a valid id")
    if new in doc.ids():
        raise IntentOpError(f"id '{new}' is already used")
    doc.find(old)

    def ren(i: str) -> str:
        return new + i[len(old):] if i == old or i.startswith(old + ".") else i

    for n, *_ in iter_nodes_raw(doc.data):
        n["id"] = _like(n["id"], ren(str(n["id"])))
        for c in n.get("checks") or []:
            c["id"] = _like(c["id"], ren(str(c["id"])))
        for a in n.get("assumptions") or []:
            a["id"] = _like(a["id"], ren(str(a["id"])))
            if a.get("supports"):
                for k, s in enumerate(a["supports"]):
                    a["supports"][k] = _like(s, ren(str(s)))
