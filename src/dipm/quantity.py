"""Quantities with ranges and worst-case propagation (tolerance-uncertainty.md §2; gui.md 3E.2).

A `Quantity` is a nominal value plus a closed range [lo, hi] and where the range came from
(a rule pack, a component's datasheet, an assumption).  Checks combine quantities with an
ordinary Python function; `propagate` gives the nominal result and the extremes.

**Worst case is the default** (decided in tolerance §2): every corner of the input box is
evaluated (2^n evaluations for n ranged inputs) and the extremes are taken.  That is exact
for functions monotone in each input, which every v0 check is (products, quotients and sums
of positive quantities, distances shifted by a tolerance); a non-monotone check would need
interval arithmetic or a search, and must say so.

**Sampling is opt-in and not built.**  `propagate(..., method="sample")` is the hook: it looks
up a sampler registered with `register_sampler` and otherwise raises.  A sampler must use a
fixed seed so results stay repeatable (tolerance §2).
"""
from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass
from typing import Callable

MAX_CORNERS = 4096    # 12 ranged inputs


@dataclass(frozen=True)
class Quantity:
    nominal: float
    lo: float
    hi: float
    unit: str = ""
    source: str = ""          # e.g. "fdm_printing.position_tolerance", "R.a1", "geometry"
    made_by: str = "pack default"   # model | user | pack default | author | engine (architecture §4.8)
    label: str = ""
    placeholder: bool = False

    def __post_init__(self):
        if not (self.lo <= self.nominal <= self.hi):
            raise ValueError(f"quantity {self.label or self.source}: nominal {self.nominal} outside [{self.lo}, {self.hi}]")

    @property
    def ranged(self) -> bool:
        return self.lo != self.hi

    @classmethod
    def exact(cls, v: float, unit: str = "", source: str = "geometry", label: str = "", made_by: str = "engine"):
        return cls(float(v), float(v), float(v), unit, source, made_by, label)

    @classmethod
    def pm(cls, v: float, tol: float, unit: str = "", source: str = "", label: str = "", made_by: str = "pack default",
           placeholder: bool = False):
        return cls(float(v), float(v) - abs(tol), float(v) + abs(tol), unit, source, made_by, label, placeholder)

    @classmethod
    def from_pack(cls, entry: dict, source: str, label: str = "", scale: float = 1.0, made_by: str = "pack default"):
        return cls(entry["value"] * scale, entry["lo"] * scale, entry["hi"] * scale, entry.get("unit", ""), source,
                   made_by, label, bool(entry.get("placeholder")))

    def as_dict(self) -> dict:
        return asdict(self)


Sampler = Callable[[Callable, dict, dict], dict]
_SAMPLERS: dict = {}


def register_sampler(name: str, fn: Sampler) -> None:
    """Hook for opt-in Monte Carlo propagation (tolerance §2).  `fn(f, inputs, options)` must
    return {"nominal", "lo", "hi", "failure_fraction"?} with a fixed seed.  None ships yet."""
    _SAMPLERS[name] = fn


@dataclass
class Propagated:
    nominal: float
    lo: float
    hi: float
    at_lo: dict          # input values at the corner giving `lo`
    at_hi: dict
    method: str
    evaluations: int


def corners(inputs: dict):
    """Every corner of the input box, as {name: value}; unranged inputs stay at nominal."""
    names = list(inputs)
    choices = [(q.lo, q.hi) if q.ranged else (q.nominal,) for q in (inputs[n] for n in names)]
    n = 1
    for c in choices:
        n *= len(c)
    if n > MAX_CORNERS:
        raise ValueError(f"{n} corners: too many ranged inputs for worst-case corner evaluation")
    for combo in itertools.product(*choices):
        yield dict(zip(names, combo))


def propagate(fn: Callable[..., float], inputs: dict, method: str = "worst_case", **options) -> Propagated:
    """Nominal value and extremes of `fn(**values)` over the ranges of `inputs` (name -> Quantity)."""
    if method != "worst_case":
        s = _SAMPLERS.get(method)
        if s is None:
            raise NotImplementedError(f"propagation method {method!r} is not built: worst case is the default; "
                                      "opt-in sampling is a hook only (register_sampler, tolerance §2)")
        r = s(fn, inputs, options)
        return Propagated(r["nominal"], r["lo"], r["hi"], {}, {}, method, r.get("evaluations", 0))
    nom = {k: q.nominal for k, q in inputs.items()}
    v0 = float(fn(**nom))
    lo = hi = v0
    at_lo = at_hi = nom
    k = 1
    for c in corners(inputs):
        v = float(fn(**c))
        k += 1
        if v < lo:
            lo, at_lo = v, c
        if v > hi:
            hi, at_hi = v, c
    return Propagated(v0, lo, hi, at_lo, at_hi, "worst_case", k)


def worst_margin(value_fn: Callable[..., float], limit_fn: Callable[..., float], sense: str, inputs: dict) -> dict:
    """Nominal and worst-case margin of `value sense limit` (sense '<=' or '>=') when the value
    and the limit share one input box: the worst corner is the one minimising the margin."""
    if sense not in ("<=", ">="):
        raise ValueError("sense must be '<=' or '>='")

    def margin(**x):
        v, lim = float(value_fn(**x)), float(limit_fn(**x))
        return lim - v if sense == "<=" else v - lim

    p = propagate(margin, inputs)
    worst = p.at_lo
    return {"nominal": float(value_fn(**{k: q.nominal for k, q in inputs.items()})),
            "limit": float(limit_fn(**{k: q.nominal for k, q in inputs.items()})),
            "worst": float(value_fn(**worst)), "limit_worst": float(limit_fn(**worst)),
            "margin": p.nominal, "margin_worst": p.lo, "worst_inputs": worst, "evaluations": p.evaluations,
            "method": f"worst case over {p.evaluations - 1} corner(s) of the input ranges"}
