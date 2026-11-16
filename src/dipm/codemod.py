"""Rename an intent id across the DSL, safely (docs/gui.md §7.4 "rename id").

Ids are stable labels: moving a node never rewrites them.  Renaming is a separate, explicit
action that must update every reference.  This codemod uses LibCST (a lossless syntax tree,
so comments and formatting are untouched) and rewrites **only** intent-id string literals:

* the first argument (or `node=`) of `intent(...)` calls, e.g. `tags=intent("A.P", "pattern")`;
* string elements of `instance_tags=[...]` / `(...)` keyword arguments.

`old` matches the id itself and every id beneath it by dotted prefix (`A.P` also renames
`A.P.1`), the same rule `intent_store.rename_id_in_doc` applies to the intent file.  Strings
anywhere else (docs, notes, feature ids like "A.P.holes" passed as the feature name) are not
touched, so a rename never silently changes geometry or feature ids.

`rename_features=True` (NOTES #49 change, an opt-in checkbox in the GUI) also renames feature
ids that start with the intent id: the first argument of the design's feature constructors
(`d.hole("A.3.cable", …)` -> `d.hole("A.C.cable", …)`).  Geometry is unchanged, but feature ids
appear in interpretation slot ids, so the lock is re-resolved.
"""
from __future__ import annotations

import ast

import libcst as cst


def _renamed(value: str, old: str, new: str) -> str | None:
    if value == old or value.startswith(old + "."):
        return new + value[len(old):]
    return None


FEATURE_CTORS = ("extrude", "revolve", "fillet", "chamfer", "mirror", "transform", "shell", "draft", "clean", "hole")


class _Renamer(cst.CSTTransformer):
    def __init__(self, old: str, new: str, rename_features: bool = False):
        self.old, self.new = old, new
        self.count = 0
        self.features = rename_features
        self.feature_count = 0

    def _fix(self, node: cst.BaseExpression) -> cst.BaseExpression:
        if isinstance(node, cst.SimpleString):
            try:
                val = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                return node
            if not isinstance(val, str):
                return node
            r = _renamed(val, self.old, self.new)
            if r is not None:
                self.count += 1
                q = node.quote
                prefix = node.prefix
                return node.with_changes(value=f"{prefix}{q}{r}{q}")
        return node

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.Call:
        f = updated.func
        name = f.value if isinstance(f, cst.Name) else (f.attr.value if isinstance(f, cst.Attribute) else None)
        args = list(updated.args)
        changed = False
        for i, a in enumerate(args):
            if (self.features and isinstance(f, cst.Attribute) and name in FEATURE_CTORS and i == 0
                    and a.keyword is None and isinstance(a.value, cst.SimpleString)):
                try:
                    val = ast.literal_eval(a.value.value)
                except (ValueError, SyntaxError):
                    val = None
                if isinstance(val, str) and val.startswith(self.old + "."):
                    q = a.value.quote
                    args[i] = a.with_changes(value=a.value.with_changes(
                        value=f"{a.value.prefix}{q}{self.new + val[len(self.old):]}{q}"))
                    self.feature_count += 1
                    changed = True
                    continue
            if name == "intent" and ((i == 0 and a.keyword is None) or (a.keyword and a.keyword.value == "node")):
                v = self._fix(a.value)
                if v is not a.value:
                    args[i] = a.with_changes(value=v)
                    changed = True
            if a.keyword and a.keyword.value == "instance_tags" and isinstance(a.value, (cst.List, cst.Tuple)):
                els = [e.with_changes(value=self._fix(e.value)) for e in a.value.elements]
                if any(x.value is not y.value for x, y in zip(els, a.value.elements)):
                    args[i] = a.with_changes(value=a.value.with_changes(elements=els))
                    changed = True
        return updated.with_changes(args=args) if changed else updated


def rename_intent_id(source: str, old: str, new: str, rename_features: bool = False) -> tuple[str, int]:
    """(new source, number of literals rewritten, feature ids included)."""
    mod = cst.parse_module(source)
    t = _Renamer(old, new, rename_features)
    out = mod.visit(t)
    return out.code, t.count + t.feature_count
