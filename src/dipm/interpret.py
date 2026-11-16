"""Interpretations: resolving ambiguous intent words (architecture §10 item 2, §4.8).

Some intent words leave a choice open.  "Hole through the plate": through *what*?  "Centred
on the face": the face's centroid, or the middle of the part of it you can still see?  The
designer can't be asked about every one of these, so each ambiguous **slot** of an intent
word declares its candidate **readings**, and the system decides as follows.

1. **Declare readings.**  A `ReadingSet` (word + slot) lists `Reading`s in a fixed order:
   name, one-line rationale, package prior rank (1 = package default), and an MDL proxy
   (`complexity`: how many references the lowering reads).  The lowering itself lives with
   the intent word (`intent_layer.py`).  A value the author gives explicitly bypasses all
   of this and is recorded as `made_by: author`.
2. **Eliminate by checks.**  `resolve()` lowers every reading of every slot and builds the
   design at every stability sample point of the declared parameter ranges
   (`stability.default_points`).  A reading that fails any invariant (validity, Euler,
   ΔH/ΔS, volume sign, reference cardinality, interaction, placement preconditions) at any
   point is eliminated, with the feature, check and parameter point recorded.  A failure
   counts against a reading only if this slot can be blamed for it: at the slot's own
   feature, unless every reading fails the same way there; at a later feature, only if
   another reading of the slot got past that feature at the same point.
3. **Measure whether it matters.**  Surviving readings are compared point by point on
   (V,E,F,R,S,H), the order-free role-geometry fingerprint and volume.  Identical everywhere
   means sensitivity `none`: nobody is asked.  Otherwise `grade_sensitivity` grades it.
4. **Ranked default.**  (1) a user/house preference; (2) the package prior; (3) the
   simplest relation (lowest `complexity`); (4) a learned-prior hook (stub).
5. **Record** each slot as an `Assumption` (§4.8 fields plus chosen reading, alternatives,
   eliminations and sensitivity).
6. **Ask only when it matters**: a `Question` only when >= 2 readings survive, they diverge
   within range, and no preference decides.  When the package default is eliminated and
   another reading survives, a non-blocking "default overridden" `Notice` is raised with
   high sensitivity: nothing intent-level (e.g. tool access, NOTES TODO 4) has verified
   the survivor.
7. **Remember answers** in a JSON `Preferences` file, keyed by word + slot + context.

Slots are resolved one at a time in build order, with every other slot at its current
choice (Gauss-Seidel), repeated until no choice changes.  The full product of slot readings
is never explored (NOTES DECISIONS #26).  The result is written to a lock file next to the
design so ordinary builds stay fast and deterministic (architecture §7).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import warnings
from dataclasses import asdict, dataclass, field
from typing import Callable

# ---------------------------------------------------------------- readings

MADE_BY_AUTHOR = "author"
MADE_BY_USER = "user preference"
MADE_BY_PACK = "pack default"
MADE_BY_MODEL = "model"


@dataclass(frozen=True)
class Reading:
    """One candidate meaning of an ambiguous slot.

    prior:       package prior rank; 1 is the package default (None = no opinion).
    complexity:  MDL proxy, the number of geometric references the lowering reads
                 (face only = 1; face + attached material = 2; ...).  Lower is simpler.
    opt_in:      offered only when the author lists it in `consider=` (it adds a coupling
                 the intent word does not imply by itself).
    """
    name: str
    rationale: str
    prior: int | None = None
    complexity: int = 1
    opt_in: bool = False


@dataclass(frozen=True)
class ReadingSet:
    """The readings an intent word declares for one of its slots, in a fixed order."""
    word: str
    slot: str
    readings: tuple
    explicit_only: tuple = ()      # values an author may give but that are never guessed, e.g. blind(depth)
    doc: str = ""

    def get(self, name: str) -> Reading | None:
        return next((r for r in self.readings if r.name == name), None)

    def offered(self, consider=()) -> tuple:
        return tuple(r for r in self.readings if not r.opt_in or r.name in consider)

    @property
    def package_default(self) -> Reading:
        return min(self.readings, key=lambda r: (r.prior if r.prior is not None else math.inf))


READING_SETS: dict = {}


def register(rs: ReadingSet) -> ReadingSet:
    READING_SETS[(rs.word, rs.slot)] = rs
    return rs


def readings_digest() -> str:
    """Changes whenever any registered reading table changes (part of the lock key)."""
    blob = json.dumps([[k, [(r.name, r.prior, r.complexity, r.opt_in) for r in rs.readings]]
                       for k, rs in sorted(READING_SETS.items())])
    return hashlib.sha256(blob.encode()).hexdigest()


# ---------------------------------------------------------------- learned prior (hook only)

LearnedPrior = Callable[[dict, tuple], "dict | None"]
_learned_prior: LearnedPrior | None = None


def set_learned_prior(fn: LearnedPrior | None) -> None:
    """Interface stub for architecture §10.2's learned prior ("which reading designers usually
    mean").  `fn(context, readings) -> {reading name: score}` (higher = more likely) or None.
    It ranks *after* preference, package prior and simplicity.  Nothing ships one yet."""
    global _learned_prior
    _learned_prior = fn


def rank(readings, preferred: str | None = None, context: dict | None = None) -> list:
    """Ranked default (architecture §10.2): preference, package prior, simplest, learned prior,
    then declaration order (so ranking is total and deterministic)."""
    lp = (_learned_prior(context or {}, tuple(readings)) if _learned_prior else None) or {}
    order = {r.name: i for i, r in enumerate(readings)}
    return sorted(readings, key=lambda r: (0 if r.name == preferred else 1,
                                           r.prior if r.prior is not None else math.inf,
                                           r.complexity, -lp.get(r.name, 0.0), order[r.name]))


# ---------------------------------------------------------------- preferences ("remember the answer")

class Preferences:
    """Remembered answers, a small JSON file (user- or project-level, passed with --prefs).

    Keys are `<word>.<slot>@<context>`, looked up most specific first:
      `hole.extent@shelf_bracket:A.3`   this design, this intent node
      `hole.extent@shelf_bracket:*`     this design, every node
      `hole.extent@*`                   house default for the word, every design
    The intent-node id (not the feature id) is the design-specific context, so the answer
    follows the intent if features are renamed.  Two slots of the same word at the same node
    share one answer: "never ask twice for the same thing".
    """

    def __init__(self, path: str | None = None, answers: dict | None = None):
        self.path = path
        self.answers = dict(answers or {})

    @classmethod
    def load(cls, path: str | None) -> "Preferences":
        if not path or not os.path.exists(path):
            return cls(path)
        with open(path) as fh:
            data = json.load(fh)
        return cls(path, data.get("answers", {}))

    def save(self) -> None:
        if not self.path:
            raise ValueError("no preferences path")
        with open(self.path, "w") as fh:
            json.dump({"dipm_preferences": 1, "answers": dict(sorted(self.answers.items()))}, fh, indent=2)
            fh.write("\n")

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.answers, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def contexts(design: str, node: str) -> list:
        return [f"{design}:{node}", f"{design}:*", "*"]

    def lookup(self, word: str, slot: str, design: str, node: str) -> tuple | None:
        """(reading name, key) of the most specific remembered answer, or None."""
        for c in self.contexts(design, node):
            key = f"{word}.{slot}@{c}"
            if key in self.answers:
                return self.answers[key]["reading"], key
        return None

    def record(self, word: str, slot: str, context: str, reading: str, note: str = "") -> str:
        key = f"{word}.{slot}@{context}"
        self.answers[key] = {"reading": reading, **({"note": note} if note else {})}
        return key


# ---------------------------------------------------------------- slot use (recorded during a build)

@dataclass(frozen=True)
class SlotUse:
    """One ambiguous (or explicitly given) slot met while building a feature."""
    id: str                 # "<feature id>/<word>.<slot>", e.g. "A.3.cable/hole.extent"
    word: str
    slot: str
    feature: str
    node: str               # intent node of the feature (first intent tag), for preference keys
    offered: tuple          # reading names offered, in declaration order ((), if explicit)
    reading: str            # the reading used (or the explicit value's text)
    made_by: str
    source: str             # "author" | "choices" (lock / resolution) | "unchecked default"


def choose(ctx, rs: ReadingSet, explicit: str | None = None, consider=(), key: str = "") -> Reading | None:
    """Called by an intent word while lowering (via `Context.interpret`).  Returns the Reading
    to lower, or None when the author gave an explicit non-reading value (e.g. through(5))."""
    feature = ctx.current_feature
    base = f"{feature}/{rs.word}.{rs.slot}"
    keys = ctx.slot_keys.setdefault(base, [])
    if key not in keys:
        keys.append(key)
    i = keys.index(key)
    sid = base if i == 0 else f"{base}#{i + 1}"
    node = ctx.current_intent[0].node if ctx.current_intent else feature
    if explicit is not None:
        rd = rs.get(explicit)
        use = SlotUse(sid, rs.word, rs.slot, feature, node, (), explicit, MADE_BY_AUTHOR, "author")
    else:
        offered = rs.offered(consider)
        name = ctx.choices.get(sid)
        if name is not None and any(r.name == name for r in offered):
            source = "choices"
            made_by = ctx.choice_made_by.get(sid, MADE_BY_MODEL)
        else:   # not resolved yet: ranked default, unchecked
            pref = ctx.prefs.lookup(rs.word, rs.slot, ctx.design.name, node) if ctx.prefs else None
            ranked = rank(offered, pref[0] if pref else None)
            name, source = ranked[0].name, "unchecked default"
            made_by = MADE_BY_USER if pref and pref[0] == name else (
                MADE_BY_PACK if name == rs.package_default.name else MADE_BY_MODEL)
        rd = rs.get(name)
        use = SlotUse(sid, rs.word, rs.slot, feature, node, tuple(r.name for r in offered), name, made_by, source)
    if all(u.id != sid for u in ctx.slot_uses):
        ctx.slot_uses.append(use)
    return rd


# ---------------------------------------------------------------- records (architecture §4.8)

@dataclass
class Elimination:
    reading: str
    feature: str
    check: str
    point: dict             # parameters that differ from the defaults ({} = defaults)
    message: str
    failed_points: int
    of_points: int

    def __str__(self):
        return (f"{self.reading}: fails {self.check} at {self.feature} at {_fmt_point(self.point)}"
                f" ({self.failed_points}/{self.of_points} points): {self.message}")


@dataclass
class Assumption:
    """An interpretation recorded as an assumption (architecture §4.8)."""
    id: str
    word: str
    slot: str
    feature: str
    node: str
    statement: str
    chosen: str
    made_by: str
    rationale: str
    status: str                       # proposed | accepted
    sensitivity: str                  # none | low | medium | high | n/a (explicit)
    sensitivity_detail: str = ""
    readings: list = field(default_factory=list)
    alternatives: list = field(default_factory=list)       # surviving readings not chosen
    eliminated: list = field(default_factory=list)         # Elimination as dicts
    supports: list = field(default_factory=list)           # what depends on it (the feature)


@dataclass
class Question:
    id: str
    text: str
    options: list                     # [{"reading", "rationale", "effect"}]
    default: str
    answer_with: str


@dataclass
class Notice:
    id: str
    kind: str                         # default_overridden | preference_overridden | undecidable | no_survivor | not_converged
    text: str
    sensitivity: str = "high"


@dataclass
class Interpretation:
    """Result of `resolve()`; also the lock file's content."""
    design: str
    choices: dict
    assumptions: list
    questions: list
    notices: list
    sample_points: list
    key: dict = field(default_factory=dict)
    prefs: str | None = None          # preferences file the resolution used (path relative to the lock)
    stats: dict = field(default_factory=dict)

    @property
    def made_by(self) -> dict:
        return {a.id: a.made_by for a in self.assumptions}

    def assumption(self, aid: str) -> Assumption:
        for a in self.assumptions:
            if a.id == aid:
                return a
        raise KeyError(f"no assumption {aid!r}; known: {[a.id for a in self.assumptions]}")

    def to_json(self) -> str:
        d = {"dipm_interpretations": 1, "design": self.design, "key": self.key, "prefs": self.prefs,
             "sample_points": self.sample_points, "choices": self.choices,
             "assumptions": [asdict(a) for a in self.assumptions],
             "questions": [asdict(q) for q in self.questions],
             "notices": [asdict(n) for n in self.notices]}
        return json.dumps(d, indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "Interpretation":
        d = json.loads(text)
        return cls(d["design"], d["choices"], [Assumption(**a) for a in d["assumptions"]],
                   [Question(**q) for q in d["questions"]], [Notice(**n) for n in d["notices"]],
                   d["sample_points"], d.get("key", {}), d.get("prefs"))


def _fmt_point(p: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in p.items()) or "(defaults)"


# ---------------------------------------------------------------- one build at one point, summarized

@dataclass
class _Outcome:
    fail: tuple | None          # (feature index, feature, check, message) of the first failure
    vefrsh: tuple | None
    roles: str | None
    volume: float | None
    slots: tuple


def _summarize(design, b) -> _Outcome:
    idx = {f.id: i for i, f in enumerate(design.features)}
    fail = None
    if b.errors:
        e = b.errors[0]
        feat = e.feature or "?"
        check = e.invariant or type(e).__name__
        fail = (idx.get(feat, len(design.features)), feat, check, " ".join(str(e.message).split())[:200])
    sig = b.signature
    return _Outcome(fail, sig.VEFRSH if sig else None, sig.roles_geom if sig else None,
                    sig.volume if sig else None, tuple(b.slots))


def sample_points(design) -> list:
    """The fixed stability sample points (defaults first), the same ones the harness sweeps."""
    from .stability import default_points
    base = design.defaults()
    pts = [base] + [p for p in default_points(design) if p != base]
    return pts


# ---------------------------------------------------------------- sensitivity

def grade_sensitivity(n_diff: int, n_points: int, max_dv_rel: float, topology_differs: bool) -> str:
    """How much the choice matters within the declared ranges (NOTES DECISIONS #25).

      none    survivors identical (VEFRSH, role-geometry fingerprint, volume) at every point
      high    topology (V,E,F,R,S,H) differs anywhere, or volume differs by >= 1 %
      medium  differs at >= half the points, or volume differs by >= 0.1 %
      low     otherwise (e.g. a small move at a few points)
    """
    if n_diff == 0:
        return "none"
    if topology_differs or max_dv_rel >= 0.01:
        return "high"
    if n_diff * 2 >= n_points or max_dv_rel >= 0.001:
        return "medium"
    return "low"


# ---------------------------------------------------------------- resolution

class _Runner:
    """Builds the design for (choices, point), memoized: deterministic and shared across slots."""

    def __init__(self, design, prefs):
        self.design, self.prefs, self.cache, self.builds = design, prefs, {}, 0

    def __call__(self, choices: dict, point: dict) -> _Outcome:
        k = (tuple(sorted(choices.items())), tuple(sorted((n, repr(v)) for n, v in point.items())))
        if k not in self.cache:
            b = self.design.build(point, on_fail="record", interpretations=dict(choices), prefs=self.prefs)
            self.builds += 1
            self.cache[k] = _summarize(self.design, b)
        return self.cache[k]


def resolve(design, prefs: Preferences | None = None, points: list | None = None,
            initial: dict | None = None, max_passes: int = 4) -> Interpretation:
    """Resolve every ambiguous slot of `design` (architecture §10.2).  Deterministic: fixed slot
    order (build order), fixed reading order, fixed sample points, memoized builds."""
    prefs = prefs or Preferences()
    points = points if points is not None else sample_points(design)
    base = design.defaults()
    run = _Runner(design, prefs)
    choices: dict = dict(initial or {})
    slots: dict = {}            # sid -> SlotUse, first seen
    seen_order: dict = {}
    results: dict = {}
    converged = False

    def note_slots(o: _Outcome):
        for u in o.slots:
            if u.id not in slots:
                slots[u.id] = u
                seen_order[u.id] = len(seen_order)

    fidx = {f.id: i for i, f in enumerate(design.features)}
    for _ in range(max_passes):
        n_before = len(slots)
        note_slots(run(choices, base))
        changed = False
        for sid in sorted(slots, key=lambda s: (fidx.get(slots[s].feature, 0), seen_order[s])):
            u = slots[sid]
            if u.made_by == MADE_BY_AUTHOR:
                continue
            res = _analyse(design, u, choices, points, prefs, run, note_slots)
            results[sid] = res
            if choices.get(sid) != res["chosen"]:
                choices[sid] = res["chosen"]
                changed = True
        if not changed and len(slots) == n_before:
            converged = True
            break
    ordered = sorted(slots, key=lambda s: (fidx.get(slots[s].feature, 0), seen_order[s]))
    assumptions, questions, notices = [], [], []
    for sid in ordered:
        u = slots[sid]
        if u.made_by == MADE_BY_AUTHOR:
            assumptions.append(Assumption(
                sid, u.word, u.slot, u.feature, u.node,
                f"{u.feature}: {u.word} {u.slot} given explicitly as {u.reading}", u.reading, MADE_BY_AUTHOR,
                "explicit in the design; not interpreted", "accepted", "n/a", supports=[u.feature]))
            continue
        r = results[sid]
        assumptions.append(r["assumption"])
        questions += r["questions"]
        notices += r["notices"]
    if not converged:
        notices.append(Notice("*", "not_converged",
                              f"slot choices still changing after {max_passes} passes; results may depend on order"))
    final = {sid: choices[sid] for sid in ordered if sid in choices and slots[sid].made_by != MADE_BY_AUTHOR}
    return Interpretation(design.name, final, assumptions, questions, notices,
                          [{k: v for k, v in p.items() if base.get(k) != v} for p in points],
                          stats={"builds": run.builds})


def _analyse(design, u: SlotUse, choices: dict, points: list, prefs: Preferences, run, note_slots) -> dict:
    """Eliminate, measure sensitivity, rank and record one slot (others at their current choice)."""
    from .intent_layer import reading_set   # the word's reading table
    rs = reading_set(u.word, u.slot)
    offered = [rs.get(n) for n in u.offered]
    own = {f.id: i for i, f in enumerate(design.features)}[u.feature]
    base = design.defaults()
    outs = {}
    for r in offered:
        outs[r.name] = []
        for p in points:
            o = run({**choices, u.id: r.name}, p)
            note_slots(o)
            outs[r.name].append(o)
    # --- 2. eliminate by checks
    eliminated: dict = {}
    undecidable = None
    for r in offered:
        fails = []
        for i, p in enumerate(points):
            f = outs[r.name][i].fail
            if f is None or f[0] < own:
                continue          # earlier features cannot depend on this slot
            others = [outs[o.name][i].fail for o in offered if o is not r]
            if f[0] == own:
                # at the slot's own feature: blame the reading unless every reading fails the same way
                if not others or all(of is not None and of[1:3] == f[1:3] for of in others):
                    undecidable = undecidable or (f, p)
                    continue
            elif not any(of is None or of[0] > f[0] for of in others):
                continue          # downstream: blame it only if another reading got past that feature
            fails.append((i, f))
        if fails:
            i, f = fails[0]
            pt = {k: v for k, v in points[i].items() if base.get(k) != v}
            eliminated[r.name] = Elimination(r.name, f[1], f[2], pt, f[3], len(fails), len(points))
    survivors = [r for r in offered if r.name not in eliminated]
    # --- 4. ranked default
    pref = prefs.lookup(u.word, u.slot, design.name, u.node)
    pref_ok = bool(pref) and any(r.name == pref[0] for r in survivors)
    pool = survivors or offered
    ctx_info = {"design": design.name, "word": u.word, "slot": u.slot, "node": u.node, "feature": u.feature}
    chosen = rank(pool, pref[0] if pref_ok else None, ctx_info)[0]
    pack = rs.package_default
    if pref_ok:
        made_by, why = MADE_BY_USER, f"remembered answer ({pref[1]})"
    elif chosen.name == pack.name:
        made_by, why = MADE_BY_PACK, f"package default: {chosen.rationale}"
    else:
        made_by = MADE_BY_MODEL
        why = (f"package default '{pack.name}' eliminated; next by prior/simplicity: {chosen.rationale}"
               if pack.name in eliminated else f"ranked first by prior/simplicity: {chosen.rationale}")
    # --- 3. sensitivity among survivors
    n_diff, max_dv, topo = set(), 0.0, False
    per_alt = {}
    for o in survivors:
        if o is chosen:
            continue
        d_o = 0
        for i in range(len(points)):
            a, b = outs[chosen.name][i], outs[o.name][i]
            dv = 0.0 if (a.volume is None or b.volume is None) else abs(a.volume - b.volume) / max(abs(a.volume), 1e-9)
            if (a.vefrsh, a.roles) != (b.vefrsh, b.roles) or dv > 1e-9:
                n_diff.add(i)
                d_o += 1
                max_dv = max(max_dv, dv)
                topo = topo or a.vefrsh != b.vefrsh
        per_alt[o.name] = d_o
    sens = grade_sensitivity(len(n_diff), len(points), max_dv, topo)
    detail = ("survivors identical at every sample point" if len(survivors) > 1 and not n_diff else
              "only one reading survives" if len(survivors) == 1 else
              "no reading survives" if not survivors else
              f"survivors differ at {len(n_diff)}/{len(points)} points, max |ΔV|/V = {max_dv:.3g}"
              + (", topology differs" if topo else ""))
    notices, questions = [], []
    if not survivors:
        notices.append(Notice(u.id, "no_survivor",
                              f"{u.feature}: every reading of {u.word} {u.slot} fails a check; using "
                              f"'{chosen.name}' and the build will fail. " + "; ".join(str(e) for e in eliminated.values())))
    elif pack.name in eliminated and chosen.name != pack.name and made_by != MADE_BY_USER:
        sens = "high"
        detail = f"package default overridden; {detail}"
        notices.append(Notice(u.id, "default_overridden",
                              f"{u.feature}: package default '{pack.name}' for {u.word} {u.slot} was eliminated "
                              f"({eliminated[pack.name]}); using '{chosen.name}'. No intent-level check (e.g. tool "
                              f"access; NOTES TODO 4) has confirmed '{chosen.name}' is what the design means."))
    if pref and not pref_ok:
        notices.append(Notice(u.id, "preference_overridden",
                              f"{u.feature}: remembered answer '{pref[0]}' ({pref[1]}) "
                              + (f"was eliminated ({eliminated[pref[0]]})" if pref[0] in eliminated
                                 else "is not an offered reading") + f"; using '{chosen.name}'"))
    if undecidable and survivors:
        f, p = undecidable
        notices.append(Notice(u.id, "undecidable",
                              f"{u.feature}: every reading of {u.word} {u.slot} fails {f[2]} at "
                              f"{_fmt_point({k: v for k, v in p.items() if base.get(k) != v})}; "
                              f"not decidable by this slot", "n/a"))
    if len(survivors) >= 2 and n_diff and not pref_ok:
        opts = [{"reading": r.name, "rationale": r.rationale,
                 "effect": "default" if r is chosen else f"differs from the default at {per_alt[r.name]}/{len(points)} points"}
                for r in survivors]
        questions.append(Question(
            u.id, f"{u.feature} ({u.node}): which meaning of {u.word} {u.slot}? "
                  f"{len(survivors)} readings pass every check but give different geometry ({detail}).",
            opts, chosen.name,
            f"python -m dipm answer <design.py> {u.id} <reading> --prefs <prefs.json>"))
    status = "accepted" if made_by == MADE_BY_USER else "proposed"
    a = Assumption(u.id, u.word, u.slot, u.feature, u.node,
                   f"{u.feature}: {u.word} {u.slot} read as '{chosen.name}' ({chosen.rationale})",
                   chosen.name, made_by, why, status, sens, detail, [r.name for r in offered],
                   [r.name for r in survivors if r is not chosen],
                   [asdict(e) for e in eliminated.values()], [u.feature])
    return {"chosen": chosen.name, "assumption": a, "questions": questions, "notices": notices}


# ---------------------------------------------------------------- lock file

def lock_path_for(design_file: str) -> str:
    """`examples/shelf_bracket.py` -> `examples/shelf_bracket.interpretations.json`."""
    root, _ = os.path.splitext(design_file)
    return root + ".interpretations.json"


def lock_key(design_file: str, prefs: Preferences) -> dict:
    """What a lock is valid for: the design source, the preferences, the reading tables."""
    from . import __version__
    with open(design_file, "rb") as fh:
        src = hashlib.sha256(fh.read()).hexdigest()
    return {"design_source_sha256": src, "prefs_sha256": prefs.digest(),
            "readings_sha256": readings_digest(), "dipm": __version__}


def read_lock(path: str) -> Interpretation | None:
    if not path or not os.path.exists(path):
        return None
    with open(path) as fh:
        return Interpretation.from_json(fh.read())


def write_lock(interp: Interpretation, path: str) -> None:
    with open(path, "w") as fh:
        fh.write(interp.to_json())


@dataclass
class LockSpec:
    design_file: str
    lock: str
    prefs: str | None = None


def prefs_path_from_lock(spec: LockSpec) -> str | None:
    if spec.prefs:
        return spec.prefs
    lk = read_lock(spec.lock)
    if lk and lk.prefs:
        return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(spec.lock)), lk.prefs))
    return None


def load_or_resolve(design, spec: LockSpec, force: bool = False) -> tuple:
    """(Interpretation, Preferences, fresh?).  A fresh lock is read as-is (fast path); a missing
    or stale one is re-resolved in memory, starting from its choices, with a warning."""
    prefs = Preferences.load(prefs_path_from_lock(spec))
    key = lock_key(spec.design_file, prefs)
    lk = read_lock(spec.lock)
    if lk is not None and lk.key == key and not force:
        return lk, prefs, True
    if not force:
        warnings.warn(f"{spec.lock}: {'missing' if lk is None else 'stale'}; resolving interpretations in "
                      f"memory (run `python -m dipm interpret {spec.design_file}` to update it)", stacklevel=3)
    interp = resolve(design, prefs, initial=lk.choices if lk else None)
    interp.key = key
    if prefs.path:
        interp.prefs = os.path.relpath(os.path.abspath(prefs.path), os.path.dirname(os.path.abspath(spec.lock)))
    return interp, prefs, False


# ---------------------------------------------------------------- report text

def format_interpretation(interp: Interpretation | None, slot_uses=(), source: str = "") -> list:
    """Lines for the build report's "Interpretations" section."""
    L = []
    if interp is None:
        if not slot_uses:
            return L
        L.append("Interpretations: UNCHECKED (no lock / resolution; package defaults used; run `dipm interpret`)")
        for u in slot_uses:
            L.append(f"  {u.id}: {u.reading}   [{u.made_by}; {u.source}]")
        return L
    nq, nn = len(interp.questions), len(interp.notices)
    L.append(f"Interpretations ({len(interp.assumptions)} slot(s), {nq} question(s), {nn} notice(s)"
             + (f"; {source}" if source else "") + "):")
    for a in interp.assumptions:
        L.append(f"  {a.id}  -> {a.chosen}   [made_by: {a.made_by}; status: {a.status}; sensitivity: {a.sensitivity}]")
        if a.made_by != MADE_BY_AUTHOR:
            L.append(f"      why: {a.rationale}")
            if a.alternatives:
                L.append(f"      also survives: {', '.join(a.alternatives)}  ({a.sensitivity_detail})")
            elif a.sensitivity_detail:
                L.append(f"      {a.sensitivity_detail}")
            for e in a.eliminated:
                L.append(f"      eliminated {Elimination(**e)}")
    used = {u.id: u for u in slot_uses}
    for a in interp.assumptions:
        u = used.get(a.id)
        if u is not None and u.made_by != MADE_BY_AUTHOR and u.reading != a.chosen:
            L.append(f"  NOTE {a.id}: this build used '{u.reading}', the record says '{a.chosen}'")
    for n in interp.notices:
        L.append(f"  NOTICE [{n.kind}] {n.text}")
    for q in interp.questions:
        L.append(f"  QUESTION {q.id}: {q.text}")
        for o in q.options:
            L.append(f"      - {o['reading']}: {o['rationale']}  [{o['effect']}]")
        L.append(f"      answer: {q.answer_with}")
    return L
