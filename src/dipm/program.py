"""Program model: a declarative, ordered feature graph with declared parameters.

architecture.md §2.2 (solution = DSL program), §7 (determinism); dsl.md §1 (two layers,
intent tags survive lowering), §5 (invariants after every feature).

* A `Design` is built once through the embedded Python API: `d.param(...)` declares
  parameters (the only literals); `d.extrude(...)`, `d.hole(...)`, ... append features
  in order.  Feature arguments are lazy (expressions, references, placements), so the
  design is *data*, not a recording of numbers.
* `Design.build(**params)` is a **pure function** parameters -> `Build`: it creates a
  fresh `Context` (empty solid, empty ledger), evaluates each feature in order, and runs
  the invariants after every one.  Re-evaluate with other values for edit tests.
* Every feature has a hierarchical id (e.g. "A.P", "A.3", "C.G") and carries
  `IntentTag`s (intent word + intent-node id).  Intent-layer features (`hole`) record the
  core op they lowered to; per-instance tags (A.P.1, A.P.2) are kept too.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from . import kernel as K
from .errors import DipmError, InvariantError, KernelError, ParameterError
from .expr import Param, ParamRef
from .invariants import FeatureChecks, Signature, canonical_bytes, run_feature_invariants, signature
from .refs import EdgesBetween, Ledger, Ref, Tag, fmt_genealogy


# ---------------------------------------------------------------- intent tags

@dataclass(frozen=True, order=True)
class IntentTag:
    """Which intent word, at which intent-tree node, produced a feature (dsl.md §1)."""
    node: str          # intent-tree node id, e.g. "A.P.1"
    word: str          # intent word, e.g. "hole", "pattern", "skeleton", "gusset"
    note: str = ""

    def __str__(self):
        return f"{self.word}@{self.node}" + (f" ({self.note})" if self.note else "")


def intent(node: str, word: str, note: str = "") -> IntentTag:
    return IntentTag(node, word, note)


def _tags(tags) -> tuple:
    if tags is None:
        return ()
    if isinstance(tags, IntentTag):
        return (tags,)
    return tuple(tags)


# ---------------------------------------------------------------- evaluation context

@dataclass
class Resolution:
    """One reference resolution performed by a feature (kept for the stability harness)."""
    ref: str
    count: int
    genealogies: tuple

    def key(self) -> tuple:
        return (self.ref, self.count, self.genealogies)


class Context:
    """Mutable state of *one* evaluation.  Never shared between builds."""

    def __init__(self, design: "Design", params: dict, choices: dict | None = None, prefs=None,
                 choice_made_by: dict | None = None):
        self.design = design
        self.params = params
        # interpretations (architecture §10.2): slot id -> reading name, and who made each choice
        self.choices = dict(choices or {})
        self.choice_made_by = dict(choice_made_by or {})
        self.prefs = prefs
        self.slot_uses: list = []         # interpret.SlotUse, in the order slots were met
        self.slot_keys: dict = {}
        self.hole_centres: list = []      # (feature_id, k, face ref text, centre) for sibling relations
        self.shape = None
        self.ledger = Ledger()
        self.current_feature: str | None = None
        self.current_intent: tuple = ()
        self.resolutions: list[Resolution] = []
        self.hole_tools: list = []        # (feature_id, instance k, tool shape, node) for interaction checks
        self.notes: list[str] = []

    def interpret(self, reading_set, explicit: str | None = None, consider=(), key: str = ""):
        """Which reading of an ambiguous intent-word slot to lower (architecture §10.2).

        Intent words call this while lowering; it returns the chosen `interpret.Reading`
        (from the lock / resolution, else the ranked default) and records the slot use.
        `explicit` is the author's own value, which bypasses interpretation."""
        from .interpret import choose
        return choose(self, reading_set, explicit, consider, key)

    def resolve(self, ref) -> list:
        """Resolve a structural or derived reference on the *current* solid.

        Returns sub-shapes oriented as in the current solid.  Raises on cardinality or
        policy violation, naming the feature doing the resolving.
        """
        if isinstance(ref, EdgesBetween):
            shapes = ref.shapes(self)
            ref.check(self, shapes)
            self.resolutions.append(Resolution(str(ref), len(shapes), ()))
            return [K.oriented_in(s, self.shape) for s in shapes]
        if not isinstance(ref, Ref):
            raise TypeError(f"not a reference: {ref!r}")
        entries = ref.entries(self)
        ref.check(self, entries)
        self.resolutions.append(Resolution(str(ref), len(entries),
                                           tuple(sorted({fmt_genealogy(e.genealogy) for e in entries}))))
        return [K.oriented_in(e.shape, self.shape) if self.shape is not None else e.shape for e in entries]


# ---------------------------------------------------------------- records and results

@dataclass
class FeatureRecord:
    id: str
    op: str                     # core op actually executed (e.g. "cut", "extrude")
    lowered_from: str | None    # intent word it was lowered from (e.g. "hole(countersink)")
    tags: tuple                 # IntentTags of the feature
    instance_tags: dict         # source -> tuple[IntentTag] (e.g. "0" -> (hole@A.P.1,))
    checks: FeatureChecks | None = None
    expect: object = None
    inputs: list = field(default_factory=list)   # Resolutions made while evaluating this feature
    error: DipmError | None = None
    ms: float = 0.0
    byte_deterministic: bool = True
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and (self.checks is None or self.checks.ok)


@dataclass
class WhyEntry:
    """One line of genealogy for "why is this here?"."""
    tag: Tag
    feature: str
    op: str
    lowered_from: str | None
    intent: tuple               # IntentTags of the creating feature
    instance_intent: tuple      # IntentTags of the specific instance, if any
    events: tuple               # (feature_id, event) after creation

    def __str__(self):
        it = ", ".join(str(t) for t in self.instance_intent + self.intent)
        low = f" lowered from {self.lowered_from}" if self.lowered_from else ""
        return f"{self.tag}  [op {self.op}{low}]  intent: {it or '-'}  history: {fmt_genealogy(self.events)}"


@dataclass
class Why:
    shape_kind: str
    descriptor: str
    entries: list               # WhyEntry
    derived_from: list = field(default_factory=list)   # for untracked edges: Why of adjacent faces

    def intent_nodes(self) -> list[str]:
        out = []
        for e in self.entries:
            for t in e.instance_intent + e.intent:
                if t.node not in out:
                    out.append(t.node)
        for w in self.derived_from:
            for n in w.intent_nodes():
                if n not in out:
                    out.append(n)
        return out

    def __str__(self):
        lines = [f"{self.shape_kind}: {self.descriptor}"]
        lines += [f"  created as {e}" for e in self.entries]
        if self.derived_from:
            lines.append("  untracked edge; derived as edges_between of:")
            lines += ["    " + str(w).replace("\n", "\n    ") for w in self.derived_from]
        if not self.entries and not self.derived_from:
            lines.append("  (no genealogy: untracked)")
        return "\n".join(lines)


@dataclass
class Build:
    """Result of one evaluation: solid, ledger, per-feature records, exports, signature."""
    design: "Design"
    params: dict
    shape: object
    ledger: Ledger
    records: list
    exports: dict               # name -> Resolution (or error string)
    errors: list                # DipmError
    signature: Signature | None = None
    ms: float = 0.0
    slots: list = field(default_factory=list)       # interpret.SlotUse met during this build
    interpretation: object = None                    # interpret.Interpretation behind the choices, if any
    interpretation_source: str = ""                  # "lock <path>" | "resolved in memory" | "explicit" | ""

    @property
    def ok(self) -> bool:
        return not self.errors and all(r.ok for r in self.records)

    @property
    def byte_deterministic(self) -> bool:
        return all(r.byte_deterministic for r in self.records)

    def record(self, fid: str) -> FeatureRecord:
        for r in self.records:
            if r.id == fid:
                return r
        raise KeyError(fid)

    def canonical(self) -> tuple[str, bytes]:
        """Canonical serialization: ('brep', BRep text) or ('fingerprint', json) (dsl.md §5.4)."""
        return canonical_bytes(self.shape, self.ledger, self.byte_deterministic)

    # references on the final solid ------------------------------------------------
    def resolve(self, ref) -> list:
        ctx = Context(self.design, self.params)
        ctx.shape, ctx.ledger, ctx.current_feature = self.shape, self.ledger, "<final>"
        return ctx.resolve(ref)

    # "why is this here?" ------------------------------------------------------------
    def why(self, sub) -> Why:
        """Genealogy of a face/edge/vertex of the final solid: creating feature, role,
        intent tags (feature + instance), and the events it went through.  Edges that no
        feature tagged are explained as `edges_between` their adjacent faces."""
        rec = {r.id: r for r in self.records}
        entries = []
        for e in self.ledger.who(sub):
            r = rec.get(e.tag.feature)
            entries.append(WhyEntry(e.tag, e.tag.feature, r.op if r else "?", r.lowered_from if r else None,
                                    r.tags if r else (), r.instance_tags.get(e.tag.source, ()) if r else (),
                                    e.genealogy))
        kind = K.KIND_NAME.get(sub.ShapeType(), "?")
        w = Why(kind, K.describe(sub, self.shape), entries)
        if not entries and kind == "edge":
            w.derived_from = [self.why(f) for f in K.faces_of_edge(self.shape, sub)]
        return w

    def faces(self) -> list:
        return K.subshapes(self.shape, K.KINDS["face"])

    def edges(self) -> list:
        return K.subshapes(self.shape, K.KINDS["edge"])

    def untracked_faces(self) -> list:
        """Faces with no genealogy (coverage gaps).  Should be empty (spike 02: coverage 0)."""
        return [f for f in self.faces() if not self.ledger.who(f)]

    def write(self, path_stem: str, brep: bool = True, step: bool = False) -> list[str]:
        out = []
        if brep:
            K.write_brep(self.shape, path_stem + ".brep")
            out.append(path_stem + ".brep")
        if step:
            K.write_step(self.shape, path_stem + ".step")
            out.append(path_stem + ".step")
        return out


# ---------------------------------------------------------------- the design

class Design:
    """An ordered feature graph plus declared parameters.  See module docstring."""

    def __init__(self, name: str, doc: str = ""):
        self.name = name
        self.doc = doc
        self.params: dict[str, Param] = {}
        self.features: list = []
        self.exports: dict[str, object] = {}
        # interpretations (architecture §10.2): attached with use_lock() or set directly
        self.interpretations: dict | None = None    # slot id -> reading name
        self.interpretation = None                  # interpret.Interpretation behind them
        self.lock = None                            # interpret.LockSpec
        self.prefs = None                           # interpret.Preferences used for resolution
        self._interp_source = ""

    # interpretations -------------------------------------------------------------
    def use_lock(self, design_file: str, lock: str | None = None, prefs: str | None = None) -> "Design":
        """Read resolved interpretations from `<design>.interpretations.json` (architecture §7,
        §10.2).  Loaded lazily at the first build: a fresh lock is used as-is; a missing or
        stale one (design source, preferences or reading tables changed) is re-resolved in
        memory with a warning.  `python -m dipm interpret <design>` rewrites it."""
        from .interpret import LockSpec, lock_path_for
        self.lock = LockSpec(os.path.abspath(design_file), lock or lock_path_for(os.path.abspath(design_file)), prefs)
        self.interpretations = self.interpretation = None
        return self

    def ensure_interpretations(self, force: bool = False):
        """Load (or resolve) the interpretation for this design's lock; memoized."""
        if self.lock is None:
            return None
        if self.interpretation is None or force:
            from .interpret import load_or_resolve
            interp, prefs, fresh = load_or_resolve(self, self.lock, force=force)
            self.interpretation, self.prefs = interp, prefs
            self.interpretations = dict(interp.choices)
            self._interp_source = f"lock {os.path.relpath(self.lock.lock)}" if fresh else "resolved in memory"
        return self.interpretation

    # parameters ------------------------------------------------------------------
    def param(self, name: str, default, range: tuple | None = None, choices: tuple | None = None,
              unit: str = "mm", doc: str = "", samples: tuple | None = None) -> ParamRef:
        if name in self.params:
            raise ValueError(f"parameter {name!r} declared twice")
        p = Param(name, default, tuple(range) if range else None, tuple(choices) if choices else None,
                  unit, doc, tuple(samples) if samples else None)
        p.validate(default)
        self.params[name] = p
        return ParamRef(name)

    def defaults(self) -> dict:
        return {n: p.default for n, p in self.params.items()}

    # features --------------------------------------------------------------------
    def add(self, feature):
        if any(f.id == feature.id for f in self.features):
            raise ValueError(f"feature id {feature.id!r} used twice")
        self.features.append(feature)
        return feature

    def feature(self, fid: str):
        """The feature (and its role accessors) with this id."""
        for f in self.features:
            if f.id == fid:
                return f
        raise KeyError(fid)

    def export(self, name: str, ref) -> None:
        """Declare a named export: resolved on the final solid with its declared cardinality
        (architecture §2.3 `exports`), and watched by the stability harness."""
        self.exports[name] = ref

    # convenience constructors (thin; see ops.py / intent.py for the real docs) ---------
    def extrude(self, id, profile, distance, *, symmetric=False, mode="new", tags=(), expect=None):
        from .ops import Extrude
        return self.add(Extrude(id, _tags(tags), profile, distance, symmetric, mode, expect))

    def revolve(self, id, profile, axis, *, angle=360.0, mode="new", tags=(), expect=None):
        from .ops import Revolve
        return self.add(Revolve(id, _tags(tags), profile, axis, angle, mode, expect))

    def fillet(self, id, edges, radius, *, tags=()):
        from .ops import Fillet
        return self.add(Fillet(id, _tags(tags), edges, radius))

    def chamfer(self, id, edges, distance, *, tags=()):
        from .ops import Chamfer
        return self.add(Chamfer(id, _tags(tags), edges, distance))

    def mirror(self, id, origin, normal, *, clean=True, tags=(), expect=None):
        from .ops import Mirror
        return self.add(Mirror(id, _tags(tags), origin, normal, clean, expect))

    def transform(self, id, *, translate=None, rotate=None, tags=()):
        from .ops import Transform
        return self.add(Transform(id, _tags(tags), translate, rotate))

    def shell(self, id, openings, thickness, *, tags=()):
        from .ops import Shell
        return self.add(Shell(id, _tags(tags), tuple(openings), thickness))

    def draft(self, id, faces, angle, *, neutral_origin=(0.0, 0.0, 0.0), pull=(0.0, 0.0, 1.0), tags=()):
        from .ops import Draft
        return self.add(Draft(id, _tags(tags), tuple(faces), angle, neutral_origin, pull))

    def clean(self, id, *, tags=()):
        from .ops import Clean
        return self.add(Clean(id, _tags(tags)))

    def hole(self, id, on, at, spec, extent=None, *, tags=(), instance_tags=None, expect=None):
        """extent=None leaves the extent to the interpretations mechanism (architecture §10.2):
        through_plate / through_all / up_to_next.  An explicit extent is used as given."""
        from .intent_layer import Hole
        inst = None
        if instance_tags is not None:
            inst = tuple(_tags(t) if not isinstance(t, str) else (IntentTag(t, "hole"),) for t in instance_tags)
        return self.add(Hole(id, _tags(tags), on, at, spec, extent, inst, expect))

    # evaluation --------------------------------------------------------------------
    def resolve_params(self, values: dict | None = None, **overrides) -> dict:
        vals = self.defaults()
        for k, v in {**(values or {}), **overrides}.items():
            if k not in self.params:
                raise ParameterError(f"unknown parameter {k!r}; declared: {sorted(self.params)}")
            p = self.params[k]
            if p.choices is None and isinstance(v, str):
                v = float(v)
            try:
                vals[k] = p.validate(v)
            except ValueError as e:
                raise ParameterError(str(e)) from None
        return vals

    def build(self, values: dict | None = None, *, on_fail: str = "raise", interpretations: dict | None = None,
              prefs=None, **overrides) -> Build:
        """Evaluate the design: parameters -> Build.  Pure: a fresh Context every call.

        interpretations: {slot id: reading} for ambiguous intent-word slots (architecture
                         §10.2).  Default: the design's lock (`use_lock`), else each slot's
                         ranked default, unchecked (reported as such).

        on_fail="raise"  raise the first DipmError (invariant, reference, kernel ...).
        on_fail="record" record failures in the Build and keep going while the solid is
                         usable (stops after a kernel failure or an invalid/null solid).
        """
        params = self.resolve_params(values, **overrides)
        interp, source = None, "explicit"
        if interpretations is None:
            interp = self.ensure_interpretations()
            interpretations, source = (self.interpretations or {}), self._interp_source
            prefs = prefs if prefs is not None else self.prefs
        ctx = Context(self, params, interpretations, prefs, interp.made_by if interp is not None else None)
        records, errors = [], []
        t_all = time.perf_counter()
        for f in self.features:
            ctx.current_feature, ctx.current_intent = f.id, f.tags
            n_res = len(ctx.resolutions)
            rec = FeatureRecord(f.id, f.op_name, getattr(f, "lowered_from", None), f.tags, {},
                                byte_deterministic=True)
            records.append(rec)
            t0 = time.perf_counter()
            before = ctx.shape
            try:
                out = f.apply(ctx)
            except DipmError as e:
                if e.feature is None:
                    e.feature, e.intent = f.id, f.tags
                    e.args = (e.render(),)
                rec.error = e
                rec.inputs = ctx.resolutions[n_res:]
                errors.append(e)
                if on_fail == "raise":
                    raise
                break
            except Exception as e:  # kernel raised: failure class "fails loudly"
                err = KernelError(f"{type(e).__name__}: {e}", feature=f.id, intent=f.tags)
                rec.error = err
                errors.append(err)
                if on_fail == "raise":
                    raise err from e
                break
            rec.lowered_from = out.lowered_from or rec.lowered_from
            rec.op = out.op or rec.op
            rec.instance_tags = dict(out.instance_tags)
            rec.byte_deterministic = out.byte_deterministic
            rec.detail = dict(out.detail)
            rec.expect = out.expect
            rec.inputs = ctx.resolutions[n_res:]
            prev = records[-2].checks if len(records) > 1 else None
            rec.checks = run_feature_invariants(f.id, before, out.shape, out.expect, prev)
            rec.ms = (time.perf_counter() - t0) * 1000
            if not rec.checks.ok:
                fails = rec.checks.failures()
                first = fails[0]
                err = InvariantError(
                    "; ".join(f"{c.name}" + (f": {c.note}" if c.note else "") for c in fails),
                    feature=f.id, intent=f.tags, invariant=first.name, expected=first.expected, got=first.got,
                    details={"all failures": [str(c) for c in fails], "op": rec.op,
                             **({"lowered from": rec.lowered_from} if rec.lowered_from else {})})
                rec.error = err
                errors.append(err)
                if on_fail == "raise":
                    raise err
                if any(c.name in ("validity", "euler") for c in fails):
                    ctx.shape = out.shape
                    break
            ctx.shape = out.shape
        build = Build(self, params, ctx.shape, ctx.ledger, records, {}, errors, slots=ctx.slot_uses,
                      interpretation=interp, interpretation_source=source if interp is not None else "")
        # exports, resolved on the final solid
        if ctx.shape is not None and not any(isinstance(e, KernelError) for e in errors):
            ctx.current_feature, ctx.current_intent = "<exports>", ()
            for name, ref in self.exports.items():
                try:
                    ctx.resolve(ref)
                    build.exports[name] = ctx.resolutions[-1]   # derived refs resolve inputs first
                except DipmError as e:
                    e.details["export"] = name
                    e.args = (e.render(),)
                    errors.append(e)
                    build.exports[name] = e
                    if on_fail == "raise":
                        raise
            build.signature = signature(ctx.shape, ctx.ledger)
        build.ms = (time.perf_counter() - t_all) * 1000
        return build


@dataclass
class StepOut:
    """What a feature's `apply` returns to the evaluator."""
    shape: object
    expect: object
    op: str | None = None
    lowered_from: str | None = None
    instance_tags: dict = field(default_factory=dict)
    byte_deterministic: bool = True
    detail: dict = field(default_factory=dict)
