"""Lazy expressions over design parameters.

A design never stores the *number* for a dimension; it stores an expression such as
`0.75 * shelf_depth`, evaluated against a parameter set at build time.  That is what
makes evaluation a pure function (parameters -> result) and lets edit tests re-evaluate
with new values (architecture.md §2.2 "literal numbers appear only for true design
parameters", §6 "relations vs. literals").

Anything with an `evaluate(env)` method is lazy; `ev(x, env)` evaluates it or returns a
literal unchanged.  `env` is the evaluation context (`program.Context`), which exposes
`env.params` (name -> value) and, for geometric relations, the current solid and ledger.
"""
from __future__ import annotations

import math
import operator
from dataclasses import dataclass, field
from typing import Any, Callable


def ev(x, env):
    """Evaluate a lazy value (Expr, placement, reference ...) or return a literal as-is."""
    if hasattr(x, "evaluate"):
        return x.evaluate(env)
    if isinstance(x, tuple):
        return tuple(ev(i, env) for i in x)
    if isinstance(x, list):
        return [ev(i, env) for i in x]
    return x


class Expr:
    """Base class: arithmetic on Exprs builds a tree; nothing is computed until `evaluate`."""

    def evaluate(self, env):  # pragma: no cover - abstract
        raise NotImplementedError

    # arithmetic -----------------------------------------------------------
    def _bin(self, other, op, sym, rev=False):
        a, b = (other, self) if rev else (self, other)
        return BinOp(a, b, op, sym)

    def __add__(self, o): return self._bin(o, operator.add, "+")
    def __radd__(self, o): return self._bin(o, operator.add, "+", True)
    def __sub__(self, o): return self._bin(o, operator.sub, "-")
    def __rsub__(self, o): return self._bin(o, operator.sub, "-", True)
    def __mul__(self, o): return self._bin(o, operator.mul, "*")
    def __rmul__(self, o): return self._bin(o, operator.mul, "*", True)
    def __truediv__(self, o): return self._bin(o, operator.truediv, "/")
    def __rtruediv__(self, o): return self._bin(o, operator.truediv, "/", True)
    def __neg__(self): return Func("neg", operator.neg, (self,))


@dataclass(frozen=True, eq=False)
class ParamRef(Expr):
    """Reference to a declared design parameter (created by `Design.param`)."""
    name: str

    def evaluate(self, env):
        try:
            return env.params[self.name]
        except KeyError:
            raise KeyError(f"parameter {self.name!r} is not declared") from None

    def __repr__(self):
        return self.name


@dataclass(frozen=True, eq=False)
class BinOp(Expr):
    a: Any
    b: Any
    op: Callable
    sym: str

    def evaluate(self, env):
        return self.op(ev(self.a, env), ev(self.b, env))

    def __repr__(self):
        return f"({self.a!r} {self.sym} {self.b!r})"


@dataclass(frozen=True, eq=False)
class Func(Expr):
    """A named pure function applied to (lazy) arguments, e.g. `clearance(screw)`."""
    name: str
    fn: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)

    def evaluate(self, env):
        return self.fn(*(ev(a, env) for a in self.args), **{k: ev(v, env) for k, v in self.kwargs.items()})

    def __repr__(self):
        parts = [repr(a) for a in self.args] + [f"{k}={v!r}" for k, v in self.kwargs.items()]
        return f"{self.name}({', '.join(parts)})"


def lift(name: str, fn: Callable) -> Callable[..., Func]:
    """Turn a plain function into an expression constructor: `lift('sqrt', math.sqrt)(x)`."""
    def make(*args, **kwargs):
        return Func(name, fn, tuple(args), dict(kwargs))
    make.__name__ = name
    return make


emin = lift("min", min)
emax = lift("max", max)
sqrt = lift("sqrt", math.sqrt)


@dataclass(frozen=True)
class Param:
    """A declared design parameter: the *only* place literals belong (architecture §8.1).

    numeric: `default` with an inclusive `range=(lo, hi)`; choice: `choices=(...)`.
    `samples` optionally lists the values the stability harness should sweep.
    """
    name: str
    default: Any
    range: tuple | None = None
    choices: tuple | None = None
    unit: str = ""
    doc: str = ""
    samples: tuple | None = None

    def validate(self, value):
        if self.choices is not None:
            if value not in self.choices:
                raise ValueError(f"{self.name}={value!r} not in {self.choices}")
        elif self.range is not None:
            lo, hi = self.range
            if not (lo - 1e-12 <= float(value) <= hi + 1e-12):
                raise ValueError(f"{self.name}={value!r} outside declared range [{lo}, {hi}]")
        return value

    def sweep_values(self) -> tuple:
        """Values the stability harness visits (dsl.md §5.7): explicit samples, else lo/default/hi."""
        if self.samples is not None:
            return tuple(self.samples)
        if self.choices is not None:
            return tuple(self.choices)
        if self.range is not None:
            lo, hi = self.range
            return tuple(dict.fromkeys((lo, self.default, hi)))
        return (self.default,)
