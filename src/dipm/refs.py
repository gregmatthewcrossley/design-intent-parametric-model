"""Structural references resolved through kernel history (dsl.md §3.4).

The topological naming problem, v0 answer:

* A reference names an entity by **how an operation created it**: (feature id, role,
  source), e.g. `E.side(mount)` = "the face extrude E swept from sketch edge `mount`".
  Never by ordinal (`face[17]`), and never as an identity reference to a contingent
  fragment left by a later cut.
* The `Ledger` records the sub-shapes each feature creates, tagged with their role,
  and carries every tag forward through each later operation using that operation's
  OCP history (`Modified`, and opt-in `Generated`), plus presence in the result.
  `IsDeleted` is **never trusted** (wrong after fillet and chamfer: spike 01 §2.1,
  spike 02 §1.2); disagreements are only logged.
* Every reference **declares its cardinality** (`one()`, `exactly(n)`, `at_least(n)`);
  a mismatch is an error, not a silent pick.
* Split and merge are **events** in each entry's genealogy.  Policies
  (`error_on_split`, `error_on_merge`) turn them into errors per reference.
* `edges_between(face_ref, face_ref)` is a **derived structural reference**: the only
  way to name edges after draft/offset (spike 02 §7.3).

Ported from spikes/01-occt-feasibility/refs.py and spikes/02-operation-history/common.py
(`Ledger2`: follow-Generated, merge detection).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import kernel as K
from .errors import CardinalityError, PolicyError, ReferenceError_


# ---------------------------------------------------------------- tags and cardinality

@dataclass(frozen=True, order=True)
class Tag:
    """Creator tag: which feature made a sub-shape, in what role, from what source."""
    feature: str
    role: str
    source: str | None = None

    def __str__(self):
        return f"{self.feature}.{self.role}" + (f"({self.source})" if self.source is not None else "")


@dataclass(frozen=True)
class Cardinality:
    mode: str   # "exactly" | "at_least"
    n: int

    def ok(self, count: int) -> bool:
        return count == self.n if self.mode == "exactly" else count >= self.n

    def __str__(self):
        if self.mode == "exactly":
            return "one()" if self.n == 1 else f"exactly({self.n})"
        return f"at_least({self.n})"


def one() -> Cardinality:
    return Cardinality("exactly", 1)


def exactly(n: int) -> Cardinality:
    return Cardinality("exactly", n)


def at_least(n: int) -> Cardinality:
    return Cardinality("at_least", n)


PROPAGATE_ALL = "propagate_all"
ERROR_ON_SPLIT = "error_on_split"
ERROR_ON_MERGE = "error_on_merge"
_POLICIES = {PROPAGATE_ALL, ERROR_ON_SPLIT, ERROR_ON_MERGE}


def _policy_set(policy) -> frozenset:
    ps = frozenset([policy] if isinstance(policy, str) else policy)
    bad = ps - _POLICIES
    if bad:
        raise ValueError(f"unknown policy {sorted(bad)}; use {sorted(_POLICIES)}")
    return ps


# ---------------------------------------------------------------- ledger

@dataclass(frozen=True)
class Entry:
    """One tracked sub-shape: its current shape, creator tag and event genealogy.

    genealogy: tuple of (feature_id, event) with event in
    {'modified', 'splitN', 'regenerated', 'regeneratedN', 'merged'}.
    """
    shape: object
    tag: Tag
    genealogy: tuple = ()


@dataclass
class Ledger:
    items: list = field(default_factory=list)
    deleted: list = field(default_factory=list)            # (tag, feature_id, genealogy)
    isdeleted_disagreements: list = field(default_factory=list)

    def copy(self) -> "Ledger":
        return Ledger(list(self.items), list(self.deleted), list(self.isdeleted_disagreements))

    # ---- creation
    def add(self, tag: Tag, shapes) -> None:
        for s in shapes:
            self.items.append(Entry(s, tag, ()))

    # ---- propagation through one operation
    def propagate(self, op_id: str, algo, result, follow_generated: bool = False) -> None:
        """Carry every entry through one operation's history.

        For each entry: images under `Modified` that are present in the result; else the
        shape itself if still present; else (opt-in) same-type `Generated` images (draft,
        offset report face images only there: spike 02 §1.6); else deleted.
        A result sub-shape reached from >= 2 distinct pre-op shapes gets a `merged` event.
        """
        present = K.presence_map(result)
        staged = []          # (old_shape, Entry)
        for e in self.items:
            mods = [m for m in K.occ_list(algo.Modified(e.shape)) if present.Contains(m)]
            gone = False
            if mods:
                ev = (op_id, "modified" if len(mods) == 1 else f"split{len(mods)}")
                staged.extend((e.shape, Entry(m, e.tag, e.genealogy + (ev,))) for m in mods)
            elif present.Contains(e.shape):
                staged.append((e.shape, e))
            else:
                gens = []
                if follow_generated:
                    gens = [g for g in K.occ_list(algo.Generated(e.shape))
                            if present.Contains(g) and g.ShapeType() == e.shape.ShapeType()]
                if gens:
                    ev = (op_id, "regenerated" if len(gens) == 1 else f"regenerated{len(gens)}")
                    staged.extend((e.shape, Entry(g, e.tag, e.genealogy + (ev,))) for g in gens)
                else:
                    self.deleted.append((e.tag, op_id, e.genealogy))
                    gone = True
            try:
                kernel_deleted = bool(algo.IsDeleted(e.shape))
            except Exception:  # some history objects lack IsDeleted; it is advisory only
                kernel_deleted = gone
            if gone != kernel_deleted:
                self.isdeleted_disagreements.append((str(e.tag), op_id, gone, kernel_deleted))
        # merge detection
        img = K.ShapeMap()
        sources: dict[int, K.ShapeMap] = {}
        for old, ent in staged:
            i = img.Add(ent.shape)
            sources.setdefault(i, K.ShapeMap()).Add(old)
        out = []
        for old, ent in staged:
            if sources[img.FindIndex(ent.shape)].Extent() > 1:
                ent = Entry(ent.shape, ent.tag, ent.genealogy + ((op_id, "merged"),))
            out.append(ent)
        self.items = out

    # ---- queries
    def entries(self, feature: str, role: str, source: str | None = None, any_source: bool = False) -> list:
        return [e for e in self.items
                if e.tag.feature == feature and e.tag.role == role
                and (any_source or e.tag.source == source)]

    def unique(self, entries) -> list:
        """De-duplicate entries by sub-shape identity (a fragment may be reachable twice)."""
        m, out = K.ShapeMap(), []
        for e in entries:
            if not m.Contains(e.shape):
                m.Add(e.shape)
                out.append(e)
        return out

    def who(self, shape) -> list:
        """All entries whose current shape IsSame `shape` (the 'why is this here?' lookup)."""
        return [e for e in self.items if e.shape.IsSame(shape)]

    def tags(self) -> list:
        seen = {}
        for e in self.items:
            seen.setdefault(e.tag, None)
        for t, _, _ in self.deleted:
            seen.setdefault(t, None)
        return list(seen)


# ---------------------------------------------------------------- lazy reference objects

@dataclass(frozen=True)
class Ref:
    """Lazy structural reference `feature.role(source)` with declared cardinality and policy.

    Created by feature handles (`body.side("mount")`), resolved during evaluation by
    `Context.resolve` (or `evaluate`), which returns sub-shapes oriented as in the
    current solid.  `any_source=True` resolves every source of the role (`F.created()`).
    """
    feature: str
    role: str
    source: str | None = None
    card: Cardinality = field(default_factory=one)
    policy: frozenset = frozenset({PROPAGATE_ALL})
    kind: str | None = None        # "face" | "edge" | "vertex" (checked if given)
    any_source: bool = False

    # fluent modifiers ----------------------------------------------------------
    def expect(self, card: Cardinality) -> "Ref":
        return replace(self, card=card)

    def with_policy(self, *policies: str) -> "Ref":
        return replace(self, policy=_policy_set(policies))

    @property
    def tag(self) -> Tag:
        return Tag(self.feature, self.role, self.source)

    def __str__(self):
        src = "*" if self.any_source else self.source
        return f"{self.feature}.{self.role}" + (f"({src})" if src is not None else "")

    def key(self) -> str:
        return str(self)

    # resolution ----------------------------------------------------------------
    def entries(self, env) -> list:
        led: Ledger = env.ledger
        return led.unique(led.entries(self.feature, self.role, self.source, self.any_source))

    def evaluate(self, env) -> list:
        return env.resolve(self)

    def check(self, env, entries: list) -> None:
        """Raise if cardinality, kind, or policy is violated."""
        n = len(entries)
        if not self.card.ok(n):
            deleted_at = [fid for t, fid, _ in env.ledger.deleted
                          if t.feature == self.feature and t.role == self.role
                          and (self.any_source or t.source == self.source)]
            raise CardinalityError(
                f"reference {self} resolved to {n} {self.kind or 'sub-shape'}(s)",
                feature=env.current_feature, intent=env.current_intent,
                invariant="reference cardinality (dsl.md §3.4)", expected=str(self.card), got=n,
                details={"genealogy": sorted({_fmt_gen(e.genealogy) for e in entries}) or "-",
                         **({"deleted by": deleted_at} if deleted_at else {})})
        if self.kind is not None:
            want = K.KINDS[self.kind]
            bad = [e for e in entries if e.shape.ShapeType() != want]
            if bad:
                raise ReferenceError_(f"reference {self} expected {self.kind}s, got another kind",
                                      feature=env.current_feature, intent=env.current_intent)
        if ERROR_ON_SPLIT in self.policy:
            ev = [x for e in entries for x in e.genealogy if x[1].startswith("split")]
            if ev:
                raise PolicyError(f"reference {self} was split (policy error_on_split)",
                                  feature=env.current_feature, intent=env.current_intent,
                                  details={"events": ev})
        if ERROR_ON_MERGE in self.policy:
            ev = [x for e in entries for x in e.genealogy if x[1] == "merged"]
            if ev:
                raise PolicyError(f"reference {self} was merged with another reference (policy error_on_merge)",
                                  feature=env.current_feature, intent=env.current_intent,
                                  details={"events": ev})


@dataclass(frozen=True)
class EdgesBetween:
    """Derived structural reference: edges shared by the faces of two face references.

    Counts as structural (dsl.md §3.4).  The input references are resolved with their own
    declared cardinality and policies first.
    """
    a: Ref
    b: Ref
    card: Cardinality = field(default_factory=one)
    policy: frozenset = frozenset({PROPAGATE_ALL})
    kind: str = "edge"

    def expect(self, card: Cardinality) -> "EdgesBetween":
        return replace(self, card=card)

    def __str__(self):
        return f"edges_between({self.a}, {self.b})"

    def key(self) -> str:
        return str(self)

    def evaluate(self, env) -> list:
        return env.resolve(self)

    def shapes(self, env) -> list:
        fa, fb = env.resolve(self.a), env.resolve(self.b)
        m, out = K.ShapeMap(), []
        for f1 in fa:
            for f2 in fb:
                for e in K.shared_edges(f1, f2):
                    if not m.Contains(e):
                        m.Add(e)
                        out.append(e)
        return out

    def check(self, env, shapes: list) -> None:
        if not self.card.ok(len(shapes)):
            raise CardinalityError(f"derived reference {self} resolved to {len(shapes)} edge(s)",
                                   feature=env.current_feature, intent=env.current_intent,
                                   invariant="reference cardinality (dsl.md §3.4)",
                                   expected=str(self.card), got=len(shapes))


def edges_between(a: Ref, b: Ref, card: Cardinality | None = None) -> EdgesBetween:
    """`edges_between(face_ref, face_ref)`: the derived edge reference of dsl.md §3.4."""
    return EdgesBetween(a, b, card or one())


def _fmt_gen(gen: tuple) -> str:
    return " -> ".join(f"{f}:{e}" for f, e in gen) or "(unchanged)"


fmt_genealogy = _fmt_gen
