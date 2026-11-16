"""Structured, readable errors.

Every failure names *where* (feature id + intent tags), *what* (the invariant or rule)
and *why* (expected vs. got).  The GUI and the intent engine read the fields; humans
read `str(err)`.  dsl.md §4.3 (failure classes) and §5 (invariants).
"""
from __future__ import annotations


class DipmError(Exception):
    """Base error.  Fields are optional; `str()` renders whatever is known."""

    kind = "error"

    def __init__(self, message: str, *, feature: str | None = None, intent: tuple = (),
                 invariant: str | None = None, expected=None, got=None, details: dict | None = None):
        self.message = message
        self.feature = feature
        self.intent = tuple(intent)
        self.invariant = invariant
        self.expected = expected
        self.got = got
        self.details = dict(details or {})
        super().__init__(self.render())

    def render(self) -> str:
        head = f"[{self.kind}]"
        if self.feature:
            head += f" feature {self.feature}"
        if self.intent:
            head += " (" + ", ".join(str(t) for t in self.intent) + ")"
        lines = [head, f"  {self.message}"]
        if self.invariant:
            lines.append(f"  invariant: {self.invariant}")
        if self.expected is not None or self.got is not None:
            lines.append(f"  expected:  {self.expected}")
            lines.append(f"  got:       {self.got}")
        for k, v in self.details.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message, "feature": self.feature,
                "intent": [str(t) for t in self.intent], "invariant": self.invariant,
                "expected": None if self.expected is None else str(self.expected),
                "got": None if self.got is None else str(self.got),
                "details": {k: str(v) for k, v in self.details.items()}}


class InvariantError(DipmError):
    """A rung-1 invariant failed after a feature (dsl.md §5)."""
    kind = "invariant"


class ReferenceError_(DipmError):
    """A structural reference could not be resolved as declared (dsl.md §3.4)."""
    kind = "reference"


class CardinalityError(ReferenceError_):
    kind = "cardinality"


class PolicyError(ReferenceError_):
    """A split/merge policy (`error_on_split`, `error_on_merge`) was violated."""
    kind = "policy"


class KernelError(DipmError):
    """The kernel raised or reported failure: failure class 'fails loudly' (dsl.md §4.3)."""
    kind = "kernel"


class InteractionError(DipmError):
    """A feature interacts with existing geometry in a way its intent did not declare
    (e.g. a hole crossing an earlier hole, which changes ΔH; spike 01 §1.4)."""
    kind = "interaction"


class SketchError(DipmError):
    """A sketch profile is degenerate, self-intersecting, or flipped its branch (dsl.md §3.2)."""
    kind = "sketch"


class ParameterError(DipmError):
    kind = "parameter"
