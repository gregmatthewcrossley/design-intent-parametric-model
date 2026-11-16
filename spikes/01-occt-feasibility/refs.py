"""A tiny structural-reference layer on top of OCCT operation history.

Every tracked sub-shape carries a Tag (feature id, role, source) and a genealogy:
the sequence of (operation, event) pairs it went through after it was created.
After every operation the ledger is carried forward with the operation's own
history API (BRepBuilderAPI_MakeShape.Modified / IsDeleted, which booleans and
fillets both implement). References are then resolved by tag, with a declared
cardinality, never by index.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher


@dataclass(frozen=True)
class Tag:
    feature: str
    role: str
    source: str | None = None

    def __str__(self):
        return f"{self.feature}.{self.role}" + (f"({self.source})" if self.source else "")


class CardinalityError(Exception):
    pass


def one():
    return ("exactly", 1)


def exactly(n):
    return ("exactly", n)


def at_least(n):
    return ("at_least", n)


def _list(lst):
    from topo import occ_list
    return occ_list(lst)


@dataclass
class Entry:
    shape: object
    tag: Tag
    genealogy: tuple = ()


@dataclass
class Ledger:
    items: list = field(default_factory=list)
    deleted: list = field(default_factory=list)          # (tag, op, genealogy)
    isdeleted_disagreements: list = field(default_factory=list)

    # ---- creation
    def add(self, tag: Tag, shapes):
        for s in shapes:
            self.items.append(Entry(s, tag, ()))

    # ---- propagation through one operation
    def propagate(self, op_id: str, algo, result):
        present = IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher()
        for kind in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
            TopExp.MapShapes_s(result, kind, present)
        new = []
        for e in self.items:
            mods = [m for m in _list(algo.Modified(e.shape)) if present.Contains(m)]
            kernel_says_deleted = bool(algo.IsDeleted(e.shape))
            if mods:
                ev = (op_id, "modified" if len(mods) == 1 else f"split{len(mods)}")
                new.extend(Entry(m, e.tag, e.genealogy + (ev,)) for m in mods)
                gone = False
            elif present.Contains(e.shape):
                new.append(e)
                gone = False
            else:
                self.deleted.append((e.tag, op_id, e.genealogy))
                gone = True
            if gone != kernel_says_deleted:
                self.isdeleted_disagreements.append((str(e.tag), op_id, gone, kernel_says_deleted))
        self.items = new

    # ---- resolution
    def entries(self, feature, role, source=None):
        return [e for e in self.items
                if e.tag.feature == feature and e.tag.role == role
                and (source is None or e.tag.source == source)]

    def resolve(self, feature, role, source=None, card=("exactly", 1), policy="propagate_all"):
        es = self.entries(feature, role, source)
        # de-duplicate by sub-shape identity (a fragment may be reachable twice)
        uniq = []
        for e in es:
            if not any(e.shape.IsSame(u.shape) for u in uniq):
                uniq.append(e)
        n = len(uniq)
        mode, k = card
        if (mode == "exactly" and n != k) or (mode == "at_least" and n < k):
            raise CardinalityError(f"{feature}.{role}({source}): expected {mode} {k}, got {n}")
        if policy == "error_on_split" and any(ev[1].startswith("split") for e in uniq for ev in e.genealogy):
            raise CardinalityError(f"{feature}.{role}({source}) was split (policy error_on_split)")
        return [e.shape for e in uniq]

    def genealogy(self, feature, role, source=None):
        return sorted({e.genealogy for e in self.entries(feature, role, source)})
